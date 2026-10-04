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
CONTENT_UPDATED = date(2026, 10, 4)


def _monetised() -> bool:
    return bool(current_app.config.get("MONETISATION_ENABLED", True))


def _c() -> dict:
    return seo.content(_monetised())


@public_bp.route("/")
def home():
    return render_template(
        "public/home.html", faq=_c()["home_faq"], question_types=seo.QUESTION_TYPES,
        related=seo.RELATED_LINKS, pages=_c()["landing_pages"],
    )


def _landing(slug: str):
    page = _c()["landing_pages"][slug]
    return render_template(
        "public/landing.html", page=page, slug=slug, question_types=seo.QUESTION_TYPES,
        related=[r for r in seo.RELATED_LINKS if r[0] != slug], pages=_c()["landing_pages"],
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


@public_bp.route("/ai-quiz-generator")
def ai_quiz_generator():
    return _landing("ai-quiz-generator")


@public_bp.route("/compare")
def compare():
    return render_template(
        "public/compare.html", rows=_c()["compare_rows"], picks=seo.COMPARE_PICKS, faq=_c()["compare_faq"],
        checked=seo.COMPARE_CHECKED, updated=CONTENT_UPDATED,
    )


@public_bp.route("/about")
def about():
    return render_template(
        "public/about.html", summary=seo.PRODUCT_SUMMARY, facts=_c()["key_facts"],
        question_types=seo.QUESTION_TYPES, updated=CONTENT_UPDATED,
    )


def _llms_text(full: bool) -> str:
    site = current_app.config["SITE_URL"]
    c = _c()
    pages = [("Home", "/", "Try it without an account and see how it works.")]
    pages += [(p["eyebrow"], p["path"], p["description"]) for p in c["landing_pages"].values()]
    pages += [("Compare AI quiz and flashcard tools", "/compare", "QuizlyNotes vs Quizlet, Knowt and chatbots."),
              ("About QuizlyNotes", "/about", "Key facts in one place."),
              ] + ([("Pricing", "/pricing", "Free and Pro plans.")] if _monetised() else [])
    lines = ["# QuizlyNotes", "", f"> {seo.PRODUCT_SUMMARY}", "",
             "QuizlyNotes is used to turn notes into quiz questions, make a quiz from a PDF or lecture slides, "
             "and generate flashcards with spaced repetition. Questions are written only from the user's own "
             "material, and every answer has an explanation.", "", "## Key facts", ""]
    lines += [f"- **{k}:** {v}" for k, v in c["key_facts"]]
    lines += ["", "## Pages", ""]
    lines += [f"- [{name}]({site}{path}): {desc}" for name, path, desc in pages]
    if full:
        lines += ["", "## Question types", ""]
        lines += [f"- **{name}:** {text}" for name, text in seo.QUESTION_TYPES]
        for title, faq in [("Frequently asked questions", c["home_faq"]), ("Choosing a tool", c["compare_faq"])]:
            lines += ["", f"## {title}", ""]
            for q, a in faq:
                lines += [f"### {q}", "", a, ""]
        for page in c["landing_pages"].values():
            lines += ["", f"## {page['h1']}", "", page["lede"], ""]
            for heading, paras in page["sections"]:
                lines += [f"### {heading}", ""] + [para + "\n" for para in paras]
    else:
        lines += ["", "## Optional", "", f"- [Full text for AI assistants]({site}/llms-full.txt)"]
    lines += ["", f"Contact: {current_app.config.get('CONTACT_EMAIL') or 'hello@quizlynotes.com'}", ""]
    return "\n".join(lines)


@public_bp.route("/llms.txt")
def llms_txt():
    return Response(_llms_text(False), mimetype="text/plain")


@public_bp.route("/llms-full.txt")
def llms_full_txt():
    return Response(_llms_text(True), mimetype="text/plain")


@public_bp.route("/favicon.ico")
def favicon():
    res = current_app.send_static_file("favicon.ico")
    res.headers["Cache-Control"] = "public, max-age=604800"
    return res


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
    # AI search and assistant crawlers are welcome on public pages, so tools
    # like ChatGPT, Claude, Perplexity and Gemini can cite QuizlyNotes.
    ai_bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-User",
               "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot-Extended", "Bingbot", "CCBot"]
    private = ["/api/", "/library", "/new", "/sets/", "/settings", "/try/", "/s/", "/r/", "/billing/",
               "/mock-exam", "/weak-spots", "/login"]
    ai_rules = []
    for bot in ai_bots:
        ai_rules += [f"User-agent: {bot}", "Allow: /"] + [f"Disallow: {p}" for p in private] + [""]
    body = "\n".join(ai_rules + [
        "User-agent: *",
        "Allow: /",
        "Disallow: /api/",
        "Disallow: /library",
        "Disallow: /new",
        "Disallow: /sets/",
        "Disallow: /settings",
        "Disallow: /try/",
        "Disallow: /s/",
        "Disallow: /r/",
        "Disallow: /billing/",
        "Disallow: /mock-exam",
        "Disallow: /weak-spots",
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
            ("/notes-to-flashcards", "0.9"), ("/ai-quiz-generator", "0.9"), ("/compare", "0.8"),
            ("/about", "0.6"), ("/pricing", "0.7"), ("/privacy", "0.2"), ("/terms", "0.2")]
    if not _monetised():
        urls = [u for u in urls if u[0] != "/pricing"]
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


# --- Shared quizzes --------------------------------------------------------------

@public_bp.route("/s/<token>")
def shared_quiz(token: str):
    from ..models import StudySet
    from .study import build_quiz_payload

    study_set = StudySet.query.filter_by(share_token=token).first()
    if study_set is None or not study_set.has_quiz:
        abort(404)
    payload = build_quiz_payload(study_set.to_dict())
    payload["submit_url"] = None
    payload["guest"] = True
    payload["shared"] = True
    payload["monetisation"] = current_app.config.get("MONETISATION_ENABLED", True)
    owner = study_set.owner
    # Friends who sign up from a shared quiz count as the owner's referrals.
    if owner and owner.referral_code and "ref" not in session:
        session["ref"] = owner.referral_code
    response = current_app.make_response(render_template(
        "public/shared.html", s=study_set, payload=payload,
        owner_name=(owner.display_name.split(" ")[0] if owner else "A student"),
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
