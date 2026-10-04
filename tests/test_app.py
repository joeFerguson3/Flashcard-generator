import io
import json

import pytest

from quizlynotes import create_app
from quizlynotes.ai.validate import clean_card, clean_notes
from quizlynotes.config import TestConfig
from quizlynotes.extensions import db
from quizlynotes.models import Card, StudySet, User


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email="a@example.com"):
    return client.get(f"/dev-login?email={email}")


def make_set(client):
    res = client.post("/api/sets", data={"text": "Cell respiration notes. " * 20, "subject": "Biology"})
    assert res.status_code == 200, res.data
    return int(res.json["redirect"].split("/")[2])


# --- public pages / SEO -------------------------------------------------------

@pytest.mark.parametrize("path", ["/", "/notes-to-quiz", "/pdf-to-quiz", "/notes-to-flashcards",
                                  "/ai-quiz-generator", "/compare", "/about", "/privacy", "/terms"])
def test_public_pages_are_indexable(client, path):
    res = client.get(path)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert '<link rel="canonical" href="https://quizlynotes.com' in html
    assert 'name="description"' in html
    assert "noindex" not in html
    assert html.count("<h1") == 1


def test_home_has_structured_data_and_keywords(client):
    html = client.get("/").get_data(as_text=True)
    assert '"@type": "FAQPage"' in html or '"@type":"FAQPage"' in html.replace(" ", "")
    assert "Quiz Notes" in html  # alternateName for brand searches
    assert "<title>QuizlyNotes: Turn Notes into Quizzes" in html


def test_robots_and_sitemap(client):
    robots = client.get("/robots.txt").get_data(as_text=True)
    assert "Sitemap: https://quizlynotes.com/sitemap.xml" in robots
    assert "Disallow: /library" in robots
    sitemap = client.get("/sitemap.xml").get_data(as_text=True)
    assert "<loc>https://quizlynotes.com/notes-to-quiz</loc>" in sitemap


def test_search_icon_images_and_ai_files(client):
    home = client.get("/").get_data(as_text=True)
    assert '<link rel="icon" href="/favicon.ico" sizes="48x48">' in home
    assert "screenshot-quiz.png" in home and '"screenshot"' in home
    fav = client.get("/favicon.ico")
    assert fav.status_code == 200 and fav.data[:4] == b"\x00\x00\x01\x00"
    robots = client.get("/robots.txt").get_data(as_text=True)
    assert "User-agent: GPTBot" in robots and "User-agent: ClaudeBot" in robots
    assert robots.count("Disallow: /library") >= 2
    llms = client.get("/llms.txt")
    assert llms.status_code == 200 and llms.get_data(as_text=True).startswith("# QuizlyNotes")
    full = client.get("/llms-full.txt").get_data(as_text=True)
    assert "Sort into groups" in full and "/compare" in full
    sitemap = client.get("/sitemap.xml").get_data(as_text=True)
    for path in ["/ai-quiz-generator", "/compare", "/about"]:
        assert f"<loc>https://quizlynotes.com{path}</loc>" in sitemap


def test_legacy_urls_redirect(client):
    for old in ["/home", "/upload", "/sets", "/quiz-sets"]:
        res = client.get(old)
        assert res.status_code == 301


def test_app_pages_require_login(client):
    assert client.get("/library").status_code == 302
    assert client.post("/api/sets").status_code == 401


# --- generation flow ----------------------------------------------------------

