"""Turn an upload into something the model can read.

PDFs are sent to Gemini as-is (it reads text, diagrams and scanned pages).
Word, PowerPoint and text files are converted to plain text here.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from flask import current_app

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md"}


class SourceError(ValueError):
    """A problem with the user's file that we can explain to them."""


@dataclass
class Source:
    name: str
    pdf_bytes: bytes | None = None
    text: str | None = None
    pages: int | None = None

    @property
    def is_pdf(self) -> bool:
        return self.pdf_bytes is not None


def _ext(filename: str) -> str:
    filename = (filename or "").lower()
    return filename[filename.rfind("."):] if "." in filename else ""


def from_text(text: str, name: str = "Pasted notes", max_chars: int | None = None) -> Source:
    text = (text or "").strip()
    if len(text) < 80:
        raise SourceError("Add a bit more text. At least a paragraph of notes works best.")
    limit = min(max_chars or current_app.config["MAX_TEXT_CHARS"], current_app.config["MAX_TEXT_CHARS"])
    if len(text) > limit:
        raise SourceError(f"That's a lot of text. Please keep it under {limit:,} characters, "
                          "or split it into a few sets by topic.")
    return Source(name=name, text=text)


class PlanLimitError(SourceError):
    """A file is over the free plan's size limits (shown with an upgrade prompt)."""


def from_upload(file_storage, max_pages: int | None = None, max_mb: int | None = None,
                max_chars: int | None = None, pro: bool = True) -> Source:
    if file_storage is None or not file_storage.filename:
        raise SourceError("Choose a file to upload.")
    name = file_storage.filename
    ext = _ext(name)
    if ext not in ALLOWED_EXTENSIONS:
        raise SourceError("That file type isn't supported. Upload a PDF, Word (.docx), PowerPoint (.pptx) or text file.")
    data = file_storage.read()
    if not data:
        raise SourceError("That file is empty.")
    if max_mb and len(data) > max_mb * 1024 * 1024:
        msg = f"That file is over {max_mb}MB."
        if not pro:
            raise PlanLimitError(msg + " Pro accepts files up to 30MB, or split it into smaller PDFs.")
        raise SourceError(msg)

    if ext == ".pdf":
        if not data.startswith(b"%PDF"):
            raise SourceError("That doesn't look like a valid PDF.")
        pages = _pdf_page_count(data)
        max_pages = min(max_pages or current_app.config["MAX_PDF_PAGES"], current_app.config["MAX_PDF_PAGES"])
        if pages and pages > max_pages:
            msg = f"That PDF has {pages} pages. The limit is {max_pages}"
            if not pro:
                raise PlanLimitError(msg + " on the free plan. Pro handles up to 150 pages, or split it by topic.")
            raise SourceError(msg + "; try splitting it by topic.")
        return Source(name=name, pdf_bytes=data, pages=pages)

    if ext == ".docx":
        text = _docx_text(data)
    elif ext == ".pptx":
        text = _pptx_text(data)
    else:
        text = data.decode("utf-8", errors="replace")
    return from_text(text, name=name, max_chars=max_chars)


def _pdf_page_count(data: bytes) -> int | None:
    try:
        from pypdf import PdfReader

        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception:
        return None  # Let the model try; it copes with slightly broken PDFs.


def _docx_text(data: bytes) -> str:
    try:
        import docx

        document = docx.Document(io.BytesIO(data))
    except Exception as exc:  # pragma: no cover - depends on file
        raise SourceError("We couldn't open that Word document.") from exc
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(parts)


def _pptx_text(data: bytes) -> str:
    try:
        from pptx import Presentation

        deck = Presentation(io.BytesIO(data))
    except Exception as exc:  # pragma: no cover - depends on file
        raise SourceError("We couldn't open that PowerPoint file.") from exc
    parts = []
    for number, slide in enumerate(deck.slides, start=1):
        parts.append(f"\n--- Slide {number} ---")
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip():
                parts.append(shape.text_frame.text)
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            parts.append("Speaker notes: " + slide.notes_slide.notes_text_frame.text)
    return "\n".join(parts)
