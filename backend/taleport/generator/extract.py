"""Text from pasted content or uploaded PDF / DOCX / PPTX / TXT files (offline)."""

from __future__ import annotations

import base64
import binascii
import io
import logging

from taleport.core.errors import AppError

log = logging.getLogger(__name__)

MAX_FILE_BYTES = 15 * 1024 * 1024
# The whole text goes into one prompt: beyond this the user is told it was shortened.
MAX_CONTENT_CHARS = 60_000


def extract_text(filename: str, data_base64: str) -> str:
    try:
        data = base64.b64decode(data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AppError("content.unreadable") from exc
    if len(data) > MAX_FILE_BYTES:
        raise AppError("content.too_large", max_mb=MAX_FILE_BYTES // (1024 * 1024))
    name = filename.lower()
    try:
        if name.endswith(".pdf"):
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        elif name.endswith(".docx"):
            text = _docx_text(data)
        elif name.endswith(".pptx"):
            text = _pptx_text(data)
        elif name.endswith((".txt", ".md")):
            text = data.decode("utf-8", errors="replace")
        else:
            raise AppError("content.unsupported_format")
    except AppError:
        raise
    except Exception as exc:  # corrupt or protected files
        log.info("Could not read %s: %s", filename, exc)
        raise AppError("content.unreadable") from exc
    text = text.strip()
    if not text:
        raise AppError("content.empty")  # e.g. a scanned PDF without a text layer
    return text


def _docx_text(data: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(data))
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(dict.fromkeys(cells)))  # merged cells repeat
    return "\n".join(parts)


def _pptx_text(data: bytes) -> str:
    """Slide by slide: titles, text boxes, tables and speaker notes."""
    from pptx import Presentation

    deck = Presentation(io.BytesIO(data))
    slides = []
    for number, slide in enumerate(deck.slides, start=1):
        lines: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                lines += [p.text for p in shape.text_frame.paragraphs if p.text.strip()]
            elif getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if cells:
                        lines.append(" | ".join(cells))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                lines.append(notes)
        if lines:
            slides.append(f"[{number}]\n" + "\n".join(lines))
    return "\n\n".join(slides)


def limit_content(text: str) -> tuple[str, bool]:
    """(text, truncated): cut at a paragraph boundary when longer than the limit."""
    text = text.strip()
    if len(text) <= MAX_CONTENT_CHARS:
        return text, False
    cut = text[:MAX_CONTENT_CHARS]
    boundary = cut.rfind("\n\n")
    return (cut[:boundary] if boundary > MAX_CONTENT_CHARS * 0.8 else cut), True
