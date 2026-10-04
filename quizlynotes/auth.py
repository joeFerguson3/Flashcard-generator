"""Google sign-in (Flask-Dance) + Flask-Login sessions."""
from __future__ import annotations

from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, flash, redirect, request, session, url_for
from flask_dance.consumer import oauth_authorized, oauth_error
from flask_dance.contrib.google import make_google_blueprint
from flask_login import current_user, login_user, logout_user

from .extensions import db, login_manager
from .models import GuestDraft, User, utcnow
from .sanitize import clean_text

auth_bp = Blueprint("auth", __name__)


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith("/api/"):
        return {"error": "Please sign in again."}, 401
    return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))


def _safe_next(target: str | None) -> str | None:
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//"):
        return None
    return target


def register_google(app) -> None:
    google_bp = make_google_blueprint(
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        scope=["openid", "https://www.googleapis.com/auth/userinfo.email",
               "https://www.googleapis.com/auth/userinfo.profile"],
    )
    # Same URL as before (/login/google/authorized) so the existing OAuth
    # redirect URI in Google Cloud Console keeps working.
    app.register_blueprint(google_bp, url_prefix="/login")

    @oauth_authorized.connect_via(google_bp)
    def google_logged_in(blueprint, token):
        if not token:
            flash("Sign-in failed. Please try again.", "error")
            return redirect(url_for("public.home"))
        resp = blueprint.session.get("/oauth2/v2/userinfo")
        if not resp.ok:
            flash("We couldn't read your Google profile. Please try again.", "error")
            return redirect(url_for("public.home"))
        info = resp.json()
        email = (info.get("email") or "").lower()
        if not email or not info.get("verified_email", True):
            flash("Your Google account needs a verified email address.", "error")
            return redirect(url_for("public.home"))
        return _complete_login(email, info.get("name"), info.get("picture"))

    @oauth_error.connect_via(google_bp)
    def google_error(blueprint, message=None, response=None, **kwargs):
        flash("Sign-in was cancelled or failed.", "error")


def _complete_login(email: str, name: str | None, picture: str | None):
    from . import billing

    user = User.query.filter_by(email=email).first()
    is_new = user is None
    if is_new:
        user = User(email=email)
        db.session.add(user)
        ref = session.pop("ref", None)
        referrer = User.query.filter_by(referral_code=ref).first() if ref else None
        if referrer is not None:
            user.referred_by_id = referrer.id
    user.name = clean_text(name, 255) or user.name
    user.picture = clean_text(picture, 500) or user.picture
    user.last_login_at = utcnow()
    db.session.flush()
    billing.ensure_referral_code(user)
    # Reverse trial: every account starts with a week of Pro (existing users
    # get it once too, as a launch gift).
    billing.start_trial(user, referred=bool(user.referred_by_id) and is_new)
    db.session.commit()
    login_user(user, remember=True)

    target = _safe_next(session.pop("next", None))
    draft_id = session.pop("guest_draft", None)
    if draft_id:
        claimed = _claim_guest_draft(user, draft_id)
        if claimed:
            return redirect(url_for("study.study_set", set_id=claimed))
    # Returning a response tells Flask-Dance not to store the token.
    return redirect(target or url_for("study.library"))


def _claim_guest_draft(user, draft_id: str):
    from .services.study import create_set, replace_cards

    draft = db.session.get(GuestDraft, draft_id)
    if draft is None:
        return None
    payload = draft.payload
    study_set = create_set(user, payload, source_name="Quick try")
    replace_cards(study_set, payload.get("cards", []))
    db.session.delete(draft)
    db.session.commit()
    return study_set.id


@auth_bp.route("/login")
def login():
    if current_user.is_authenticated:
        return redirect(_safe_next(request.args.get("next")) or url_for("study.library"))
    session["next"] = _safe_next(request.args.get("next"))
    if not current_app.config.get("GOOGLE_CLIENT_ID") and current_app.config["ENABLE_DEV_LOGIN"]:
        return redirect(url_for("auth.dev_login"))
    return redirect(url_for("google.login"))


@auth_bp.route("/dev-login")
def dev_login():
    """Local development only: sign in without Google."""
    if not current_app.config["ENABLE_DEV_LOGIN"] or current_app.config["IS_PRODUCTION"]:
        abort(404)
    email = request.args.get("email", "dev@example.com")
    return _complete_login(email, "Dev Student", None)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    session.clear()
    # Keep Flask-Login's instruction to delete the remember-me cookie,
    # otherwise the user is silently logged back in on the next request.
    session["_remember"] = "clear"
    return redirect(url_for("public.home"))
