"""Background processing: document ingestion, research jobs and the research scheduler.

A thread pool keeps uploads and research off the request path. Jobs are persisted in the
database (processing_status / research_jobs.status), so their progress is visible in the UI.
A PostgreSQL advisory lock makes the scheduler safe when several API replicas run."""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeDocument, ResearchJob

log = logging.getLogger(__name__)
_executor: ThreadPoolExecutor | None = None
_stop = threading.Event()


def _pool() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=get_settings().background_workers, thread_name_prefix="bui-job")
    return _executor


def submit(fn, *args) -> None:
    if get_settings().run_jobs_inline:
        fn(*args)
    else:
        _pool().submit(fn, *args)


def process_document(document_id: int) -> None:
    """Extracts text from the current version's file (if any) and re-indexes the document."""
    from app.rag import parsers, indexer
    from app.services import storage

    db = SessionLocal()
    try:
        doc = db.get(KnowledgeDocument, document_id)
        if doc is None:
            return
        doc.processing_status = "processing"
        doc.processing_error = None
        db.commit()
        try:
            if doc.file_path:
                ext = "." + doc.original_filename.rsplit(".", 1)[-1].lower() if doc.original_filename and "." in doc.original_filename else ""
                text_content = parsers.extract_text(ext, storage.read_bytes(doc.file_path))
                doc.content = text_content
                if doc.versions:
                    current = next((v for v in doc.versions if v.version == doc.current_version), None)
                    if current is not None:
                        current.content = text_content
            indexer.index_document(db, doc)
            doc.processing_status = "ready"
        except Exception as exc:
            log.exception("Document %s processing failed", document_id)
            db.rollback()
            doc = db.get(KnowledgeDocument, document_id)
            doc.processing_status = "failed"
            doc.processing_error = str(exc)[:1000]
        db.commit()
    finally:
        db.close()


def run_research(job_id: int) -> None:
    from app.research.engine import run_research_job

    db = SessionLocal()
    try:
        job = db.get(ResearchJob, job_id)
        if job is not None:
            run_research_job(db, job)
    finally:
        db.close()


def _scheduler_loop() -> None:
    while not _stop.wait(60):
        try:
            db = SessionLocal()
            try:
                if not db.execute(text("SELECT pg_try_advisory_lock(424242)")).scalar():
                    continue
                try:
                    due = db.scalars(
                        select(ResearchJob.id).where(
                            ResearchJob.schedule_hours.is_not(None),
                            ResearchJob.next_run_at <= datetime.now(timezone.utc),
                            ResearchJob.status != "running",
                        )
                    ).all()
                    for job_id in due:
                        db.get(ResearchJob, job_id).status = "queued"
                        db.commit()
                        submit(run_research, job_id)
                finally:
                    db.execute(text("SELECT pg_advisory_unlock(424242)"))
                    db.commit()
            finally:
                db.close()
        except Exception:  # pragma: no cover - defensive
            log.exception("Research scheduler iteration failed")


def start_scheduler() -> None:
    if get_settings().research_scheduler_enabled and not get_settings().run_jobs_inline:
        threading.Thread(target=_scheduler_loop, name="bui-scheduler", daemon=True).start()
        log.info("Research scheduler started")


def shutdown() -> None:
    _stop.set()
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
    time.sleep(0)
