"""Signed-in pages: library, set overview, notes editor, quiz, flashcards, settings."""
from __future__ import annotations

import json

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user

from ..extensions import db
from ..models import QUIZ_KINDS, StudySet, get_owned_set, subjects_for, utcnow
from ..sanitize import clean_text
from ..services.study import update_card_from_form

study_bp = Blueprint("study", __name__)


@study_bp.before_request
@login_required
def require_login():
    """Every page in this blueprint needs a signed-in user."""
    return None


@study_bp.after_request
def no_index(response):
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@study_bp.route("/library")
def library():
    sets = (
        StudySet.query.filter_by(user_id=current_user.id)
        .order_by(StudySet.updated_at.desc())
        .all()
    )
    subjects = subjects_for(current_user)
    active = request.args.get("subject")
    if active not in subjects:
        active = None
    now = utcnow()
    due_total = sum(len(s.due_flashcards(now)) for s in sets)
    return render_template(
        "app/library.html", sets=sets, subjects=subjects, active_subject=active, due_total=due_total,
    )


@study_bp.route("/new")
def new_set():
    return render_template("app/new.html", subjects=subjects_for(current_user))


@study_bp.route("/sets/<int:set_id>")
def study_set(set_id: int):
    s = get_owned_set(set_id, current_user)
    siblings = (
        StudySet.query.filter_by(user_id=current_user.id, subject=s.subject)
        .order_by(StudySet.created_at.asc())
        .all()
    )
    return render_template(
        "app/set.html", s=s, siblings=siblings, due=len(s.due_flashcards()),
        attempts=s.attempts[:8],
    )


@study_bp.route("/sets/<int:set_id>/notes")
def edit_notes(set_id: int):
    s = get_owned_set(set_id, current_user)
    return render_template(
        "app/notes.html", s=s, subjects=subjects_for(current_user), kinds=QUIZ_KINDS,
        notes_json=[sec.to_dict() for sec in s.sections],
    )


@study_bp.route("/sets/<int:set_id>/quiz")
def quiz(set_id: int):
    s = get_owned_set(set_id, current_user)
    if not s.has_quiz:
        flash("Generate a quiz for these notes first.", "info")
        return redirect(url_for("study.edit_notes", set_id=s.id))
    only_missed = request.args.get("mode") == "missed"
    payload = build_quiz_payload(s.to_dict(), only_ids=_ids(request.args.get("ids")) if only_missed else None)
    payload["submit_url"] = url_for("api.submit_attempt", set_id=s.id)
    payload["set_url"] = url_for("study.study_set", set_id=s.id)
    payload["retry_url"] = url_for("study.quiz", set_id=s.id)
    return render_template("app/quiz.html", s=s, payload=payload)


@study_bp.route("/sets/<int:set_id>/flashcards")
def flashcards(set_id: int):
    s = get_owned_set(set_id, current_user)
    mode = request.args.get("mode", "due")
    cards = s.due_flashcards() if mode == "due" else s.flashcards
    if mode == "due" and not cards:
        mode, cards = "all", s.flashcards
    payload = {
        "title": s.title,
        "mode": mode,
        "set_url": url_for("study.study_set", set_id=s.id),
        "review_url": "/api/cards/{id}/review",
        "cards": [{"id": c.id, "front": c.prompt, "back": (c.answers or [""])[0]} for c in cards],
    }
    return render_template("app/flashcards.html", s=s, payload=payload, mode=mode)


@study_bp.route("/sets/<int:set_id>/cards", methods=["GET", "POST"])
def edit_cards(set_id: int):
    s = get_owned_set(set_id, current_user)
    if request.method == "POST":
        action = request.form.get("action", "save")
        invalid = 0
        for card in list(s.cards):
            prefix = f"c{card.id}"
            if request.form.get(f"{prefix}-delete") == "1":
                s.cards.remove(card)
                db.session.delete(card)
                continue
            if f"{prefix}-prompt" in request.form and not update_card_from_form(card, request.form, prefix):
                invalid += 1
        if action == "add_flashcard":
            front = clean_text(request.form.get("new-front"), 1000)
            back = clean_text(request.form.get("new-back"), 600)
            if front and back:
                from ..models import Card

                s.cards.append(Card(kind="flashcard", prompt=front, answers=[back], options=[],
                                    position=len(s.cards)))
        s.updated_at = utcnow()
        db.session.commit()
        if invalid:
            flash(f"{invalid} card(s) had a missing answer and weren't changed.", "error")
        else:
            flash("Cards saved.", "success")
        return redirect(url_for("study.edit_cards", set_id=s.id, tab=request.form.get("tab", "quiz")))
    tab = request.args.get("tab", "quiz")
    return render_template("app/cards.html", s=s, tab=tab)


