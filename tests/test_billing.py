import hashlib
import hmac
import json
import time
from datetime import timedelta

import pytest

from quizlynotes import billing, create_app
from quizlynotes.config import TestConfig
from quizlynotes.extensions import db
from quizlynotes.models import StudySet, User, utcnow


class BillingConfig(TestConfig):
    STRIPE_WEBHOOK_SECRET = "whsec_test"
    ADMIN_EMAILS = {"boss@example.com"}

    @classmethod
    def with_db(cls):
        # In-memory SQLite is per-connection; a shared file keeps data across contexts.
        import os
        import tempfile

        path = os.path.join(tempfile.mkdtemp(), "t.db")
        return type("Cfg", (cls,), {"SQLALCHEMY_DATABASE_URI": "sqlite:///" + path})


@pytest.fixture
def app():
    # No app context is held open during requests, so each request loads
    # fresh user state (like production).
    app = create_app(BillingConfig.with_db())
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email="a@example.com"):
    client.get(f"/dev-login?email={email}")


def make_free(app, email="a@example.com"):
    with app.app_context():
        u = User.query.filter_by(email=email).one()
        u.pro_until = None
        db.session.commit()


def new_set(client):
    return client.post("/api/sets", data={"text": "Cell respiration notes. " * 20})


def test_signup_starts_trial(client, app):
    login(client)
    with app.app_context():
        u = User.query.one()
        assert billing.is_pro(u)
        assert 6 <= (u.pro_until - utcnow()).days <= 7
        assert u.referral_code
    assert b"Pro trial" in client.get("/library").data


def test_free_set_limit_and_upgrade_prompt(client, app):
    login(client)
    make_free(app)
    for _ in range(billing.FREE.sets_per_month):
        assert new_set(client).status_code == 200
    res = new_set(client)
    assert res.status_code == 402
    assert res.json["upgrade"] and "/pricing" in res.json["upgrade_url"]
    page = client.get("/library").data
    assert b"0</strong> of 5 free AI sets left" in page


def test_regenerate_and_ai_edit_limits(client, app):
    login(client)
    make_free(app)
    set_id = int(new_set(client).json["redirect"].split("/")[2])
    for _ in range(1 + billing.FREE.regenerations_per_set):
        assert client.post(f"/api/sets/{set_id}/generate", json={}).status_code == 200
    assert client.post(f"/api/sets/{set_id}/generate", json={}).status_code == 402
    section = {"heading": "H", "subheading": "S", "points": [{"text": "x", "level": 1}]}
    for _ in range(billing.FREE.ai_edits_per_month):
        assert client.post(f"/api/sets/{set_id}/enhance", json={"heading": "H", "sections": [section]}).status_code == 200
    assert client.post(f"/api/sets/{set_id}/enhance", json={"heading": "H", "sections": [section]}).status_code == 402


def test_pro_features_gated(client, app):
    login(client)
    make_free(app)
    assert client.get("/mock-exam").status_code == 402
    assert client.get("/weak-spots").status_code == 402
    with app.app_context():
        u = User.query.one()
        billing.extend_pro(u, 3)
        db.session.commit()
    set_id = int(new_set(client).json["redirect"].split("/")[2])
    client.post(f"/api/sets/{set_id}/generate", json={})
    assert client.get("/mock-exam").status_code == 200
    page = client.get("/mock-exam?subject=Biology&n=10")
    assert page.status_code == 200 and b'"timed": true' in page.data
    assert b"No weak spots yet" in client.get("/weak-spots").data
    with app.app_context():
        card = StudySet.query.one().quiz_cards[0]
        card_id = card.id
    res = client.post("/api/cards/results", json={"results": [{"card_id": card_id, "correct": False}]})
    assert res.json["score"] == 0
    assert b"quiz-data" in client.get("/weak-spots").data


def test_admin_email_is_pro(client, app):
    login(client, "boss@example.com")
    with app.app_context():
        u = User.query.one()
        u.pro_until = None
        db.session.commit()
        assert billing.is_pro(u) and billing.plan_status(u)["lifetime"]