def test_full_flow(client, app):
    login(client)
    set_id = make_set(client)
    assert client.get(f"/sets/{set_id}/notes").status_code == 200

    res = client.post(f"/api/sets/{set_id}/generate", json={"count": 5, "difficulty": "hard"})
    assert res.status_code == 200, res.data
    with app.app_context():
        s = db.session.get(StudySet, set_id)
        assert s.subject == "Biology"
        assert len(s.quiz_cards) == 5
        assert s.flashcards
        quiz_ids = [c.id for c in s.quiz_cards]

    assert client.get(f"/sets/{set_id}").status_code == 200
    page = client.get(f"/sets/{set_id}/quiz").get_data(as_text=True)
    assert 'id="quiz-data"' in page

    res = client.post(f"/api/sets/{set_id}/attempts",
                      json={"results": [{"card_id": i, "correct": n % 2 == 0} for n, i in enumerate(quiz_ids)]})
    assert res.json["score"] == 60.0
    assert client.get(f"/sets/{set_id}/flashcards").status_code == 200

    with app.app_context():
        card = db.session.get(StudySet, set_id).flashcards[0]
    res = client.post(f"/api/cards/{card.id}/review", json={"grade": "good"})
    assert res.json["ok"]


def test_notes_autosave_keeps_section_ids(client, app):
    login(client)
    set_id = make_set(client)
    with app.app_context():
        sections = [s.to_dict() for s in db.session.get(StudySet, set_id).sections]
    sections[0]["points"].append({"text": "New point", "level": 2})
    sections.append({"id": None, "heading": "Extra", "subheading": "Added", "points": [{"text": "x", "level": 1}]})
    res = client.put(f"/api/sets/{set_id}/notes", json={"title": "Renamed", "sections": sections[1:]})
    assert res.status_code == 200
    returned = res.json["sections"]
    assert [s["id"] for s in returned[:-1]] == [s["id"] for s in sections[1:-1]]
    assert returned[-1]["heading"] == "Extra"


def test_cannot_access_someone_elses_set(client):
    login(client, "owner@example.com")
    set_id = make_set(client)
    client.post("/logout")
    login(client, "intruder@example.com")
    assert client.get(f"/sets/{set_id}").status_code == 404
    assert client.post(f"/sets/{set_id}/delete").status_code == 404
    assert client.post(f"/api/sets/{set_id}/generate", json={}).status_code == 404
    assert client.put(f"/api/sets/{set_id}/notes", json={}).status_code == 404


def test_upload_rejects_bad_files(client):
    login(client)
    res = client.post("/api/sets", data={"file": (io.BytesIO(b"hello"), "virus.exe")},
                      content_type="multipart/form-data")
    assert res.status_code == 400
    res = client.post("/api/sets", data={"file": (io.BytesIO(b"not a pdf"), "notes.pdf")},
                      content_type="multipart/form-data")
    assert res.status_code == 400
    assert "PDF" in res.json["error"]


def test_upload_pdf(client):
    login(client)
    pdf = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
           b"trailer<</Root 1 0 R>>\n%%EOF")
    res = client.post("/api/sets", data={"file": (io.BytesIO(pdf), "Lecture 3.pdf"), "skip_review": "1"},
                      content_type="multipart/form-data")
    assert res.status_code == 200
    assert res.json["redirect"].startswith("/sets/")


def test_edit_cards(client, app):
    login(client)
    set_id = make_set(client)
    client.post(f"/api/sets/{set_id}/generate", json={})
    with app.app_context():
        s = db.session.get(StudySet, set_id)
        mc = next(c for c in s.cards if c.kind == "multiple_choice")
        fc = s.flashcards[0]
        mc_id, fc_id = mc.id, fc.id
    res = client.post(f"/sets/{set_id}/cards", data={
        f"c{mc_id}-prompt": "Edited question?",
        f"c{mc_id}-options": "One\nTwo\nThree",
        f"c{mc_id}-correct": "2",
        f"c{mc_id}-explanation": "Because.",
        f"c{fc_id}-delete": "1",
        "action": "add_flashcard", "new-front": "Front", "new-back": "Back",
    })
    assert res.status_code == 302
    with app.app_context():
        mc = db.session.get(Card, mc_id)
        assert mc.prompt == "Edited question?" and mc.answers == ["Three"]
        assert db.session.get(Card, fc_id) is None
        assert any(c.prompt == "Front" for c in db.session.get(StudySet, set_id).flashcards)


