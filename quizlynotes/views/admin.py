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
