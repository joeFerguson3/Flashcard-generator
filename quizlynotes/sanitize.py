"""Text sanitisation for user input and model output.

Jinja auto-escaping protects HTML templates and the front-end inserts text
with textContent, so this is about keeping stored data tidy: no control
characters, no stray HTML tags, sensible lengths.
"""
from __future__ import annotations

import re
from typing import Any

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")


def clean_text(value: Any, max_length: int = 1024) -> str:
    if value is None:
        return ""
    text = str(value)
    text = _CONTROL_CHAR_RE.sub("", text)
    text = _TAG_RE.sub("", text)
    text = text.strip()
    return text[:max_length]


def clean_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