def test_guest_demo_and_claim(client, app):
    res = client.post("/try", json={"text": "Photosynthesis converts light energy. " * 10})
    assert res.status_code == 200
    page = client.get(res.json["redirect"])
    assert page.status_code == 200
    login(client, "new@example.com")
    with app.app_context():
        user = User.query.filter_by(email="new@example.com").one()
        assert user.sets.count() == 1


def test_export_and_delete_account(client, app):
    login(client)
    make_set(client)
    data = json.loads(client.get("/settings/export").data)
    assert data["sets"][0]["sections"]
    res = client.post("/settings/delete", data={"confirm": "DELETE"})
    assert res.status_code == 302
    with app.app_context():
        assert User.query.count() == 0
        assert StudySet.query.count() == 0


# --- validation of model output -------------------------------------------------

def test_clean_card_repairs_and_rejects():
    mc = clean_card({"kind": "multiple_choice", "prompt": "Q?", "options": ["A1", "B1", "C1", "D1"],
                     "answers": ["b"], "explanation": ""}, 1)
    assert mc["answers"] == ["B1"]
    assert clean_card({"kind": "multiple_choice", "prompt": "Q?", "options": ["x", "y"], "answers": ["z"]}, 1) is None
    fb = clean_card({"kind": "fill_blank", "prompt": "The ___ is red.", "answers": ["apple"]}, 1)
    assert fb["prompt"] == "The {blank} is red."
    assert clean_card({"kind": "fill_blank", "prompt": "No blank", "answers": ["x"]}, 1) is None
    assert clean_card({"kind": "true_false", "prompt": "S", "answers": ["False"]}, 1)["answers"] == ["false"]
    assert clean_card({"kind": "ordering", "prompt": "Order", "options": ["a", "b"]}, 1) is None


def test_clean_notes_strips_bullets_and_tags():
    out = clean_notes([{"heading": "<b>H</b>", "subheading": "S", "points": [{"text": "- <i>point</i>", "level": 7}]}])
    assert out == [{"heading": "H", "subheading": "S", "points": [{"text": "point", "level": 3}]}]


def test_simplify_and_improve(client, app):
    login(client)
    set_id = make_set(client)
    with app.app_context():
        sections = [s.to_dict() for s in db.session.get(StudySet, set_id).sections]
    long_section = dict(sections[1], points=sections[1]["points"] + [{"text": "trivia", "level": 2}])
    res = client.post(f"/api/sets/{set_id}/enhance", json={"heading": "Cell respiration", "sections": [long_section], "mode": "simplify"})
    assert res.status_code == 200
    simplified = res.json["sections"][0]["points"]
    assert len(simplified) < len(long_section["points"]) and all(p["level"] == 1 for p in simplified)
    res = client.post(f"/api/sets/{set_id}/enhance", json={"heading": "Cell respiration", "sections": [long_section]})
    assert len(res.json["sections"][0]["points"]) > len(long_section["points"])


@pytest.mark.parametrize("game", ["match", "speed", "write"])
def test_games(client, game):
    login(client)
    set_id = make_set(client)
    page = client.get(f"/sets/{set_id}/play/{game}").get_data(as_text=True)
    assert "Not enough cards yet" in page  # no cards generated yet
    client.post(f"/api/sets/{set_id}/generate", json={})
    page = client.get(f"/sets/{set_id}/play/{game}").get_data(as_text=True)
    assert 'id="game"' in page and '"flashcards"' in page
    assert client.get(f"/sets/{set_id}/play/nope").status_code == 404


