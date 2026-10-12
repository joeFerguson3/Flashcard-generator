"""Creating, updating and scoring study sets."""
from __future__ import annotations

from datetime import timedelta

from ..ai.validate import clean_card, clean_notes
from ..extensions import db
from ..models import Attempt, Card, Section, StudySet, utcnow
from ..sanitize import clean_int, clean_text


def create_set(user, notes: dict, *, title: str = "", subject: str = "", source_name: str = "") -> StudySet:
    study_set = StudySet(
        owner=user,
        title=clean_text(title, 200) or clean_text(notes.get("title"), 200) or "Untitled notes",
        subject=clean_text(subject, 120) or clean_text(notes.get("subject"), 120) or "General",
        source_name=clean_text(source_name, 255) or None,
    )
    db.session.add(study_set)
    for position, s in enumerate(clean_notes(notes.get("sections", []))):
        study_set.sections.append(Section(position=position, **s))
    db.session.flush()
    return study_set


def save_sections(study_set: StudySet, raw_sections: list[dict]) -> None:
    """Apply the notes editor's state, keeping section ids stable so
    existing cards stay linked to the right section."""
    existing = {s.id: s for s in study_set.sections}
    keep_ids = set()
    position = 0
    for raw in raw_sections or []:
        cleaned = clean_notes([raw])
        if not cleaned:
            continue
        data = cleaned[0]
        section_id = clean_int(raw.get("id"))
        section = existing.get(section_id) if section_id else None
        if section is None:
            section = Section(study_set=study_set)
            db.session.add(section)
        section.position = position
        section.heading = data["heading"]
        section.subheading = data["subheading"]
        section.points = data["points"]
        if section.id:
            keep_ids.add(section.id)
        position += 1
    for section_id, section in existing.items():
        if section_id not in keep_ids:
            study_set.sections.remove(section)
            db.session.delete(section)
    study_set.updated_at = utcnow()
    db.session.flush()


def replace_cards(study_set: StudySet, cards: list[dict]) -> None:
    sections = list(study_set.sections)
    for card in list(study_set.cards):
        study_set.cards.remove(card)
        db.session.delete(card)
    db.session.flush()
    for position, data in enumerate(cards):
        index = data.get("section", 0)
        section = sections[index] if 0 <= index < len(sections) else None
        study_set.cards.append(Card(
            position=position,
            section_id=section.id if section else None,
            kind=data["kind"],
            prompt=data["prompt"],
            options=data["options"],
            answers=data["answers"],
            explanation=data.get("explanation", ""),
        ))
    study_set.updated_at = utcnow()
    db.session.flush()


def update_card_from_form(card: Card, form, prefix: str) -> bool:
    """Apply edits from the card editor. Returns False if the result is invalid."""
    def field(name, limit=1000):
        return clean_text(form.get(f"{prefix}-{name}"), limit)

    def lines(name):
        return [clean_text(x, 300) for x in (form.get(f"{prefix}-{name}") or "").splitlines() if x.strip()]

    raw = {"section": 0, "kind": card.kind, "prompt": field("prompt"), "explanation": field("explanation")}
    if card.kind == "flashcard":
        raw.update(options=[], answers=[field("answer", 600)])
    elif card.kind in ("multiple_choice", "odd_one_out"):
        options = lines("options")
        correct = clean_int(form.get(f"{prefix}-correct"), 0)
        raw.update(options=options, answers=[options[correct]] if 0 <= correct < len(options) else [])
    elif card.kind == "true_false":
        raw.update(options=[], answers=[field("answer", 10)])
    elif card.kind in ("fill_blank", "short_answer"):
        raw.update(options=[], answers=lines("answers"))
    elif card.kind == "ordering":
        raw.update(options=lines("options"), answers=[])
    elif card.kind in ("matching", "categorize"):
        pairs = [line.split("=", 1) for line in lines("pairs") if "=" in line]
        raw.update(options=[a.strip() for a, _ in pairs], answers=[b.strip() for _, b in pairs])
    elif card.kind == "multi_select":
        items = lines("options")
        raw.update(options=[i.lstrip("*").strip() for i in items],
                   answers=[i.lstrip("*").strip() for i in items if i.startswith("*")])
    elif card.kind == "numeric":
        raw.update(options=[], answers=[field("number", 40)] + ([field("unit", 30)] if field("unit", 30) else []))
    elif card.kind == "explain":
        raw.update(options=[], answers=lines("answers"))
    cleaned = clean_card(raw, 1)
    if cleaned is None:
        return False
    card.prompt = cleaned["prompt"]
    card.options = cleaned["options"]
    card.answers = cleaned["answers"]
    card.explanation = cleaned["explanation"]
    return True


def record_attempt(study_set: StudySet, results: list[dict]) -> Attempt:
    """Store a finished quiz. `results` = [{"card_id": int, "correct": bool}]."""
    cards = {c.id: c for c in study_set.cards}
    counted = {}
    for r in results or []:
        card_id = clean_int(r.get("card_id"))
        if card_id in cards and cards[card_id].kind != "flashcard":
            counted[card_id] = bool(r.get("correct"))
    total = len(counted) or len(study_set.quiz_cards) or 1
    correct = sum(1 for v in counted.values() if v)
    score = round(correct / total * 100, 1)

    for card_id, was_correct in counted.items():
        card = cards[card_id]
        card.times_seen += 1
        card.times_correct += int(was_correct)

    # Skips and "I was right" overrides per question type, for the owner's stats.
    from ..models import SiteEvent
    for r in results or []:
        card = cards.get(clean_int(r.get("card_id")))
        if card is None or card.kind == "flashcard":
            continue
        for flag, kind in (("skipped", "q_skip"), ("overridden", "q_override")):
            if r.get(flag):
                db.session.add(SiteEvent(kind=kind, user_id=study_set.user_id, detail=card.kind))

    attempt = Attempt(study_set=study_set, score=score, correct=correct, total=total)
    db.session.add(attempt)
    study_set.last_score = score
    study_set.best_score = max(score, study_set.best_score or 0)
    study_set.last_studied_at = utcnow()
    db.session.flush()
    return attempt


# --- Spaced repetition (simplified SM-2) -------------------------------------

GRADES = {"again": 0, "hard": 1, "good": 2, "easy": 3}


def review_card(card: Card, grade: str) -> None:
    g = GRADES.get(grade, 2)
    now = utcnow()
    if g == 0:
        card.lapses += 1
        card.reps = 0
        card.interval_days = 0
        card.ease = max(1.3, card.ease - 0.2)
        card.due_at = now + timedelta(minutes=1)
    else:
        if card.reps == 0:
            interval = {1: 0.5, 2: 1, 3: 3}[g]
        elif card.reps == 1:
            interval = {1: 2, 2: 3, 3: 6}[g]
        else:
            factor = {1: 1.2, 2: card.ease, 3: card.ease * 1.3}[g]
            interval = max(card.interval_days + 1, card.interval_days * factor)
        card.ease = max(1.3, card.ease + {1: -0.15, 2: 0.0, 3: 0.15}[g])
        card.reps += 1
        card.interval_days = round(interval, 2)
        card.due_at = now + timedelta(days=interval)
    card.times_seen += 1
    card.times_correct += int(g > 0)
    if card.study_set:
        card.study_set.last_studied_at = now
