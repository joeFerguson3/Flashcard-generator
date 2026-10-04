"""JSON endpoints used by the front-end."""
from __future__ import annotations

import logging

from flask import Blueprint, current_app, jsonify, request, url_for
from flask_login import current_user, login_required

from .. import billing
from ..ai import AIError, PlanLimitError, SourceError, from_text, from_upload, get_provider, plan_counts
from ..extensions import db, limiter
from ..models import QUIZ_KINDS, Card, StudySet, get_owned_set
from ..sanitize import clean_int, clean_text
from ..services.study import create_set, record_attempt, replace_cards, review_card, save_sections

log = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _generation_limit():
    return current_app.config["GENERATION_LIMIT"]


def error(message: str, status: int = 400):
    return jsonify(error=message), status


@api_bp.errorhandler(AIError)
def handle_ai_error(exc):
    db.session.rollback()
    return error(str(exc), 502)


@api_bp.errorhandler(SourceError)
def handle_source_error(exc):
    if isinstance(exc, PlanLimitError):
        return jsonify(error=str(exc), upgrade=True, feature="file_size",
                       upgrade_url=url_for("billing.pricing", feature="file_size")), 402
    return error(str(exc), 400)


@api_bp.errorhandler(billing.LimitReached)
def handle_limit(exc):
    db.session.rollback()
    return jsonify(error=exc.message, upgrade=True, feature=exc.feature,
                   upgrade_url=url_for("billing.pricing", feature=exc.feature)), 402


def _quiz_options(payload: dict) -> tuple[int | None, list[str], str]:
    count = clean_int(payload.get("count"))
    count = min(max(count, 3), 60) if count else None
    kinds = [k for k in (payload.get("kinds") or []) if k in QUIZ_KINDS] or list(QUIZ_KINDS)
    difficulty = payload.get("difficulty") if payload.get("difficulty") in ("easy", "medium", "hard") else "medium"
    return count, kinds, difficulty


def _generate_cards(study_set: StudySet, payload: dict) -> None:
    sections = [s.to_dict() for s in study_set.sections]
    if not sections:
        raise SourceError("Add some notes before generating a quiz.")
    count, kinds, difficulty = _quiz_options(payload)
    limit = billing.limits_for(current_user).max_questions
    quiz_count, flash_count = plan_counts(sections, count)
    quiz_count = min(quiz_count, limit)
    cards = get_provider().make_cards(sections, quiz_count, flash_count, kinds, difficulty)
    replace_cards(study_set, cards)
    study_set.generations = (study_set.generations or 0) + 1
    billing.record(current_user, "quiz")


@api_bp.post("/sets")
@login_required
@limiter.limit(_generation_limit)
def create_study_set():
    """Upload a file (or paste text) -> notes, optionally straight to a quiz."""
    form = request.form
    billing.check_new_set(current_user)
    lim = billing.limits_for(current_user)
    if request.files.get("file") and request.files["file"].filename:
        source = from_upload(request.files["file"], max_pages=lim.max_pages, max_mb=lim.max_upload_mb,
                             max_chars=lim.max_text_chars, pro=billing.is_pro(current_user))
    else:
        source = from_text(form.get("text", ""), max_chars=lim.max_text_chars)

    notes = get_provider().make_notes(source)
    study_set = create_set(
        current_user, notes,
        title=form.get("title", ""), subject=form.get("subject", ""),
        source_name=source.name,
    )
    billing.record(current_user, "new_set")
    billing.reward_referrer(current_user)
    db.session.commit()  # keep the notes even if quiz generation fails

    if form.get("skip_review") == "1":
        try:
            _generate_cards(study_set, {"count": form.get("count"), "difficulty": form.get("difficulty")})
            db.session.commit()
            return jsonify(redirect=url_for("study.study_set", set_id=study_set.id))
        except AIError:
            db.session.rollback()
    return jsonify(redirect=url_for("study.edit_notes", set_id=study_set.id))


