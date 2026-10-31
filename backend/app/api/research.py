from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.models import Product, ResearchFinding, ResearchJob, User
from app.rag.indexer import remove_source
from app.research.engine import approve_finding
from app.research.fetcher import Fetcher
from app.schemas.common import (
    FindingReview, Page, ResearchFindingOut, ResearchJobDetail, ResearchJobIn, ResearchJobOut, ResearchJobUpdate, ResearchSourceOut,
)
from app.services.audit import audit
from app.services.system_settings import get_setting
from app.workers.jobs import run_research, submit

router = APIRouter(prefix="/research", tags=["research"])


def _counts(db: Session, job_ids: list[int]) -> dict[int, dict]:
    out: dict[int, dict] = {jid: {"pending": 0, "approved": 0, "rejected": 0, "conflicts": 0} for jid in job_ids}
    if not job_ids:
        return out
    for jid, status, n in db.execute(select(ResearchFinding.job_id, ResearchFinding.status, func.count()).where(ResearchFinding.job_id.in_(job_ids)).group_by(ResearchFinding.job_id, ResearchFinding.status)):
        out[jid][status] = n
    for jid, n in db.execute(select(ResearchFinding.job_id, func.count()).where(ResearchFinding.job_id.in_(job_ids), ResearchFinding.has_conflict.is_(True), ResearchFinding.status == "pending").group_by(ResearchFinding.job_id)):
        out[jid]["conflicts"] = n
    return out


def _job_out(db: Session, j: ResearchJob, counts: dict) -> ResearchJobOut:
    name = db.scalar(select(Product.name).where(Product.id == j.product_id)) if j.product_id else None
    return ResearchJobOut.model_validate(j).model_copy(update={"product_name": name, "finding_counts": counts.get(j.id, {})})


def _finding_out(f: ResearchFinding) -> ResearchFindingOut:
    return ResearchFindingOut.model_validate(f).model_copy(
        update={
            "source_url": f.source.url if f.source else None, "source_domain": f.source.domain if f.source else None,
            "source_official": bool(f.source and f.source.is_official), "retrieved_at": f.source.retrieved_at if f.source else None,
        }
    )


@router.get("/jobs", response_model=Page[ResearchJobOut])
def list_jobs(
    status: str | None = None, product_id: int | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_admin), db: Session = Depends(get_db),
):
    stmt = select(ResearchJob)
    if status:
        stmt = stmt.where(ResearchJob.status == status)
    if product_id:
        stmt = stmt.where(ResearchJob.product_id == product_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    jobs = db.scalars(stmt.order_by(ResearchJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    counts = _counts(db, [j.id for j in jobs])
    return Page(items=[_job_out(db, j, counts) for j in jobs], total=total, page=page, page_size=page_size)


@router.post("/jobs", response_model=ResearchJobOut, status_code=201)
def create_job(body: ResearchJobIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not get_setting(db, "web_research_enabled"):
        raise HTTPException(400, "Online research is disabled in Settings")
    if not (body.query or body.url or body.product_id):
        raise HTTPException(400, "Enter a product name, a URL, or choose a product")
    if body.url and not body.url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")
    if body.url and not Fetcher.is_public_url(body.url):
        raise HTTPException(400, "Only public website URLs can be researched")
    job = ResearchJob(
        query=(body.query or "").strip() or None, url=body.url, product_id=body.product_id, origin="admin", created_by_id=user.id,
        schedule_hours=body.schedule_hours,
    )
    db.add(job)
    db.flush()
    audit(db, user, "research.create", "research_job", job.id, f"Research: {job.query or job.url or 'product #' + str(job.product_id)}", request=request)
    db.commit()
    submit(run_research, job.id)
    db.refresh(job)
    return _job_out(db, job, _counts(db, [job.id]))


@router.get("/jobs/{job_id}", response_model=ResearchJobDetail)
def get_job(job_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    j = db.get(ResearchJob, job_id)
    if not j:
        raise HTTPException(404, "Research job not found")
    base = _job_out(db, j, _counts(db, [j.id]))
    findings = sorted(j.findings, key=lambda f: (f.status != "pending", not f.has_conflict, f.category, -f.confidence))
    return ResearchJobDetail(
        **base.model_dump(), log=j.log or [], sources=[ResearchSourceOut.model_validate(s) for s in j.sources],
        findings=[_finding_out(f) for f in findings],
    )


@router.patch("/jobs/{job_id}", response_model=ResearchJobOut)
def update_job(job_id: int, body: ResearchJobUpdate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    from datetime import datetime, timedelta, timezone

    j = db.get(ResearchJob, job_id)
    if not j:
        raise HTTPException(404, "Research job not found")
    if body.clear_schedule:
        j.schedule_hours, j.next_run_at = None, None
    elif body.schedule_hours:
        j.schedule_hours = body.schedule_hours
        j.next_run_at = datetime.now(timezone.utc) + timedelta(hours=body.schedule_hours)
    audit(db, user, "research.schedule", "research_job", j.id, f"Schedule: {j.schedule_hours or 'manual'}")
    db.commit()
    return _job_out(db, j, _counts(db, [j.id]))


@router.post("/jobs/{job_id}/run", response_model=ResearchJobOut)
def rerun_job(job_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    j = db.get(ResearchJob, job_id)
    if not j:
        raise HTTPException(404, "Research job not found")
    if j.status == "running":
        raise HTTPException(409, "This research job is already running")
    j.status = "queued"
    audit(db, user, "research.refresh", "research_job", j.id, "Manual refresh")
    db.commit()
    submit(run_research, j.id)
    db.refresh(j)
    return _job_out(db, j, _counts(db, [j.id]))


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    j = db.get(ResearchJob, job_id)
    if not j:
        raise HTTPException(404, "Research job not found")
    for f in j.findings:
        remove_source(db, "research", f.id)
    audit(db, user, "research.delete", "research_job", j.id, "Deleted research job")
    db.delete(j)
    db.commit()


@router.get("/findings", response_model=Page[ResearchFindingOut])
def list_findings(
    status: str = "pending", product_id: int | None = None, conflicts_only: bool = False,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), _: User = Depends(require_admin), db: Session = Depends(get_db),
):
    stmt = select(ResearchFinding).where(ResearchFinding.status == status)
    if product_id:
        stmt = stmt.where(ResearchFinding.product_id == product_id)
    if conflicts_only:
        stmt = stmt.where(ResearchFinding.has_conflict.is_(True))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(ResearchFinding.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=[_finding_out(f) for f in rows], total=total, page=page, page_size=page_size)


@router.post("/findings/review")
def review_findings(body: FindingReview, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if body.action not in ("approve", "reject"):
        raise HTTPException(400, "action must be approve or reject")
    results = []
    from datetime import datetime, timezone

    for fid in body.finding_ids:
        f = db.get(ResearchFinding, fid)
        if not f:
            results.append({"id": fid, "result": "not found"})
            continue
        if body.action == "approve":
            outcome = approve_finding(db, f, user, body.apply_to_product, body.replace_conflicts, body.note)
        else:
            f.status, f.reviewed_by_id, f.reviewed_at, f.review_note = "rejected", user.id, datetime.now(timezone.utc), body.note
            remove_source(db, "research", f.id)
            outcome = "Rejected"
        results.append({"id": fid, "result": outcome})
        db.flush()
    audit(db, user, f"research.{body.action}", "research_finding", ",".join(map(str, body.finding_ids))[:50], f"{body.action.title()}d {len(body.finding_ids)} finding(s)", {"results": results}, request=request)
    db.commit()
    return {"results": results}