def test_promo_codes(client, app):
    with app.app_context():
        _, week = billing.create_promo("Week", days=7, max_redemptions=1)
        _, life = billing.create_promo("Life", code="qn-life-1234")
        db.session.commit()
    login(client)
    make_free(app)
    res = client.post("/redeem", data={"code": week}, follow_redirects=True)
    assert b"7 days of Pro added" in res.data
    login(client, "b@example.com")
    res = client.post("/redeem", data={"code": week}, follow_redirects=True)
    assert b"fully used" in res.data
    res = client.post("/redeem", data={"code": "QN-LIFE-1234"}, follow_redirects=True)
    assert b"Pro for life" in res.data
    res = client.post("/redeem", data={"code": "nope"}, follow_redirects=True)
    assert b"isn&#39;t valid" in res.data or b"isn't valid" in res.data


def test_referrals(client, app):
    login(client, "inviter@example.com")
    with app.app_context():
        inviter = User.query.filter_by(email="inviter@example.com").one()
        code, before = inviter.referral_code, inviter.pro_until
    client.post("/logout")
    client.get(f"/r/{code}")
    login(client, "friend@example.com")
    with app.app_context():
        friend = User.query.filter_by(email="friend@example.com").one()
        assert friend.referred_by_id == inviter.id
        assert (friend.pro_until - utcnow()).days >= 13
    new_set(client)
    with app.app_context():
        inviter = User.query.filter_by(email="inviter@example.com").one()
        assert inviter.pro_until >= before + timedelta(days=6, hours=23)
        assert billing.referral_count(inviter) == 1


def _signed(payload: dict, secret="whsec_test"):
    body = json.dumps(payload)
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
    return body, {"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"}


def test_stripe_webhook_updates_subscription(client, app):
    login(client)
    make_free(app)
    with app.app_context():
        user_id = User.query.one().id
    period_end = int(time.time()) + 30 * 86400
    event = {"id": "evt_1", "object": "event", "type": "customer.subscription.updated", "data": {"object": {
        "id": "sub_1", "object": "subscription", "customer": "cus_1", "status": "active",
        "cancel_at_period_end": False, "metadata": {"user_id": str(user_id)},
        "items": {"data": [{"current_period_end": period_end, "price": {"recurring": {"interval": "year"}}}]},
    }}}
    body, headers = _signed(event)
    assert client.post("/billing/webhook", data=body, headers=headers).status_code == 200
    with app.app_context():
        u = db.session.get(User, user_id)
        assert u.subscription_status == "active" and u.subscription_interval == "year"
        assert u.stripe_customer_id == "cus_1" and billing.is_pro(u)
        assert billing.plan_status(u)["paid"]
    bad_body, bad_headers = _signed(event, secret="wrong")
    assert client.post("/billing/webhook", data=bad_body, headers=bad_headers).status_code == 400


def test_pricing_page_and_checkout_without_stripe(client, app):
    res = client.get("/pricing")
    assert res.status_code == 200 and b"Try Pro free for 7 days" in res.data
    assert b'rel="canonical" href="https://quizlynotes.com/pricing"' in res.data
    login(client)
    make_free(app)
    assert b"Payments open soon" in client.get("/pricing").data
    res = client.post("/billing/checkout", data={"interval": "year"})
    assert res.status_code == 302


def test_sharing(client, app):
    login(client)
    set_id = int(new_set(client).json["redirect"].split("/")[2])
    client.post(f"/api/sets/{set_id}/generate", json={})
    client.post(f"/sets/{set_id}/share")
    with app.app_context():
        token = db.session.get(StudySet, set_id).share_token
    client.post("/logout")
    anon = app.test_client()
    page = anon.get(f"/s/{token}")
    assert page.status_code == 200 and b"shared this quiz" in page.data
    assert page.headers["X-Robots-Tag"] == "noindex"
    login(client)
    client.post(f"/sets/{set_id}/share", data={"action": "stop"})
    assert anon.get(f"/s/{token}").status_code == 404


