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


def from_text(text: str, name: str = "Pasted notes") -> Source:
    text = (text or "").strip()
    if len(text) < 80:
        raise SourceError("Add a bit more text. At least a paragraph of notes works best.")
    limit = current_app.config["MAX_TEXT_CHARS"]
    if len(text) > limit:
        raise SourceError(f"That's a lot of text. Please keep it under {limit:,} characters.")
    return Source(name=name, text=text)


def from_upload(file_storage) -> Source:
    if file_storage is None or not file_storage.filename:
        raise SourceError("Choose a file to upload.")
    name = file_storage.filename
    ext = _ext(name)
    if ext not in ALLOWED_EXTENSIONS:
        raise SourceError("That file type isn't supported. Upload a PDF, Word (.docx), PowerPoint (.pptx) or text file.")
    data = file_storage.read()
    if not data:
        raise SourceError("That file is empty.")

    if ext == ".pdf":
        if not data.startswith(b"%PDF"):
            raise SourceError("That doesn't look like a valid PDF.")
        pages = _pdf_page_count(data)
        max_pages = current_app.config["MAX_PDF_PAGES"]
        if pages and pages > max_pages:
            raise SourceError(f"That PDF has {pages} pages. The limit is {max_pages}; try splitting it by topic.")
        return Source(name=name, pdf_bytes=data, pages=pages)

    if ext == ".docx":
        text = _docx_text(data)
    elif ext == ".pptx":
        text = _pptx_text(data)
    else:
        text = data.decode("utf-8", errors="replace")
    return from_text(text, name=name)


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
