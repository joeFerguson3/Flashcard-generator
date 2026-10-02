"""Public pages: landing pages, legal, SEO files, guest demo, legacy redirects."""
from __future__ import annotations

from datetime import date, timedelta

from flask import (Blueprint, Response, abort, current_app, jsonify, redirect,
                   render_template, request, session, url_for)

from .. import seo
from ..ai import AIError, SourceError, get_provider
from ..extensions import db, limiter
from ..models import GuestDraft, utcnow

public_bp = Blueprint("public", __name__)

# Update when page copy changes meaningfully (used in sitemap lastmod).
CONTENT_UPDATED = date(2026, 10, 2)


@public_bp.route("/")
def home():
    return render_template(
        "public/home.html", faq=seo.HOME_FAQ, question_types=seo.QUESTION_TYPES,
        related=seo.RELATED_LINKS, pages=seo.LANDING_PAGES,
    )


def _landing(slug: str):
    page = seo.LANDING_PAGES[slug]
    return render_template(
        "public/landing.html", page=page, slug=slug, question_types=seo.QUESTION_TYPES,
        related=[r for r in seo.RELATED_LINKS if r[0] != slug], pages=seo.LANDING_PAGES,
    )


@public_bp.route("/notes-to-quiz")
def notes_to_quiz():
    return _landing("notes-to-quiz")


@public_bp.route("/pdf-to-quiz")
def pdf_to_quiz():
    return _landing("pdf-to-quiz")


@public_bp.route("/notes-to-flashcards")
def notes_to_flashcards():
    return _landing("notes-to-flashcards")


@public_bp.route("/privacy")
def privacy():
    return render_template("public/privacy.html")


@public_bp.route("/terms")
def terms():
    return render_template("public/terms.html")


@public_bp.route("/healthz")
def healthz():
    return {"ok": True}


@public_bp.route("/robots.txt")
def robots():
    site = current_app.config["SITE_URL"]
    body = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Disallow: /api/",
        "Disallow: /library",
        "Disallow: /new",
        "Disallow: /sets/",
        "Disallow: /settings",
        "Disallow: /try/",
        "Disallow: /login",
        "",
        f"Sitemap: {site}/sitemap.xml",
        "",
    ])
    return Response(body, mimetype="text/plain")


@public_bp.route("/sitemap.xml")
def sitemap():
    site = current_app.config["SITE_URL"]
    urls = [("/", "1.0"), ("/notes-to-quiz", "0.9"), ("/pdf-to-quiz", "0.9"),
            ("/notes-to-flashcards", "0.9"), ("/privacy", "0.2"), ("/terms", "0.2")]
    items = "".join(
        f"<url><loc>{site}{path}</loc><lastmod>{CONTENT_UPDATED.isoformat()}</lastmod>"
        f"<priority>{priority}</priority></url>"
        for path, priority in urls
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + items + "</urlset>")
    return Response(xml, mimetype="application/xml")


@public_bp.route("/site.webmanifest")
def manifest():
    return jsonify({
        "name": "QuizlyNotes",
        "short_name": "QuizlyNotes",
        "start_url": "/library",
        "display": "standalone",
        "background_color": "#f6f3ea",
        "theme_color": "#1d1b16",
        "icons": [
            {"src": url_for("static", filename="img/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": url_for("static", filename="img/icon-512.png"), "sizes": "512x512", "type": "image/png"},
        ],
    })


# --- Guest demo -------------------------------------------------------------

def _guest_limit():
    return current_app.config["GUEST_LIMIT"]


@public_bp.route("/try", methods=["POST"])
@limiter.limit(_guest_limit)
def try_it():
    """Generate a short quiz from pasted text without an account."""
    if not current_app.config["ENABLE_GUEST_DEMO"]:
        abort(404)
    payload = request.get_json(silent=True) or request.form
    text = (payload.get("text") or "").strip()
    max_chars = current_app.config["GUEST_DEMO_MAX_CHARS"]
    if len(text) < 150:
        return jsonify(error="Paste at least a paragraph of notes (150+ characters)."), 400
    if len(text) > max_chars:
        return jsonify(error=f"The free try is limited to {max_chars:,} characters. Sign in to use longer notes or upload files."), 400
    try:
        data = get_provider().quick_study(text)
    except (AIError, SourceError) as exc:
        return jsonify(error=str(exc)), 502
    # Drafts nobody claimed within two days are discarded.
    cutoff = utcnow() - timedelta(days=2)
    GuestDraft.query.filter(GuestDraft.created_at < cutoff).delete()
    draft = GuestDraft(payload=data)
    db.session.add(draft)
    db.session.commit()
    session["guest_draft"] = draft.id
    return jsonify(redirect=url_for("public.try_result", draft_id=draft.id))


@public_bp.route("/try/<draft_id>")
def try_result(draft_id: str):
    draft = db.session.get(GuestDraft, draft_id)
    if draft is None or session.get("guest_draft") != draft_id:
        abort(404)
    from .study import build_quiz_payload

    payload = build_quiz_payload(draft.payload)
    payload["submit_url"] = None
    payload["guest"] = True
    flashcards = [c for c in draft.payload.get("cards", []) if c["kind"] == "flashcard"]
    response = current_app.make_response(render_template(
        "public/try.html", payload=payload, data=draft.payload, flashcards=flashcards,
    ))
    response.headers["X-Robots-Tag"] = "noindex"
    return response


# --- Old URLs from v1 -------------------------------------------------------

LEGACY = {
    "/home": "study.library",
    "/upload": "study.new_set",
    "/sets": "study.library",
    "/quiz-sets": "study.library",
    "/quiz": "study.library",
    "/notes": "study.library",
    "/edit-notes": "study.library",
}


def _legacy_redirect():
    target = LEGACY.get(request.path)
    if target is None:
        abort(404)
    return redirect(url_for(target), code=301)


for _path in LEGACY:
    public_bp.add_url_rule(_path, f"legacy{_path.replace('/', '_').replace('-', '_')}", _legacy_redirect)