def test_new_question_kinds_validation():
    ok = clean_card({"kind": "matching", "prompt": "Match", "options": ["a", "b", "c"], "answers": ["1", "2", "3"]}, 1)
    assert ok["options"] == ["a", "b", "c"]
    assert clean_card({"kind": "matching", "prompt": "Match", "options": ["a", "b", "c"], "answers": ["1", "2"]}, 1) is None
    ms = clean_card({"kind": "multi_select", "prompt": "Pick", "options": ["A", "B", "C", "D"], "answers": ["a", "c"]}, 1)
    assert ms["answers"] == ["A", "C"]
    assert clean_card({"kind": "multi_select", "prompt": "Pick", "options": ["A", "B", "C", "D"], "answers": ["A", "B", "C", "D"]}, 1) is None
    cat = clean_card({"kind": "categorize", "prompt": "Sort", "options": ["x", "y", "z"], "answers": ["Hot", "cold", "hot"]}, 1)
    assert cat["answers"] == ["Hot", "cold", "Hot"]
    assert clean_card({"kind": "categorize", "prompt": "Sort", "options": ["x", "y", "z"], "answers": ["a", "a", "a"]}, 1) is None
    num = clean_card({"kind": "numeric", "prompt": "How many?", "answers": ["1,200", "cells"]}, 1)
    assert num["answers"] == ["1200", "cells"]
    assert clean_card({"kind": "numeric", "prompt": "How many?", "answers": ["lots"]}, 1) is None
    odd = clean_card({"kind": "odd_one_out", "prompt": "Odd one out?", "options": ["Cat", "Dog", "Cow", "Car"], "answers": ["car"]}, 1)
    assert odd["answers"] == ["Car"]
    assert clean_card({"kind": "odd_one_out", "prompt": "Odd?", "options": ["A", "B"], "answers": ["A"]}, 1) is None


def test_quiz_includes_new_kinds_and_editing(client, app):
    login(client)
    set_id = make_set(client)
    client.post(f"/api/sets/{set_id}/generate", json={"count": 20})
    with app.app_context():
        s = db.session.get(StudySet, set_id)
        kinds = {c.kind for c in s.quiz_cards}
        assert {"matching", "multi_select", "categorize", "numeric", "odd_one_out"} <= kinds
        assert "explain" not in kinds
        ids = {c.kind: c.id for c in s.quiz_cards}
    assert client.get(f"/sets/{set_id}/cards").status_code == 200
    res = client.post(f"/sets/{set_id}/cards", data={
        f"c{ids['matching']}-prompt": "Match these", f"c{ids['matching']}-pairs": "A = 1\nB = 2\nC = 3",
        f"c{ids['multi_select']}-prompt": "Pick", f"c{ids['multi_select']}-options": "*W\nX\n*Y\nZ",
        f"c{ids['numeric']}-prompt": "How many?", f"c{ids['numeric']}-number": "42", f"c{ids['numeric']}-unit": "kg",
    })
    assert res.status_code == 302
    with app.app_context():
        assert db.session.get(Card, ids["matching"]).answers == ["1", "2", "3"]
        assert db.session.get(Card, ids["multi_select"]).answers == ["W", "Y"]
        assert db.session.get(Card, ids["numeric"]).answers == ["42", "kg"]


def test_quiz_page_has_options_and_skips_legacy_explain(client, app):
    login(client)
    set_id = make_set(client)
    client.post(f"/api/sets/{set_id}/generate", json={"count": 20})
    with app.app_context():
        s = db.session.get(StudySet, set_id)
        db.session.add(Card(set_id=s.id, kind="explain", prompt="Explain why?", options=[], answers=["a", "b"]))
        db.session.commit()
    page = client.get(f"/sets/{set_id}/quiz").get_data(as_text=True)
    assert "data-options-dialog" in page and "data-new-quiz" in page and "Odd one out" in page
    assert "Explain why?" not in page and '"generate_url"' in page
    res = client.post(f"/api/sets/{set_id}/generate", json={"count": 5, "kinds": ["odd_one_out", "multiple_choice"]})
    assert res.status_code == 200
    with app.app_context():
        kinds = {c.kind for c in db.session.get(StudySet, set_id).quiz_cards}
        assert kinds <= {"odd_one_out", "multiple_choice"}
