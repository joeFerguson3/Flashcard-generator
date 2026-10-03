"""Database models.

One StudySet holds everything generated from a single upload: the revision
notes (Sections) and the questions/flashcards (Cards). Every query that loads
a set goes through `get_owned_set`, so users can only ever touch their own data.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from flask import abort
from flask_login import UserMixin
from sqlalchemy import func

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


CARD_KINDS = (
    "flashcard",
    "multiple_choice",
    "true_false",
    "fill_blank",
    "short_answer",
    "ordering",
    "matching",
    "multi_select",
    "categorize",
    "numeric",
    "explain",
)
QUIZ_KINDS = tuple(k for k in CARD_KINDS if k != "flashcard")


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255))
    picture = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime, default=utcnow)

    sets = db.relationship(
        "StudySet", back_populates="owner", cascade="all, delete-orphan", lazy="dynamic"
    )

    @property
    def display_name(self) -> str:
        return (self.name or self.email.split("@")[0]).strip()

    @property
    def initial(self) -> str:
        return (self.display_name[:1] or "?").upper()


class StudySet(db.Model):
    __tablename__ = "study_set"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(120), nullable=False, default="General")
    source_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    last_studied_at = db.Column(db.DateTime)
    last_score = db.Column(db.Float)
    best_score = db.Column(db.Float)

    owner = db.relationship("User", back_populates="sets")
    sections = db.relationship(
        "Section", back_populates="study_set", cascade="all, delete-orphan",
        order_by="Section.position",
    )
    cards = db.relationship(
        "Card", back_populates="study_set", cascade="all, delete-orphan",
        order_by="Card.position",
    )
    attempts = db.relationship(
        "Attempt", back_populates="study_set", cascade="all, delete-orphan",
        order_by="Attempt.created_at.desc()",
    )

    @property
    def quiz_cards(self):
        return [c for c in self.cards if c.kind != "flashcard"]

    @property
    def flashcards(self):
        return [c for c in self.cards if c.kind == "flashcard"]

    @property
    def has_quiz(self) -> bool:
        return any(c.kind != "flashcard" for c in self.cards)

    def due_flashcards(self, now: datetime | None = None):
        now = now or utcnow()
        return [c for c in self.flashcards if c.due_at is None or c.due_at <= now]

    def heading_groups(self):
        """Sections grouped by heading, preserving order."""
        groups: list[dict] = []
        for section in self.sections:
            if not groups or groups[-1]["heading"] != section.heading:
                groups.append({"heading": section.heading, "sections": []})
            groups[-1]["sections"].append(section)
        return groups

    def to_dict(self, include_cards: bool = True) -> dict:
        data = {
            "id": self.id,
            "title": self.title,
            "subject": self.subject,
            "source_name": self.source_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "best_score": self.best_score,
            "last_score": self.last_score,
            "sections": [s.to_dict() for s in self.sections],
        }
        if include_cards:
            data["cards"] = [c.to_dict() for c in self.cards]
        return data


class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    set_id = db.Column(db.Integer, db.ForeignKey("study_set.id", ondelete="CASCADE"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    heading = db.Column(db.String(255), nullable=False, default="")
    subheading = db.Column(db.String(255), nullable=False, default="")
    # [{"text": "...", "level": 1..3}]
    points = db.Column(db.JSON, nullable=False, default=list)

    study_set = db.relationship("StudySet", back_populates="sections")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "heading": self.heading,
            "subheading": self.subheading,
            "points": self.points or [],
        }


class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    set_id = db.Column(db.Integer, db.ForeignKey("study_set.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = db.Column(db.Integer, db.ForeignKey("section.id", ondelete="SET NULL"), nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    kind = db.Column(db.String(32), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    options = db.Column(db.JSON, nullable=False, default=list)
    answers = db.Column(db.JSON, nullable=False, default=list)
    explanation = db.Column(db.Text, nullable=False, default="")

    # Spaced repetition state (simplified SM-2)
    due_at = db.Column(db.DateTime)
    interval_days = db.Column(db.Float, nullable=False, default=0)
    ease = db.Column(db.Float, nullable=False, default=2.5)
    reps = db.Column(db.Integer, nullable=False, default=0)
    lapses = db.Column(db.Integer, nullable=False, default=0)
    times_seen = db.Column(db.Integer, nullable=False, default=0)
    times_correct = db.Column(db.Integer, nullable=False, default=0)

    study_set = db.relationship("StudySet", back_populates="cards")
    section = db.relationship("Section")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "section_id": self.section_id,
            "kind": self.kind,
            "prompt": self.prompt,
            "options": self.options or [],
            "answers": self.answers or [],
            "explanation": self.explanation or "",
        }


class Attempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    set_id = db.Column(db.Integer, db.ForeignKey("study_set.id", ondelete="CASCADE"), nullable=False, index=True)
    score = db.Column(db.Float, nullable=False)
    correct = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    study_set = db.relationship("StudySet", back_populates="attempts")


class GuestDraft(db.Model):
    """A quiz generated from the public demo box, claimable after sign-in."""

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payload = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


def get_owned_set(set_id: int, user) -> StudySet:
    study_set = db.session.get(StudySet, set_id)
    if study_set is None or study_set.user_id != user.id:
        abort(404)
    return study_set


def subjects_for(user) -> list[str]:
    rows = (
        db.session.query(StudySet.subject, func.max(StudySet.updated_at))
        .filter(StudySet.user_id == user.id)
        .group_by(StudySet.subject)
        .order_by(func.max(StudySet.updated_at).desc())
        .all()
    )
    return [r[0] for r in rows]
