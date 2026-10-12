"""Owner-only statistics page at /admin/stats (ADMIN_EMAILS)."""
from __future__ import annotations

from flask import Blueprint, abort, current_app, render_template, request
from flask_login import current_user, login_required

from .. import billing
from ..activity import build_stats

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.app_context_processor
def inject_admin():
    try:
        return {"is_admin": bool(current_user and current_user.is_authenticated and billing.is_admin(current_user))}
    except Exception:
        return {"is_admin": False}


@admin_bp.before_request
@login_required
def only_admins():
    if not billing.is_admin(current_user):
        abort(404)


@admin_bp.after_request
def no_index(response):
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Cache-Control"] = "no-store"
    return response


@admin_bp.route("/stats")
def stats():
    include_me = request.args.get("me") == "1"
    exclude = set() if include_me else set(current_app.config["ADMIN_EMAILS"])
    days = 90 if request.args.get("range") == "90" else 30
    return render_template("admin/stats.html", s=build_stats(exclude, days=days), include_me=include_me, days=days)


@admin_bp.route("/sets/<int:set_id>")
def set_preview(set_id: int):
    from ..models import Attempt, StudySet

    s = StudySet.query.get_or_404(set_id)
    attempts = Attempt.query.filter_by(set_id=s.id).order_by(Attempt.created_at.desc()).all()
    return render_template("admin/set.html", s=s, owner=s.owner, attempts=attempts)


@admin_bp.route("/users/<int:user_id>")
def user_detail(user_id: int):
    from ..activity import set_rows
    from ..models import Attempt, StudySet, User

    u = User.query.get_or_404(user_id)
    sets = StudySet.query.filter_by(user_id=u.id).all()
    ids = [x.id for x in sets]
    attempts = Attempt.query.filter(Attempt.set_id.in_(ids)).order_by(Attempt.created_at.desc()).all() if ids else []
    titles = {x.id: x.title for x in sets}
    return render_template("admin/user.html", u=u, rows=set_rows(sets, attempts, {u.id: u.email}),
                           attempts=attempts[:50], titles=titles)


@admin_bp.app_template_filter("uk")
def uk_time(dt, fmt="%a %-d %b, %H:%M"):
    from datetime import timezone

    from ..activity import LOCAL_TZ

    if dt is None:
        return "–"
    return dt.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ).strftime(fmt)