def test_logout_really_logs_out(client, app):
    login(client)
    assert client.get("/library").status_code == 200
    client.post("/logout")
    assert client.get("/library").status_code == 302


def test_monetisation_switched_off():
    cfg = type("Off", (BillingConfig.with_db(),), {"MONETISATION_ENABLED": False})
    app = create_app(cfg)
    with app.app_context():
        db.create_all()
    client = app.test_client()
    home = client.get("/").get_data(as_text=True)
    assert "/pricing" not in home and "Pro trial" not in home and "Pro (monthly)" not in home
    assert client.get("/pricing").status_code == 302
    assert "/pricing" not in client.get("/sitemap.xml").get_data(as_text=True)
    assert "£" not in client.get("/llms-full.txt").get_data(as_text=True)
    assert "£" not in client.get("/ai-quiz-generator").get_data(as_text=True)
    login(client)
    with app.app_context():
        u = User.query.one()
        assert u.trial_started_at is None and billing.is_pro(u)
    lib = client.get("/library").get_data(as_text=True)
    assert "Upgrade" not in lib and "Pro trial" not in lib and "free AI sets left" not in lib
    for _ in range(billing.FREE.sets_per_month + 1):
        assert new_set(client).status_code == 200
    assert client.get("/mock-exam").status_code == 200
    assert "Plan & billing" not in client.get("/settings").get_data(as_text=True)


def test_admin_stats_page(client, app):
    login(client, "someone@example.com")
    set_id = int(new_set(client).json["redirect"].split("/")[2])
    client.post(f"/api/sets/{set_id}/generate", json={})
    client.post(f"/api/sets/{set_id}/attempts", json={"results": []})
    client.get("/library")
    client.get("/library")
    assert client.get("/admin/stats").status_code == 404
    with app.app_context():
        from quizlynotes.models import UsageEvent
        assert UsageEvent.query.filter_by(kind="visit").count() == 1  # once per day
    client.post("/logout")
    login(client, "boss@example.com")
    assert b">Stats<" in client.get("/library").data
    page = client.get("/admin/stats")
    assert page.status_code == 200 and page.headers["X-Robots-Tag"].startswith("noindex")
    html = page.get_data(as_text=True)
    users_table = html.split('id="t-users"')[1]
    assert "someone@example.com" in users_table and "boss@example.com" not in users_table
    assert "boss@example.com" in client.get("/admin/stats?me=1").get_data(as_text=True).split('id="t-users"')[1]
    for r in (7, 30, 90, 0):
        assert client.get(f"/admin/stats?range={r}").status_code == 200


