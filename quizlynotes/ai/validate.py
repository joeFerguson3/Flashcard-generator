"""Server-side checks on model output.

Structured output guarantees the *shape* of the JSON; these functions check
that the *content* is usable (e.g. the correct option is actually one of the
options) and silently drop or repair anything that isn't.
"""
from __future__ import annotations

import re

from ..sanitize import clean_text

_BLANK_RE = re.compile(r"\{blank\}|_{3,}|\[blank\]", re.IGNORECASE)
_BULLET_RE = re.compile(r"^\s*(?:[-*•–]+|\d+[.)])\s*")


def clean_notes(sections: list[dict]) -> list[dict]:
    cleaned = []
    for raw in sections or []:
        heading = clean_text(raw.get("heading"), 200)
        subheading = clean_text(raw.get("subheading"), 200)
        points = []
        for p in raw.get("points") or []:
            if isinstance(p, str):
                p = {"text": p, "level": 1}
            text = _BULLET_RE.sub("", clean_text(p.get("text"), 1000))
            if not text:
                continue
            try:
                level = int(p.get("level", 1))
            except (TypeError, ValueError):
                level = 1
            points.append({"text": text, "level": min(3, max(1, level))})
        if not points and not subheading:
            continue
        cleaned.append({
            "heading": heading or subheading or "Notes",
            "subheading": subheading or heading or "Overview",
            "points": points,
        })
    return cleaned


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _unique(items: list[str]) -> list[str]:
    seen, out = set(), []
    for item in items:
        if _norm(item) not in seen:
            seen.add(_norm(item))
            out.append(item)
    return out


def clean_card(raw: dict, section_count: int) -> dict | None:
    kind = raw.get("kind")
    prompt = clean_text(raw.get("prompt"), 1000)
    options = [clean_text(o, 300) for o in (raw.get("options") or []) if clean_text(o, 300)]
    answers = [clean_text(a, 300) for a in (raw.get("answers") or []) if clean_text(a, 300)]
    explanation = clean_text(raw.get("explanation"), 1000)
    try:
        section = int(raw.get("section", 0))
    except (TypeError, ValueError):
        section = 0
    section = min(max(section, 0), max(section_count - 1, 0))

    if not prompt:
        return None

    if kind == "flashcard":
        if not answers:
            return None
        options, answers = [], [answers[0]]

    elif kind == "multiple_choice":
        # De-duplicate options, keep order.
        seen, unique = set(), []
        for o in options:
            if _norm(o) not in seen:
                seen.add(_norm(o))
                unique.append(o)
        options = unique
        if not answers or not 2 <= len(options) <= 6:
            return None
        match = next((o for o in options if _norm(o) == _norm(answers[0])), None)
        if match is None:
            # Model sometimes answers "B" or "Option B".
            letter = re.fullmatch(r"(?:option\s*)?([a-f])[.)]?", answers[0].strip().lower())
            if letter and ord(letter.group(1)) - 97 < len(options):
                match = options[ord(letter.group(1)) - 97]
        if match is None:
            return None
        bad = {"all of the above", "none of the above"}
        if any(_norm(o) in bad for o in options):
            return None
        answers = [match]

    elif kind == "true_false":
        if not answers:
            return None
        value = _norm(answers[0])
        if value in {"true", "t", "yes"}:
            answers = ["true"]
        elif value in {"false", "f", "no"}:
            answers = ["false"]
        else:
            return None
        options = []

    elif kind == "fill_blank":
        prompt = _BLANK_RE.sub("{blank}", prompt)
        blanks = prompt.count("{blank}")
        if blanks == 0 or len(answers) < blanks:
            return None
        answers = answers[:blanks]
        options = []

    elif kind == "short_answer":
        if not answers:
            return None
        options = []
        answers = answers[:6]

    elif kind == "ordering":
        seen, unique = set(), []
        for o in options:
            if _norm(o) not in seen:
                seen.add(_norm(o))
                unique.append(o)
        if not 3 <= len(unique) <= 8:
            return None
        options, answers = unique, []

    elif kind == "matching":
        if len(options) != len(answers) or not 3 <= len(options) <= 6:
            return None
        if len({_norm(o) for o in options}) != len(options) or len({_norm(a) for a in answers}) != len(answers):
            return None

    elif kind == "multi_select":
        options = _unique(options)
        if not 4 <= len(options) <= 7:
            return None
        lookup = {_norm(o): o for o in options}
        correct = []
        for a in answers:
            match = lookup.get(_norm(a))
            if match and match not in correct:
                correct.append(match)
        if not 2 <= len(correct) < len(options):
            return None
        answers = correct

    elif kind == "categorize":
        if len(options) != len(answers) or not 3 <= len(options) <= 10:
            return None
        if len({_norm(o) for o in options}) != len(options):
            return None
        # Normalise category spelling to the first form used.
        canon = {}
        answers = [canon.setdefault(_norm(a), a) for a in answers]
        if not 2 <= len(canon) <= 4:
            return None

    elif kind == "numeric":
        if not answers:
            return None
        number = answers[0].replace(",", "").replace(" ", "")
        try:
            float(number)
        except ValueError:
            return None
        answers = [number] + ([answers[1][:30]] if len(answers) > 1 else [])
        options = []

    elif kind == "explain":
        answers = answers[:5]
        if len(answers) < 2:
            return None
        options = []

    else:
        return None

    return {
        "section": section,
        "kind": kind,
        "prompt": prompt,
        "options": options,
        "answers": answers,
        "explanation": explanation,
    }


def clean_cards(raw_cards: list[dict], section_count: int) -> list[dict]:
    result, seen = [], set()
    for raw in raw_cards or []:
        card = clean_card(raw, section_count)
        if card is None:
            continue
        key = (card["kind"] == "flashcard", _norm(card["prompt"]))
        if key in seen:
            continue
        seen.add(key)
        result.append(card)
    return result
