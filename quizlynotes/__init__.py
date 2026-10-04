"""QuizlyNotes: turn notes into quizzes and flashcards."""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import csrf, db, limiter, login_manager, migrate
from .models import utcnow

load_dotenv()


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or Config)
    os.makedirs(app.instance_path, exist_ok=True)

    logging.basicConfig(level=logging.INFO)

    if not app.config.get("SECRET_KEY"):
        if app.config["IS_PRODUCTION"]:
            raise RuntimeError("FLASK_SECRET_KEY must be set in production.")
        app.config["SECRET_KEY"] = "dev-only-secret"

    # Cloud Run sits behind Google's proxy; trust its forwarded headers.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    if not app.config["IS_PRODUCTION"]:
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
    # Google returns scopes in a different form than requested.
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = None

    try:
        from flask_compress import Compress

        Compress(app)
    except ImportError:  # pragma: no cover
        pass

    from .auth import auth_bp, register_google
    from .views.api import api_bp
    from .views.billing import billing_bp
    from .views.public import public_bp
    from .views.study import study_bp

    register_google(app)
    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(study_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(billing_bp)

    _register_template_helpers(app)
    _register_error_handlers(app)
    _register_security_headers(app)
    _register_cli(app)

    with app.app_context():
        # Safe and idempotent; migrations (flask db upgrade) handle later changes.
        uri = app.config["SQLALCHEMY_DATABASE_URI"]
        if app.config.get("TESTING") or (uri.startswith("sqlite") and not os.getenv("SKIP_CREATE_ALL")):
            db.create_all()

    return app


def _register_template_helpers(app: Flask) -> None:
    hashes: dict[str, str] = {}

    def asset(filename: str) -> str:
        """Static URL with a content hash, so files can be cached for a year."""
        if filename not in hashes or app.debug:
            path = os.path.join(app.static_folder, filename)
            try:
                with open(path, "rb") as fh:
                    hashes[filename] = hashlib.md5(fh.read()).hexdigest()[:10]
            except OSError:
                hashes[filename] = "0"
        return url_for("static", filename=filename, v=hashes[filename])

    def absolute_url(endpoint: str, **values) -> str:
        return app.config["SITE_URL"] + url_for(endpoint, **values)

    @app.context_processor
    def inject_plan():
        from flask_login import current_user

        from . import billing

        if current_user and current_user.is_authenticated:
            return {"plan": billing.plan_status(current_user)}
        return {"plan": None}

    @app.context_processor
    def inject_globals():
        return {
            "asset": asset,
            "absolute_url": absolute_url,
            "site": {
                "name": app.config["SITE_NAME"],
                "url": app.config["SITE_URL"],
                "email": app.config["CONTACT_EMAIL"],
                "year": datetime.now().year,
                "guest_demo": app.config["ENABLE_GUEST_DEMO"],
                "dev_login": app.config["ENABLE_DEV_LOGIN"],
                "monetisation": app.config.get("MONETISATION_ENABLED", True),
            },
        }

    @app.template_filter("note_chunks")
    def note_chunks(points):
        """Group points like the quiz notes: a level-1 lead, level-2 items, level-3 details."""
        chunks = []
        for p in points or []:
            level = int(p.get("level") or 1)
            if level == 1 or not chunks:
                chunks.append({"lead": p if level == 1 else None, "items": []})
                if level == 1:
                    continue
            chunk = chunks[-1]
            if level == 2 or not chunk["items"]:
                chunk["items"].append({"point": p, "subs": []})
            else:
                chunk["items"][-1]["subs"].append(p)
        return chunks

    @app.template_filter("term")
    def term(text):
        """'Term: explanation' -> bold term, matching the quiz notes."""
        from markupsafe import Markup, escape
        text = text or ""
        i = text.find(": ")
        if 0 < i < 48:
            return Markup("<strong>%s</strong>%s") % (escape(text[:i]), escape(text[i:]))
        return escape(text)

    @app.template_filter("pct")
    def pct(value):
        if value is None:
            return "–"
        return f"{round(value)}%"

    @app.template_filter("ago")
    def ago(value):
        if not value:
            return "never"
        delta = utcnow() - value
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            return f"{seconds // 60} min ago"
        if seconds < 86400:
            return f"{seconds // 3600} h ago"
        days = seconds // 86400
        if days == 1:
            return "yesterday"
        if days < 30:
            return f"{days} days ago"
        return value.strftime("%d %b %Y")


def _wants_json() -> bool:
    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


def _register_error_handlers(app: Flask) -> None:
    from flask_wtf.csrf import CSRFError

    @app.errorhandler(404)
    def not_found(_e):
        if _wants_json():
            return jsonify(error="Not found."), 404
        return render_template("public/error.html", code=404,
                               title="Page not found",
                               message="That page doesn't exist, or it isn't yours."), 404

    @app.errorhandler(413)
    def too_large(_e):
        mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        msg = f"That file is too large. The limit is {mb}MB."
        if _wants_json():
            return jsonify(error=msg), 413
        return render_template("public/error.html", code=413, title="File too large", message=msg), 413

    @app.errorhandler(429)
    def rate_limited(_e):
        msg = "You've hit the generation limit for now. Please wait a little and try again."
        if _wants_json():
            return jsonify(error=msg), 429
        return render_template("public/error.html", code=429, title="Slow down", message=msg), 429

    @app.errorhandler(CSRFError)
    def csrf_error(_e):
        msg = "Your session expired. Refresh the page and try again."
        if _wants_json():
            return jsonify(error=msg), 400
        return render_template("public/error.html", code=400, title="Session expired", message=msg), 400

    @app.errorhandler(500)
    def server_error(_e):
        db.session.rollback()
        if _wants_json():
            return jsonify(error="Something went wrong on our side. Please try again."), 500
        return render_template("public/error.html", code=500, title="Something went wrong",
                               message="Please try again in a moment."), 500


def _register_security_headers(app: Flask) -> None:
    @app.after_request
    def headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if app.config["IS_PRODUCTION"]:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.path.startswith("/static/"):
            if "v" in request.args:
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                response.headers["Cache-Control"] = "public, max-age=86400"
        return response


def _register_cli(app: Flask) -> None:
    import click

    @app.cli.command("promo")
    @click.argument("label")
    @click.option("--days", type=int, default=None, help="Days of Pro (omit for lifetime).")
    @click.option("--uses", type=int, default=None, help="Max redemptions (omit for unlimited).")
    @click.option("--code", default=None, help="Use this exact code instead of a random one.")
    def promo(label, days, uses, code):
        """Create a promo code, e.g. flask promo "Launch week" --days 30 --uses 100"""
        from . import billing

        _, plain = billing.create_promo(label, days=days, max_redemptions=uses, code=code)
        db.session.commit()
        print(f"Created code: {plain}  ({'lifetime' if days is None else f'{days} days'}, "
              f"{'unlimited' if uses is None else uses} uses)")

    @app.cli.command("create-db")
    def create_db():
        """Create all tables (first deploy without migrations)."""
        db.create_all()
        print("Tables created.")
