"""Local file storage for uploads. Files are stored under random names outside the web root and
served only through authenticated API endpoints."""
import secrets
from pathlib import Path

from app.core.config import get_settings


def upload_root() -> Path:
    root = get_settings().upload_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_bytes(subdir: str, extension: str, data: bytes) -> str:
    folder = upload_root() / subdir
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(16)}{extension}"
    (folder / name).write_bytes(data)
    return f"{subdir}/{name}"


def resolve(relative: str) -> Path:
    path = (upload_root() / relative).resolve()
    if upload_root() not in path.parents:
        raise ValueError("Invalid storage path")
    return path


def read_bytes(relative: str) -> bytes:
    return resolve(relative).read_bytes()


def delete(relative: str | None) -> None:
    if not relative:
        return
    try:
        resolve(relative).unlink(missing_ok=True)
    except ValueError:
        pass
