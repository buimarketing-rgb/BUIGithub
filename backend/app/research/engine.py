"""Online research workflow: search -> fetch (robots-aware) -> extract -> organise -> flag
duplicates/conflicts -> store as *pending* findings for administrator review.

Research NEVER modifies verified company information by itself. Only an administrator's explicit
approval (see approve_finding) moves information into the knowledge base."""
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Product, ResearchFinding, ResearchJob, ResearchSource, User
from app.rag.embeddings import tokenize
from app.rag.safety import sanitize_source_text
from app.research.extractor import extract_page, normalize_key, normalize_value
from app.research.fetcher import get_fetcher
from app.research.search import SearchUnavailable, get_search_provider
from app.services.system_settings import get_setting

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _log(job: ResearchJob, msg: str) -> None:
    job.log = [*(job.log or []), {"at": _now().isoformat(), "msg": msg}]


def domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_official(url: str, db: Session, product: Product | None) -> bool:
    d = domain_of(url)
    official = [x.lower().removeprefix("www.") for x in (get_setting(db, "official_domains") or [])]
    if product:
        official += [domain_of(u) for u in (product.source_urls or []) if u]
        if product.brand:
            brand = re.sub(r"[^a-z0-9]", "", product.brand.lower())
            if brand and len(brand) >= 3 and brand in d.replace("-", "").replace(".", ""):
                return True
    return any(d == o or d.endswith("." + o) for o in official if o)


def build_queries(job: ResearchJob, product: Product | None) -> list[str]:
    if job.query:
        base = job.query
    elif product:
        base = " ".join(x for x in (product.brand, product.name, product.model_number) if x)
    else:
        return []
    queries = [f"{base} specifications"]
    if product or job.query:
        queries += [f"{base} manual", f"{base} warranty"]
    return queries


def run_research_job(db: Session, job: ResearchJob) -> ResearchJob:
    s = get_settings()
    job.status = "running"
    job.error = None
    _log(job, "Research started")
    db.commit()
    product = db.get(Product, job.product_id) if job.product_id else None
    fetcher = get_fetcher()
    try:
        candidates: list[tuple[str, str, str]] = []  # url, title, snippet
        if job.url:
            candidates.append((job.url, job.url, ""))
        else:
            provider = get_search_provider()
            if provider is None:
                raise SearchUnavailable("No search provider configured (set SEARCH_PROVIDER / SEARXNG_URL), or research a specific URL instead.")
            seen = set()
            for q in build_queries(job, product):
                _log(job, f"Searching: {q}")
                for r in provider.search(q, s.research_max_pages * 2):
                    if r.url not in seen:
                        seen.add(r.url)
                        candidates.append((r.url, r.title, r.snippet))
            # Prefer official manufacturer websites
            candidates.sort(key=lambda c: 0 if is_official(c[0], db, product) else 1)
        if not candidates:
            _log(job, "No search results found")
        existing_hashes = set(
            db.scalars(
                select(ResearchSource.content_hash).join(ResearchJob).where(
                    ResearchJob.product_id == job.product_id if job.product_id else ResearchJob.id == job.id,
                    ResearchSource.content_hash.is_not(None),
                )
            )
        )
        page_items: list[tuple[ResearchSource, list]] = []
        for url, title, snippet in candidates[: s.research_max_pages]:
            fr = fetcher.fetch(url)
            src = ResearchSource(
                job_id=job.id, url=fr.url[:1000], domain=domain_of(fr.url), title=title[:500], snippet=snippet,
                is_official=is_official(fr.url, db, product), robots_allowed=fr.status != "blocked_robots",
                fetch_status=fr.status, http_status=fr.http_status, retrieved_at=_now(),
            )
            db.add(src)
            db.flush()
            if fr.status != "fetched" or not fr.html:
                _log(job, f"Skipped {fr.url}: {fr.error or fr.status}")
                continue
            page = extract_page(fr.html)
            src.title = page.title[:500]
            src.extracted_text = sanitize_source_text(page.text)
            src.content_hash = hashlib.sha256(page.text.encode()).hexdigest()
            if src.content_hash in existing_hashes:
                _log(job, f"Duplicate page content (already researched): {fr.url}")
                continue
            existing_hashes.add(src.content_hash)
            _log(job, f"Extracted {len(page.items)} items from {src.domain}{' (official)' if src.is_official else ''}")
            page_items.append((src, page.items))
        _create_findings(db, job, product, page_items)
        job.status = "completed"
        _log(job, f"Research completed: {len(job.findings)} findings pending review")
    except Exception as exc:
        log.exception("Research job %s failed", job.id)
        job.status = "failed"
        job.error = str(exc)[:1000]
        _log(job, f"Failed: {exc}")
    job.last_run_at = _now()
    job.next_run_at = _now() + timedelta(hours=job.schedule_hours) if job.schedule_hours else None
    db.commit()
    return job


