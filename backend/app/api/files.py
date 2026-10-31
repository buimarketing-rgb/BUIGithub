"""Serves stored files through short-lived signed URLs (no public file directory)."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_file_signature
from app.models import DocumentVersion, ProductImage
from app.services import storage

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{kind}/{object_id}")
def serve_file(kind: str, object_id: int, exp: int, sig: str, db: Session = Depends(get_db)):
    if not verify_file_signature(kind, object_id, exp, sig):
        raise HTTPException(403, "Link expired or invalid")
    if kind == "image":
        obj = db.get(ProductImage, object_id)
        if not obj:
            raise HTTPException(404)
        path, name, ctype, inline = obj.file_path, obj.original_name, obj.content_type, True
    elif kind == "docver":
        obj = db.get(DocumentVersion, object_id)
        if not obj or not obj.file_path:
            raise HTTPException(404)
        path, name, ctype, inline = obj.file_path, obj.original_filename or "document", obj.content_type or "application/octet-stream", False
    else:
        raise HTTPException(404)
    try:
        full = storage.resolve(path)
    except ValueError:
        raise HTTPException(404)
    if not full.exists():
        raise HTTPException(404, "File missing from storage")
    headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"}
    return FileResponse(full, media_type=ctype, filename=None if inline else name, headers=headers)