@api_bp.put("/sets/<int:set_id>/notes")
@login_required
def update_notes(set_id: int):
    study_set = get_owned_set(set_id, current_user)
    payload = request.get_json(silent=True) or {}
    if "title" in payload:
        study_set.title = clean_text(payload["title"], 200) or study_set.title
    if "subject" in payload:
        study_set.subject = clean_text(payload["subject"], 120) or study_set.subject
    if isinstance(payload.get("sections"), list):
        save_sections(study_set, payload["sections"])
    db.session.commit()
    return jsonify(ok=True, sections=[s.to_dict() for s in study_set.sections])


@api_bp.post("/sets/<int:set_id>/generate")
@login_required
@limiter.limit(_generation_limit)
def generate_quiz(set_id: int):
    study_set = get_owned_set(set_id, current_user)
    payload = request.get_json(silent=True) or {}
    billing.check_regenerate(current_user, study_set)
    if isinstance(payload.get("sections"), list):
        save_sections(study_set, payload["sections"])
        db.session.commit()
    _generate_cards(study_set, payload)
    db.session.commit()
    return jsonify(redirect=url_for("study.study_set", set_id=study_set.id))


@api_bp.post("/sets/<int:set_id>/enhance")
@login_required
@limiter.limit(_generation_limit)
def enhance(set_id: int):
    get_owned_set(set_id, current_user)
    payload = request.get_json(silent=True) or {}
    heading = clean_text(payload.get("heading"), 200)
    sections = payload.get("sections") or []
    if not sections:
        return error("Nothing to improve yet.")
    mode = "simplify" if payload.get("mode") == "simplify" else "improve"
    billing.check_ai_edit(current_user)
    improved = get_provider().enhance(heading, sections[:20], mode=mode)
    billing.record(current_user, "ai_edit")
    db.session.commit()
    return jsonify(sections=improved)


@api_bp.post("/sets/<int:set_id>/attempts")
@login_required
def submit_attempt(set_id: int):
    study_set = get_owned_set(set_id, current_user)
    payload = request.get_json(silent=True) or {}
    attempt = record_attempt(study_set, payload.get("results") or [])
    db.session.commit()

    next_set = (
        StudySet.query.filter(
            StudySet.user_id == current_user.id,
            StudySet.subject == study_set.subject,
            StudySet.id != study_set.id,
        )
        .order_by(StudySet.last_studied_at.is_(None).desc(), StudySet.last_studied_at.asc())
        .first()
    )
    return jsonify(
        score=attempt.score,
        best=study_set.best_score,
        next=({"title": next_set.title, "url": url_for("study.study_set", set_id=next_set.id)}
              if next_set else None),
    )


@api_bp.post("/cards/results")
@login_required
def card_results():
    """Results from a cross-set quiz (mock exam / weak spots)."""
    payload = request.get_json(silent=True) or {}
    results = payload.get("results") or []
    ids = [clean_int(r.get("card_id")) for r in results]
    cards = {c.id: c for c in Card.query.join(StudySet).filter(
        Card.id.in_([i for i in ids if i]), StudySet.user_id == current_user.id).all()}
    correct = 0
    for r in results:
        card = cards.get(clean_int(r.get("card_id")))
        if card is None:
            continue
        card.times_seen += 1
        if r.get("correct"):
            card.times_correct += 1
            correct += 1
    db.session.commit()
    total = len([r for r in results if clean_int(r.get("card_id")) in cards]) or 1
    return jsonify(score=round(correct / total * 100, 1), best=None, next=None)


@api_bp.post("/cards/<int:card_id>/review")
@login_required
def review(card_id: int):
    card = db.session.get(Card, card_id)
    if card is None:
        return error("Not found.", 404)
    get_owned_set(card.set_id, current_user)
    review_card(card, (request.get_json(silent=True) or {}).get("grade", "good"))
    db.session.commit()
    return jsonify(ok=True, due_at=card.due_at.isoformat() if card.due_at else None)
