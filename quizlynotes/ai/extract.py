"""Turn an upload into something the model can read.

PDFs are sent to Gemini as-is (it reads text, diagrams and scanned pages).
Word, PowerPoint and text files are converted to plain text here.
"""
from __future__ import annotations

import io
import multiprocessing
import zipfile
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
        pages = _isolated(_pdf_page_count, data)
        if not pages:
            raise SourceError("We couldn't read that PDF. Try exporting it again, or upload it as Word or PowerPoint.")
        max_pages = min(max_pages or current_app.config["MAX_PDF_PAGES"], current_app.config["MAX_PDF_PAGES"])
        if pages > max_pages:
            msg = f"That PDF has {pages} pages. The limit is {max_pages}"
            if not pro:
                raise PlanLimitError(msg + " on the free plan. Pro handles up to 150 pages, or split it by topic.")
            raise SourceError(msg + "; try splitting it by topic.")
        return Source(name=name, pdf_bytes=data, pages=pages)

    limit = min(max_chars or current_app.config["MAX_TEXT_CHARS"], current_app.config["MAX_TEXT_CHARS"])
    if ext in (".docx", ".pptx"):
        _check_zip(data)
        text = _isolated(_docx_text if ext == ".docx" else _pptx_text, data, limit + 1)
        if text is None:
            kind = "Word document" if ext == ".docx" else "PowerPoint file"
            raise SourceError(f"We couldn't open that {kind}. Try saving it again, or upload it as a PDF.")
    else:
        text = data.decode("utf-8", errors="replace")
    return from_text(text, name=name, max_chars=max_chars)


# --- Parsing untrusted files safely ------------------------------------------------
# Word/PowerPoint files are zip archives and PDFs can be crafted to make parsers loop or
# eat memory, so parsing happens in a short-lived child process with a memory cap and a
# time limit. If it fails or runs out of time, the upload is rejected.

PARSE_TIMEOUT = 25        # seconds
PARSE_MEMORY = 1024 ** 3  # 1 GB address space for the child


def _zip_limits():
    return {"members": 3000, "total": 150 * 1024 * 1024, "member": 60 * 1024 * 1024, "ratio": 120}


def _check_zip(data: bytes) -> None:
    """Reject zip bombs before python-docx / python-pptx expand them."""
    lim = _zip_limits()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
    except zipfile.BadZipFile as exc:
        raise SourceError("That file looks damaged. Try saving it again.") from exc
    if len(infos) > lim["members"]:
        raise SourceError("That file is too complex to read. Try saving it as a PDF.")
    total = 0
    for info in infos:
        total += info.file_size
        if info.file_size > lim["member"] or total > lim["total"]:
            raise SourceError("That file is too large once unpacked. Try saving it as a PDF.")
        if info.file_size > 1024 * 1024 and info.file_size > lim["ratio"] * max(info.compress_size, 1):
            raise SourceError("That file is too large once unpacked. Try saving it as a PDF.")


def _child(conn, func, data, args):
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (PARSE_MEMORY, PARSE_MEMORY))
    except Exception:  # pragma: no cover - not available on every OS
        pass
    try:
        conn.send(("ok", func(data, *args)))
    except BaseException as exc:  # noqa: BLE001 - report any failure to the parent
        conn.send(("error", type(exc).__name__))
    finally:
        conn.close()


def _isolated(func, data: bytes, *args):
    """Run func(data, *args) in a child process; return its result, or None on failure/timeout."""
    if current_app.config.get("TESTING") or not hasattr(__import__("os"), "fork"):
        try:
            return func(data, *args)
        except Exception:
            return None
    ctx = multiprocessing.get_context("fork")
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child, args=(child, func, data, args), daemon=True)
    proc.start()
    child.close()
    try:
        if not parent.poll(PARSE_TIMEOUT):
            current_app.logger.warning("file parse timed out (%s)", func.__name__)
            return None
        status, value = parent.recv()
        return value if status == "ok" else None
    except EOFError:  # child died (e.g. hit the memory cap)
        return None
    finally:
        parent.close()
        if proc.is_alive():
            proc.kill()
        proc.join(1)


def _pdf_page_count(data: bytes) -> int | None:
    from pypdf import PdfReader

    return len(PdfReader(io.BytesIO(data)).pages)


def _docx_text(data: bytes, max_chars: int = 10**9) -> str:
    import docx

    document = docx.Document(io.BytesIO(data))
    parts, size = [], 0
    for p in document.paragraphs:
        if p.text.strip():
            parts.append(p.text)
            size += len(p.text)
            if size > max_chars:
                return "\n".join(parts)
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
            size += len(parts[-1])
            if size > max_chars:
                return "\n".join(parts)
    return "\n".join(parts)


def _pptx_text(data: bytes, max_chars: int = 10**9) -> str:
    from pptx import Presentation

    deck = Presentation(io.BytesIO(data))
    parts, size = [], 0
    for number, slide in enumerate(deck.slides, start=1):
        parts.append(f"\n--- Slide {number} ---")
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip():
                parts.append(shape.text_frame.text)
                size += len(parts[-1])
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            parts.append("Speaker notes: " + slide.notes_slide.notes_text_frame.text)
            size += len(parts[-1])
        if size > max_chars:
            break
    return "\n".join(parts)