def test_growth_stats(client, app):
    ua = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0) Mobile"}
    client.get("/notes-to-quiz?ref=TikTok", headers=ua)
    client.get("/", headers=ua)  # same session: not a second landing
    app.test_client().get("/", headers={"User-Agent": "Googlebot/2.1"})  # bots ignored
    app.test_client().get("/pdf-to-quiz", headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.google.com/"})
    login(client, "fan@example.com")
    set_id = int(new_set(client).json["redirect"].split("/")[2])
    client.post(f"/api/sets/{set_id}/generate", json={})
    with app.app_context():
        from quizlynotes.models import SiteEvent
        u = User.query.filter_by(email="fan@example.com").one()
        assert (u.signup_source, u.signup_landing, u.signup_device) == ("tiktok", "/notes-to-quiz", "mobile")
        assert SiteEvent.query.filter_by(kind="landing").count() == 2
        card = StudySet.query.one().quiz_cards[0]
        card_id, kind = card.id, card.kind
    client.post(f"/api/sets/{set_id}/attempts", json={"results": [{"card_id": card_id, "correct": False, "skipped": True}]})
    client.post("/api/sets", data={"text": "too short"})  # rejected upload
    client.post("/logout")
    login(client, "boss@example.com")
    html = client.get("/admin/stats").get_data(as_text=True)
    assert "tiktok" in html and "Google" in html and "/notes-to-quiz" in html
    assert "Upload rejected" in html
    with app.app_context():
        from quizlynotes.activity import build_stats
        s = build_stats({"boss@example.com"})
        q = next(r for r in s["qtypes"] if r["skips"])
        assert q["skips"] == 1
        assert dict((label, n) for label, n, _ in s["funnel"])["Signed up"] == 1


def test_admin_set_and_user_preview(client, app):
    login(client, "someone@example.com")
    set_id = int(new_set(client).json["redirect"].split("/")[2])
    client.post(f"/api/sets/{set_id}/generate", json={})
    assert client.get(f"/admin/sets/{set_id}").status_code == 404
    with app.app_context():
        uid = User.query.filter_by(email="someone@example.com").one().id
    client.post("/logout")
    login(client, "boss@example.com")
    stats = client.get("/admin/stats").get_data(as_text=True)
    assert f"/admin/sets/{set_id}" in stats and f"/admin/users/{uid}" in stats
    page = client.get(f"/admin/sets/{set_id}")
    assert page.status_code == 200 and b"Preview" in page.data and b"Questions" in page.data
    assert client.get(f"/admin/users/{uid}").status_code == 200
    assert client.get("/admin/sets/99999").status_code == 404


def test_quality_and_dropoff_events(client, app):
    from quizlynotes.models import SiteEvent

    login(client, "learner@example.com")
    set_id = int(new_set(client).json["redirect"].split("/")[2])
    with app.app_context():
        st = db.session.get(StudySet, set_id)
        sections = [x.to_dict() for x in st.sections]
    sections[0]["points"] = sections[0]["points"][1:]  # delete a point
    assert client.put(f"/api/sets/{set_id}/notes", json={"sections": sections}).status_code == 200
    client.post(f"/api/sets/{set_id}/generate", json={})
    client.get(f"/sets/{set_id}/quiz?n=2")
    with app.app_context():
        card = StudySet.query.get(set_id).quiz_cards[0]
        cid, ckind = card.id, card.kind
    client.post(f"/api/sets/{set_id}/attempts", json={"secs": 95, "results": [{"card_id": cid, "correct": True}]})
    client.post("/api/beacon", data='{"kind":"quiz_abandon","fields":{"set":"%d","answered":"1","of":"4","stage":"question","qkind":"%s"}}' % (set_id, ckind))
    client.post("/api/beacon", data='{"kind":"evil","fields":{}}')
    assert client.post(f"/api/cards/{cid}/report", json={"reason": "wrong"}).json["ok"]
    client.post(f"/sets/{set_id}/cards", data={f"c{cid}-delete": "1"})
    with app.app_context():
        kinds = {e.kind for e in SiteEvent.query.all()}
        assert {"notes_made", "notes_edit", "quiz_made", "quiz_start", "quiz_done", "quiz_abandon",
                "q_report", "card_delete"} <= kinds and "evil" not in kinds
        edit = SiteEvent.query.filter_by(kind="notes_edit").first()
        assert "removed=1" in edit.detail
    client.post("/logout")
    login(client, "boss@example.com")
    html = client.get("/admin/stats").get_data(as_text=True)
    assert "Answer is wrong" in html and "Where people stop" in html and "Coming back" in html
    # Opting out stops new events.
    with app.app_context():
        before = SiteEvent.query.count()
    client.post("/privacy/analytics", data={"choice": "off"})
    client.post("/api/beacon", data='{"kind":"quiz_abandon","fields":{}}')
    with app.app_context():
        assert SiteEvent.query.count() == before


def test_google_ads_tag_needs_consent(client):
    html = client.get("/").get_data(as_text=True)
    assert "AW-TEST" in html and "data-cookie-banner" in html
    # The gtag script is only injected by JS after consent, never as a static tag.
    assert 'src="https://www.googletagmanager.com' not in html
    assert "qn_ads=yes" in html
    assert 'id="cookies"' in client.get("/privacy").get_data(as_text=True)