@study_bp.route("/sets/<int:set_id>/rename", methods=["POST"])
def rename_set(set_id: int):
    s = get_owned_set(set_id, current_user)
    s.title = clean_text(request.form.get("title"), 200) or s.title
    s.subject = clean_text(request.form.get("subject"), 120) or s.subject
    db.session.commit()
    return redirect(url_for("study.study_set", set_id=s.id))


@study_bp.route("/sets/<int:set_id>/delete", methods=["POST"])
def delete_set(set_id: int):
    s = get_owned_set(set_id, current_user)
    subject = s.subject
    db.session.delete(s)
    db.session.commit()
    flash("Deleted.", "success")
    still_has = StudySet.query.filter_by(user_id=current_user.id, subject=subject).first()
    return redirect(url_for("study.library", subject=subject if still_has else None))


@study_bp.route("/settings")
def settings():
    return render_template("app/settings.html", set_count=current_user.sets.count())


@study_bp.route("/settings/export")
def export_data():
    data = {
        "exported_at": utcnow().isoformat() + "Z",
        "account": {"email": current_user.email, "name": current_user.name,
                    "created_at": current_user.created_at.isoformat()},
        "sets": [s.to_dict() for s in current_user.sets.order_by(StudySet.created_at).all()],
    }
    return Response(
        json.dumps(data, indent=2, ensure_ascii=False),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=quizlynotes-export.json"},
    )


@study_bp.route("/settings/delete", methods=["POST"])
def delete_account():
    if request.form.get("confirm", "").strip().lower() != "delete":
        flash("Type DELETE to confirm.", "error")
        return redirect(url_for("study.settings"))
    user = current_user._get_current_object()
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash("Your account and all your data have been deleted.", "success")
    return redirect(url_for("public.home"))


def _ids(raw: str | None) -> set[int] | None:
    if not raw:
        return None
    out = set()
    for part in raw.split(","):
        if part.strip().isdigit():
            out.add(int(part))
    return out or None


def build_quiz_payload(data: dict, only_ids: set[int] | None = None) -> dict:
    """Group notes and questions by heading for the quiz player.

    The player shows the notes for a topic, then the questions on it.
    """
    sections = data.get("sections", [])
    index_by_id = {s.get("id"): i for i, s in enumerate(sections)}
    groups: list[dict] = []
    group_of_section: dict[int, int] = {}
    for i, sec in enumerate(sections):
        if not groups or groups[-1]["heading"] != sec["heading"]:
            groups.append({"heading": sec["heading"], "notes": [], "cards": []})
        groups[-1]["notes"].append({"subheading": sec["subheading"], "points": sec["points"]})
        group_of_section[i] = len(groups) - 1

    for n, card in enumerate(data.get("cards", [])):
        if card["kind"] == "flashcard":
            continue
        if only_ids is not None and card.get("id") not in only_ids:
            continue
        sec_index = card.get("section")
        if sec_index is None:
            sec_index = index_by_id.get(card.get("section_id"), 0)
        g = group_of_section.get(sec_index, 0)
        if not groups:
            groups.append({"heading": data.get("title", "Quiz"), "notes": [], "cards": []})
        c = dict(card)
        c.setdefault("id", f"g{n}")
        groups[g]["cards"].append(c)

    if only_ids is not None:
        groups = [g for g in groups if g["cards"]]
        for g in groups:
            g["notes"] = []
    return {"title": data.get("title", ""), "groups": groups}
