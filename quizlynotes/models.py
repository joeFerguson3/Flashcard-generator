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
    "odd_one_out",
    "explain",  # legacy, self-marked: no longer generated or shown in quizzes
)
QUIZ_KINDS = tuple(k for k in CARD_KINDS if k not in ("flashcard", "explain"))


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255))
    picture = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime, default=utcnow)

    # Billing / entitlements. Pro access = lifetime_pro, or pro_until in the future
    # (covers the signup trial, referral bonuses, promo codes and paid periods).
    pro_until = db.Column(db.DateTime)
    lifetime_pro = db.Column(db.Boolean, nullable=False, default=False)
    stripe_customer_id = db.Column(db.String(64), index=True)
    stripe_subscription_id = db.Column(db.String(64))
    subscription_status = db.Column(db.String(32))
    subscription_interval = db.Column(db.String(16))
    trial_started_at = db.Column(db.DateTime)
    # Referrals
    referral_code = db.Column(db.String(16), unique=True, index=True)
    referred_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    referral_rewarded = db.Column(db.Boolean, nullable=False, default=False)
    # How this person found the site (first visit in the session they signed up in).
    signup_source = db.Column(db.String(60))
    signup_landing = db.Column(db.String(200))
    signup_device = db.Column(db.String(10))
    signup_sid = db.Column(db.String(16))

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
    generations = db.Column(db.Integer, nullable=False, default=0)
    share_token = db.Column(db.String(32), unique=True, index=True)

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
        return [c for c in self.cards if c.kind not in ("flashcard", "explain")]

    @property
    def flashcards(self):
        return [c for c in self.cards if c.kind == "flashcard"]

    @property
    def has_quiz(self) -> bool:
        return any(c.kind not in ("flashcard", "explain") for c in self.cards)

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


class SiteEvent(db.Model):
    """Anonymous-friendly analytics event for the owner's stats page.

    kinds: "landing" (first page of a visit), "demo" (try-it used), "share_open",
    "error_upload", "error_ai", "error_demo", "q_skip", "q_override".
    `sid` is a random per-browser-session id, never linked to anything else.
    """

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    sid = db.Column(db.String(16))
    source = db.Column(db.String(60))
    path = db.Column(db.String(200))
    device = db.Column(db.String(10))
    detail = db.Column(db.String(200))

    __table_args__ = (db.Index("ix_site_event_kind_time", "kind", "created_at"),)


class UsageEvent(db.Model):
    """One AI action (new set, quiz generation, note edit) for monthly limits."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    kind = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    __table_args__ = (db.Index("ix_usage_user_kind_time", "user_id", "kind", "created_at"),)


class PromoCode(db.Model):
    """Redeemable code granting Pro. Only a hash of the code is stored."""

    id = db.Column(db.Integer, primary_key=True)
    code_hash = db.Column(db.String(64), unique=True, nullable=False)
    label = db.Column(db.String(120), nullable=False, default="")
    days = db.Column(db.Integer)  # None = lifetime
    max_redemptions = db.Column(db.Integer)  # None = unlimited
    redemptions = db.Column(db.Integer, nullable=False, default=0)
    expires_at = db.Column(db.DateTime)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class PromoRedemption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code_id = db.Column(db.Integer, db.ForeignKey("promo_code.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint("code_id", "user_id", name="uq_promo_user"),)


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
