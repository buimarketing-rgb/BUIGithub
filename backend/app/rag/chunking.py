"""Splits text into overlapping, heading-aware chunks."""
import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{1,6}\s+.+|\[Page \d+\]|\[Sheet: .+\]|[A-Z][A-Za-z0-9 /&\-]{2,60}:)\s*$")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    text: str
    section: str | None


def _split_long(paragraph: str, size: int) -> list[str]:
    if len(paragraph) <= size:
        return [paragraph]
    parts, buf = [], ""
    for sentence in _SENTENCE_RE.split(paragraph):
        while len(sentence) > size:  # extremely long "sentence" (e.g. tables)
            parts.append(sentence[:size])
            sentence = sentence[size:]
        if len(buf) + len(sentence) + 1 > size and buf:
            parts.append(buf)
            buf = ""
        buf = f"{buf} {sentence}".strip()
    if buf:
        parts.append(buf)
    return parts


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> list[Chunk]:
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[Chunk] = []
    buf, section, buf_section = "", None, None

    def flush() -> None:
        nonlocal buf
        if buf.strip():
            chunks.append(Chunk(buf.strip(), buf_section))
        buf = buf[-overlap:] if overlap and len(buf) > overlap else ""
        # start overlap at a word boundary
        if buf and " " in buf:
            buf = buf[buf.index(" ") + 1 :]

    for para in paragraphs:
        first_line = para.split("\n", 1)[0].strip()
        if _HEADING_RE.match(first_line):
            heading = first_line.lstrip("#").strip().rstrip(":")
            if heading != section:
                if buf.strip() and len(buf) > overlap:
                    flush()
                    buf = ""
                section = heading
        for piece in _split_long(para, size):
            if not buf.strip():
                buf_section = section
            if len(buf) + len(piece) + 2 > size and buf.strip():
                flush()
                buf_section = section
            buf = f"{buf}\n\n{piece}" if buf else piece
    if buf.strip():
        chunks.append(Chunk(buf.strip(), buf_section))
    # Drop chunks that are pure overlap duplicates of the previous chunk
    deduped: list[Chunk] = []
    for c in chunks:
        if deduped and c.text in deduped[-1].text:
            continue
        deduped.append(c)
    return deduped
