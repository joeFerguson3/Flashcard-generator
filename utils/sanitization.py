"""Utility functions for sanitising user and model generated text."""
from __future__ import annotations

import re
from typing import Any

# Pattern to remove ASCII control characters except for new lines and tabs.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_text(value: Any, max_length: int = 1024) -> str:
    """Return a normalised, length-limited string without HTML tags.

    Args:
        value: The value to sanitise. Non-string values are coerced to strings.
        max_length: Maximum number of characters to retain after sanitisation.

    Returns:
        A stripped, control-character-free string limited to ``max_length``
        characters with any HTML tags removed.
    """

    if value is None:
        return ""

    text = str(value)
    text = _CONTROL_CHAR_RE.sub("", text)
    text = _TAG_RE.sub("", text)
    text = text.strip()
    if len(text) > max_length:
        text = text[:max_length]
    return text


def sanitize_structure(data: Any, max_length: int = 1024) -> Any:
    """Recursively sanitise any strings within a nested data structure."""

    if isinstance(data, dict):
        return {key: sanitize_structure(value, max_length) for key, value in data.items()}
    if isinstance(data, list):
        return [sanitize_structure(item, max_length) for item in data]
    if isinstance(data, str):
        return sanitize_text(data, max_length)

    return data