def _create_findings(db: Session, job: ResearchJob, product: Product | None, page_items) -> None:
    verified_specs = {normalize_key(k): (k, str(v)) for k, v in ((product.specifications or {}) if product else {}).items()}
    known: set[tuple[str, str]] = set()
    if product:
        for f in db.scalars(
            select(ResearchFinding).where(ResearchFinding.product_id == product.id, ResearchFinding.status != "rejected", ResearchFinding.job_id != job.id)
        ):
            known.add((normalize_key(f.key), normalize_value(f.value)))
    # Track values per spec key across sources in this job to flag disagreements between sources
    per_key: dict[str, list[ResearchFinding]] = {}
    for src, items in page_items:
        for it in items[:80]:
            nk, nv = normalize_key(it.key), normalize_value(it.value)
            f = ResearchFinding(
                job_id=job.id, source_id=src.id, product_id=product.id if product else None,
                category=it.category, key=it.key, value=sanitize_source_text(it.value),
                confidence=min(1.0, it.confidence + (0.15 if src.is_official else 0.0)),
            )
            if (nk, nv) in known:
                f.is_duplicate = True
            elif it.category == "specification" and nk in verified_specs:
                vk, vv = verified_specs[nk]
                if normalize_value(vv) == nv:
                    f.is_duplicate = True
                else:
                    f.has_conflict = True
                    f.conflict_with = f"Verified company value for '{vk}': {vv}"
            known.add((nk, nv))
            if it.category == "specification" and nk:
                per_key.setdefault(nk, []).append(f)
            db.add(f)
            job.findings.append(f)
    for nk, fs in per_key.items():
        values = {normalize_value(f.value) for f in fs}
        if len(values) > 1:
            for f in fs:
                if not f.has_conflict:
                    others = sorted({o.value for o in fs if normalize_value(o.value) != normalize_value(f.value)})
                    f.has_conflict = True
                    f.conflict_with = "Other sources report: " + "; ".join(others[:3])
    db.flush()


def approve_finding(db: Session, finding: ResearchFinding, user: User, apply_to_product: bool, replace_conflict: bool, note: str | None) -> str:
    """Approves a finding. Returns a description of what happened."""
    from app.rag.indexer import index_product, index_research_finding
    from app.services.products import snapshot_product

    finding.status = "approved"
    finding.reviewed_by_id = user.id
    finding.reviewed_at = _now()
    finding.review_note = note
    outcome = "Added to the knowledge base as approved research."
    product = db.get(Product, finding.product_id) if finding.product_id else None
    if apply_to_product and product:
        changed = False
        if finding.category == "specification" and finding.key:
            specs = dict(product.specifications or {})
            match = next((k for k in specs if normalize_key(k) == normalize_key(finding.key)), None)
            if match is None:
                specs[finding.key] = finding.value
                changed = True
            elif replace_conflict and finding.has_conflict:
                specs[match] = finding.value
                changed = True
            else:
                outcome = "Verified value kept (not overwritten). Finding stored as approved research."
            if changed:
                product.specifications = specs
        elif finding.category == "feature":
            if finding.value not in (product.features or []):
                product.features = [*(product.features or []), finding.value]
                changed = True
        if changed:
            src = finding.source.url if finding.source else None
            if src and src not in (product.source_urls or []):
                product.source_urls = [*(product.source_urls or []), src]
            product.version += 1
            product.updated_by_id = user.id
            db.flush()
            snapshot_product(db, product, user, f"Applied approved research finding #{finding.id}")
            index_product(db, product)
            outcome = f"Applied to product '{product.name}' (version {product.version})."
    index_research_finding(db, finding)
    return outcome


def relevant_excerpt(text: str, question: str, max_chars: int = 1800) -> str:
    q = set(tokenize(question))
    sentences = re.split(r"(?<=[.!?])\s+", text)
    scored = sorted(
        ((len(q & set(tokenize(snt))), i, snt) for i, snt in enumerate(sentences) if 20 < len(snt) < 500),
        key=lambda x: (-x[0], x[1]),
    )
    picked = sorted([x for x in scored if x[0] > 0][:12], key=lambda x: x[1])
    out = " ".join(s for _, _, s in picked)
    return out[:max_chars]


def quick_web_research(db: Session, question: str, user: User, product: Product | None, limit_pages: int = 3) -> tuple[list[dict], ResearchJob]:
    """Chat-triggered research. Returns page excerpts for answering and records a job whose
    findings wait for admin review (nothing is added to the knowledge base automatically)."""
    job = ResearchJob(query=question[:500], product_id=product.id if product else None, origin="chat", created_by_id=user.id, status="running")
    db.add(job)
    db.commit()
    provider = get_search_provider()
    fetcher = get_fetcher()
    pages: list[dict] = []
    page_items = []
    try:
        if provider is None:
            raise SearchUnavailable("Online research is not configured (no search provider).")
        q = question if not product else f"{product.brand or ''} {product.name} {product.model_number or ''} {question}".strip()
        results = provider.search(q, limit_pages * 3)
        results.sort(key=lambda r: 0 if is_official(r.url, db, product) else 1)
        for r in results:
            if len(pages) >= limit_pages:
                break
            fr = fetcher.fetch(r.url)
            src = ResearchSource(
                job_id=job.id, url=fr.url[:1000], domain=domain_of(fr.url), title=(r.title or fr.url)[:500], snippet=r.snippet,
                is_official=is_official(fr.url, db, product), robots_allowed=fr.status != "blocked_robots",
                fetch_status=fr.status, http_status=fr.http_status, retrieved_at=_now(),
            )
            db.add(src)
            db.flush()
            if fr.status != "fetched" or not fr.html:
                continue
            page = extract_page(fr.html)
            src.extracted_text = sanitize_source_text(page.text)
            src.content_hash = hashlib.sha256(page.text.encode()).hexdigest()
            excerpt = relevant_excerpt(src.extracted_text, question) or (page.description or "")
            if not excerpt:
                continue
            pages.append({"url": src.url, "title": page.title, "excerpt": excerpt, "official": src.is_official, "retrieved_at": src.retrieved_at.date().isoformat(), "domain": src.domain})
            page_items.append((src, page.items))
        _create_findings(db, job, product, page_items)
        job.status = "completed"
        _log(job, f"Chat research: {len(pages)} pages used, {len(job.findings)} findings pending review")
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)[:1000]
        _log(job, f"Failed: {exc}")
    job.last_run_at = _now()
    db.commit()
    return pages, job
