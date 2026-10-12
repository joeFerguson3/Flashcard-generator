"""Lightweight activity tracking and the owner's statistics.

`track(kind)` stores at most one UsageEvent per user, per kind, per day, so
repeat visits can be measured without logging every request. The kinds used
here ("visit", "flashcards", "practice") are separate from the plan-limit
kinds ("new_set", "quiz", "ai_edit") and never count towards limits.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import current_app, has_request_context, request, session
from flask_login import current_user

from .extensions import db
from .models import Attempt, Card, GuestDraft, SiteEvent, StudySet, UsageEvent, User, utcnow

LOCAL_TZ = ZoneInfo("Europe/London")


def local_day(dt: datetime | None) -> date | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ).date()


OPT_OUT_COOKIE = "qn_analytics"


def analytics_allowed() -> bool:
    """False when this browser has opted out of usage analytics."""
    return not (has_request_context() and request.cookies.get(OPT_OUT_COOKIE) == "off")


def kv(**fields) -> str:
    """Compact "key=value;key=value" detail string for SiteEvents."""
    return ";".join(f"{k}={v}" for k, v in fields.items() if v is not None)[:200]


def parse_kv(detail: str | None) -> dict:
    out = {}
    for part in (detail or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def track(kind: str) -> None:
    """Record `kind` for the signed-in user, once per day. Never raises."""
    try:
        if not analytics_allowed():
            return
        if not current_user or not current_user.is_authenticated:
            return
        today = utcnow().date().isoformat()
        key = f"_seen_{kind}"
        if session.get(key) == today:
            return
        session[key] = today
        db.session.add(UsageEvent(user_id=current_user.id, kind=kind))
        db.session.commit()
    except Exception:  # tracking must never break a page
        db.session.rollback()
        current_app.logger.exception("activity tracking failed")


# --- Visit attribution ----------------------------------------------------------

import re
import secrets
from urllib.parse import urlparse

_BOT_RE = re.compile(r"bot|crawl|spider|slurp|preview|monitor|headless|lighthouse|python|curl|wget|httpx|scrapy", re.I)
_SKIP_ENDPOINTS = {
    "static", "public.robots", "public.sitemap", "public.manifest", "public.llms_txt", "public.llms_full_txt",
    "public.favicon", "public.healthz", "public.try_it",
}
_REFERRERS = [
    ("google.", "Google"), ("bing.com", "Bing"), ("duckduckgo.com", "DuckDuckGo"), ("yahoo.", "Yahoo"),
    ("ecosia.org", "Ecosia"), ("chatgpt.com", "ChatGPT"), ("openai.com", "ChatGPT"), ("perplexity.ai", "Perplexity"),
    ("claude.ai", "Claude"), ("gemini.google", "Gemini"), ("copilot.microsoft", "Copilot"), ("reddit.com", "Reddit"),
    ("tiktok.com", "TikTok"), ("instagram.com", "Instagram"), ("facebook.com", "Facebook"), ("t.co", "X / Twitter"),
    ("x.com", "X / Twitter"), ("twitter.com", "X / Twitter"), ("youtube.com", "YouTube"), ("linkedin.com", "LinkedIn"),
    ("discord", "Discord"), ("whatsapp", "WhatsApp"), ("snapchat", "Snapchat"),
]


def classify_source(req) -> str:
    tag = req.args.get("ref") or req.args.get("utm_source")
    if tag:
        return re.sub(r"[^a-z0-9_\-]", "", tag.lower())[:40] or "Tagged link"
    if req.path.startswith("/s/"):
        return "Shared quiz"
    if req.path.startswith("/r/"):
        return "Invite link"
    ref = req.referrer or ""
    host = (urlparse(ref).hostname or "").lower()
    if not host or host == (req.host or "").split(":")[0].lower():
        return "Direct"
    if host.startswith("www."):
        host = host[4:]
    for needle, label in _REFERRERS:
        if needle in host:
            return label
    return host[:60]


def device_of(req) -> str:
    ua = req.headers.get("User-Agent", "")
    if re.search(r"iPad|Tablet", ua):
        return "tablet"
    if re.search(r"Mobi|Android|iPhone", ua):
        return "mobile"
    return "desktop"


def capture_visit(req) -> None:
    """On the first page of a browser session, note where the visitor came from."""
    try:
        if req.method != "GET" or not req.endpoint or req.endpoint in _SKIP_ENDPOINTS:
            return
        if req.endpoint.startswith(("api.", "admin.")) or session.get("sid") or not analytics_allowed():
            return
        ua = req.headers.get("User-Agent", "")
        if not ua or _BOT_RE.search(ua):
            return
        sid = secrets.token_hex(8)
        session["sid"] = sid
        session["src"] = classify_source(req)
        session["land"] = req.path[:200]
        session["dev"] = device_of(req)
        user_id = current_user.id if current_user and current_user.is_authenticated else None
        db.session.add(SiteEvent(kind="landing", sid=sid, source=session["src"], path=session["land"],
                                 device=session["dev"], user_id=user_id))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("visit capture failed")


def log_event(kind: str, detail: str | None = None, user_id: int | None = None) -> None:
    """Store a SiteEvent with the current visit's source. Never raises."""
    try:
        if not analytics_allowed():
            return
        if user_id is None and current_user and current_user.is_authenticated:
            user_id = current_user.id
        db.session.add(SiteEvent(kind=kind, sid=session.get("sid"), source=session.get("src"),
                                 path=session.get("land"), device=session.get("dev"),
                                 user_id=user_id, detail=(detail or "")[:200] or None))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("event logging failed")


def attribute_signup(user) -> None:
    """Copy the visit's source onto a brand-new user."""
    user.signup_source = session.get("src") or "Direct"
    user.signup_landing = session.get("land")
    user.signup_device = session.get("dev")
    user.signup_sid = session.get("sid")


# --- Statistics -----------------------------------------------------------------

def _pct(part: int, whole: int) -> int | None:
    return round(part / whole * 100) if whole else None


def build_stats(exclude_emails: set[str], days: int = 30) -> dict:
    """Everything the stats page shows, computed in Python (the data is small)."""
    users = [u for u in User.query.all() if (u.email or "").lower() not in exclude_emails]
    user_ids = {u.id for u in users}

    sets = [s for s in StudySet.query.all() if s.user_id in user_ids]
    set_owner = {s.id: s.user_id for s in sets}
    set_title = {s.id: s.title for s in sets}
    attempts = [a for a in Attempt.query.order_by(Attempt.created_at).all() if a.set_id in set_owner]
    events = [e for e in UsageEvent.query.all() if e.user_id in user_ids]
    guests = GuestDraft.query.all()

    today = local_day(utcnow())
    if not days:  # "all time": from the first sign-up
        first = min((local_day(u.created_at) for u in users), default=today)
        days = max(7, (today - first).days + 1)
    window = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    week_ago = today - timedelta(days=6)

    # Which days each user did something.
    active = defaultdict(set)
    for u in users:
        for d in (local_day(u.created_at), local_day(u.last_login_at)):
            if d:
                active[u.id].add(d)
    for s in sets:
        active[s.user_id].add(local_day(s.created_at))
    for a in attempts:
        active[set_owner[a.set_id]].add(local_day(a.created_at))
    for e in events:
        active[e.user_id].add(local_day(e.created_at))

    quizzes_by_user = Counter(set_owner[a.set_id] for a in attempts)
    scores_by_user = defaultdict(list)
    for a in attempts:
        scores_by_user[set_owner[a.set_id]].append(a.score)
    sets_by_user = Counter(s.user_id for s in sets)
    flash_days = Counter(e.user_id for e in events if e.kind == "flashcards")
    game_days = Counter(e.user_id for e in events if e.kind == "game")
    cross_by_user = Counter(e.user_id for e in events if e.kind == "cross_quiz")

    # Daily series for the charts.
    quizzes_per_day = Counter(local_day(a.created_at) for a in attempts)
    signups_per_day = Counter(local_day(u.created_at) for u in users)
    active_per_day = Counter(d for days_ in active.values() for d in days_)
    sets_per_day = Counter(local_day(s.created_at) for s in sets)
    hidden_ids = {u.id for u in User.query.all()} - user_ids
    visits_per_day = Counter(local_day(e.created_at) for e in SiteEvent.query.filter_by(kind="landing").all()
                             if e.user_id not in hidden_ids)
    series = [
        {"day": d, "quizzes": quizzes_per_day.get(d, 0), "active": active_per_day.get(d, 0),
         "signups": signups_per_day.get(d, 0), "sets": sets_per_day.get(d, 0), "visits": visits_per_day.get(d, 0)}
        for d in window
    ]
    # Running total of users, for the growth line.
    joined_days = sorted(local_day(u.created_at) for u in users)
    cumulative = [{"day": d, "total": sum(1 for j in joined_days if j <= d)} for d in window]

    # When people study (all time, UK time).
    local_times = [a.created_at.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ) for a in attempts]
    by_hour = Counter(t.hour for t in local_times)
    by_weekday = Counter(t.weekday() for t in local_times)
    hours = [{"label": f"{h:02d}", "v": by_hour.get(h, 0), "tip": f"{h:02d}:00–{h:02d}:59"} for h in range(24)]
    weekdays = [{"label": n, "v": by_weekday.get(i, 0), "tip": n} for i, n in
                enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])]

    # How well people score.
    score_bands = [("0–19%", 0, 20), ("20–39%", 20, 40), ("40–59%", 40, 60), ("60–79%", 60, 80), ("80–100%", 80, 101)]
    scores_hist = [{"label": lab, "v": sum(1 for a in attempts if lo <= a.score < hi), "tip": lab}
                   for lab, lo, hi in score_bands]

    # Repeat use.
    active_days = {uid: len(ds) for uid, ds in active.items()}
    returned = [u for u in users if len(active[u.id] - {local_day(u.created_at)}) > 0]
    old_enough = [u for u in users if local_day(u.created_at) <= today - timedelta(days=7)]
    returned_old = [u for u in old_enough if len(active[u.id] - {local_day(u.created_at)}) > 0]
    buckets = [("1 day", 0), ("2 days", 0), ("3 to 5 days", 0), ("6+ days", 0)]
    counts = Counter()
    for u in users:
        n = active_days.get(u.id, 1)
        label = "1 day" if n <= 1 else "2 days" if n == 2 else "3 to 5 days" if n <= 5 else "6+ days"
        counts[label] += 1
    buckets = [(label, counts[label]) for label, _ in buckets]

    rows = []
    for u in users:
        scores = scores_by_user.get(u.id, [])
        last = max(active[u.id]) if active[u.id] else None
        rows.append({
            "id": u.id, "email": u.email, "name": u.name or "", "joined": local_day(u.created_at), "last_active": last,
            "active_days": active_days.get(u.id, 0), "sets": sets_by_user.get(u.id, 0),
            "quizzes": quizzes_by_user.get(u.id, 0),
            "avg_score": round(sum(scores) / len(scores)) if scores else None,
            "flash_days": flash_days.get(u.id, 0),
            "game_days": game_days.get(u.id, 0),
            "cross": cross_by_user.get(u.id, 0),
            "returned": u in returned,
        })
    rows.sort(key=lambda r: (r["last_active"] or date.min, r["quizzes"]), reverse=True)

    email_of = {u.id: u.email for u in users}
    recent = [
        {"when": a.created_at.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ), "email": email_of[set_owner[a.set_id]],
         "set_id": a.set_id, "user_id": set_owner[a.set_id],
         "title": set_title[a.set_id], "score": a.score, "correct": a.correct, "total": a.total}
        for a in reversed(attempts[-40:])
    ]

    week_active = sum(1 for ds in active.values() if any(d >= week_ago for d in ds))
    growth = _growth_stats(users, sets, attempts, active, exclude_emails, window[0], today)
    insight = _insight_stats(users, sets, attempts, active, exclude_emails, window[0], today)
    return {
        **growth,
        **insight,
        "today": today,
        "days": days,
        "tiles": {
            "users": len(users),
            "new_week": sum(1 for u in users if local_day(u.created_at) >= week_ago),
            "active_week": week_active,
            "returned": len(returned),
            "returned_pct": _pct(len(returned), len(users)),
            "returned_old_pct": _pct(len(returned_old), len(old_enough)),
            "old_enough": len(old_enough),
            "quizzes": len(attempts),
            "quizzes_week": sum(1 for a in attempts if local_day(a.created_at) >= week_ago),
            "sets": len(sets),
            "avg_score": round(sum(a.score for a in attempts) / len(attempts)) if attempts else None,
            "guests": len(guests),
            "cross": sum(cross_by_user.values()),
            "flash_users": len(flash_days),
        },
        "series": series,
        "series_max": {k: max([s[k] for s in series] + [1]) for k in ("quizzes", "active", "signups", "sets", "visits")},
        "cumulative": cumulative,
        "hours": hours, "weekdays": weekdays, "scores_hist": scores_hist,
        "set_rows": set_rows(sets, attempts, email_of)[:60],
        "buckets": buckets,
        "users": rows,
        "recent": recent,
        "visits_since": min((local_day(e.created_at) for e in events if e.kind == "visit"), default=None),
    }


def _growth_stats(users, sets, attempts, active, exclude_emails, start: date, today: date) -> dict:
    """Sources, funnel, shares, failures and question-type stats for the period."""
    excluded_ids = {u.id for u in User.query.all() if (u.email or "").lower() in exclude_emails}
    in_period = lambda dt: dt is not None and local_day(dt) >= start  # noqa: E731
    site = [e for e in SiteEvent.query.all() if e.user_id not in excluded_ids]
    landings = [e for e in site if e.kind == "landing" and in_period(e.created_at)]
    tracking_since = min((local_day(e.created_at) for e in site if e.kind == "landing"), default=None)

    joined = [u for u in users if in_period(u.created_at)]
    sets_by_user = Counter(s.user_id for s in sets)
    set_owner = {s.id: s.user_id for s in sets}
    quiz_users = {set_owner[a.set_id] for a in attempts}
    returned = {u.id for u in users if active[u.id] - {local_day(u.created_at)}}

    # Where people come from.
    by_source = defaultdict(lambda: {"visits": 0, "signups": 0, "active": 0})
    for e in landings:
        by_source[e.source or "Direct"]["visits"] += 1
    for u in joined:
        row = by_source[u.signup_source or "Unknown (before tracking)"]
        row["signups"] += 1
        row["active"] += int(u.id in quiz_users)
    sources = sorted(
        ({"source": k, **v, "rate": _pct(v["signups"], v["visits"])} for k, v in by_source.items()),
        key=lambda r: (r["visits"], r["signups"]), reverse=True)

    by_page = defaultdict(lambda: {"visits": 0, "signups": 0})
    for e in landings:
        by_page[e.path or "/"]["visits"] += 1
    for u in joined:
        if u.signup_landing:
            by_page[u.signup_landing]["signups"] += 1
    pages = sorted(({"path": k, **v, "rate": _pct(v["signups"], v["visits"])} for k, v in by_page.items()),
                   key=lambda r: (r["visits"], r["signups"]), reverse=True)[:15]

    devices = Counter(e.device or "unknown" for e in landings)
    signup_devices = Counter(u.signup_device for u in joined if u.signup_device)

    # Funnel for the period.
    demo_sids = {e.sid for e in site if e.kind == "demo" and in_period(e.created_at) and e.sid}
    demo_signups = sum(1 for u in joined if u.signup_sid and u.signup_sid in demo_sids)
    made_set = [u for u in joined if sets_by_user.get(u.id)]
    did_quiz = [u for u in joined if u.id in quiz_users]
    came_back = [u for u in joined if u.id in returned]
    funnel = [
        ("Visits", len({e.sid for e in landings}), "people who opened the site"),
        ("Tried the demo", len(demo_sids), "made a quiz without an account"),
        ("Signed up", len(joined), f"{demo_signups} of them had tried the demo first" if demo_sids else "new accounts"),
        ("Made a study set", len(made_set), "of those who signed up"),
        ("Finished a quiz", len(did_quiz), "of those who signed up"),
        ("Came back another day", len(came_back), "of those who signed up"),
    ]
    funnel_max = max([n for _, n, _ in funnel] + [1])

    # Shared quizzes.
    share_opens = [e for e in site if e.kind == "share_open" and in_period(e.created_at)]
    shares = {
        "opens": len(share_opens),
        "visitors": len({e.sid for e in share_opens if e.sid}),
        "quizzes": len({e.detail for e in share_opens}),
        "signups": sum(1 for u in joined if u.signup_source == "Shared quiz"),
        "invite_signups": sum(1 for u in joined if u.signup_source == "Invite link" or u.referred_by_id),
    }

    # Things going wrong.
    email_of = {u.id: u.email for u in users}
    errors = [e for e in site if e.kind.startswith("error_") and in_period(e.created_at)]
    error_counts = Counter(e.kind for e in errors)
    recent_errors = [
        {"when": e.created_at.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ),
         "kind": {"error_upload": "Upload rejected", "error_ai": "AI failed", "error_demo": "Demo failed"}.get(e.kind, e.kind),
         "who": email_of.get(e.user_id) or "Visitor", "detail": e.detail or ""}
        for e in sorted(errors, key=lambda e: e.created_at, reverse=True)[:25]
    ]
    no_sets = [{"email": u.email, "joined": local_day(u.created_at),
                "last_active": max(active[u.id]) if active[u.id] else None,
                "errors": sum(1 for e in site if e.kind.startswith("error_") and e.user_id == u.id)}
               for u in users if not sets_by_user.get(u.id)]

    # Question types (all time, since cards keep running totals).
    set_ids = set(set_owner)
    by_kind = defaultdict(lambda: {"seen": 0, "correct": 0, "cards": 0})
    for c in Card.query.filter(Card.kind != "flashcard").all():
        if c.set_id not in set_ids:
            continue
        row = by_kind[c.kind]
        row["cards"] += 1
        row["seen"] += c.times_seen or 0
        row["correct"] += c.times_correct or 0
    skips = Counter(e.detail for e in site if e.kind == "q_skip")
    overrides = Counter(e.detail for e in site if e.kind == "q_override")
    labels = {"multiple_choice": "Multiple choice", "true_false": "True or false", "fill_blank": "Fill in the blank",
              "short_answer": "Short answer", "ordering": "Ordering", "matching": "Matching",
              "multi_select": "Select all that apply", "categorize": "Sort into groups", "numeric": "Numeric",
              "odd_one_out": "Odd one out", "explain": "Explain (old)"}
    qtypes = sorted(({
        "key": k, "kind": labels.get(k, k), "cards": v["cards"], "seen": v["seen"],
        "accuracy": _pct(v["correct"], v["seen"]), "skips": skips.get(k, 0), "skip_rate": _pct(skips.get(k, 0), v["seen"]),
        "overrides": overrides.get(k, 0),
    } for k, v in by_kind.items()), key=lambda r: (r["accuracy"] is None, r["accuracy"] if r["accuracy"] is not None else 0))

    return {
        "tracking_since": tracking_since,
        "sources": sources, "pages": pages,
        "devices": sorted(devices.items(), key=lambda kv: -kv[1]),
        "signup_devices": dict(signup_devices),
        "funnel": funnel, "funnel_max": funnel_max,
        "shares": shares,
        "error_counts": error_counts, "recent_errors": recent_errors, "no_sets": no_sets,
        "qtypes": qtypes,
    }


def set_rows(sets, attempts, email_of) -> list[dict]:
    taken = Counter(a.set_id for a in attempts)
    rows = [{
        "id": st.id, "title": st.title, "subject": st.subject, "email": email_of.get(st.user_id, ""),
        "user_id": st.user_id, "created": local_day(st.created_at), "questions": len(st.quiz_cards),
        "flashcards": len(st.flashcards), "quizzes": taken.get(st.id, 0), "best": st.best_score,
        "source": st.source_name or "",
    } for st in sets]
    rows.sort(key=lambda r: r["created"] or date.min, reverse=True)
    return rows


def _median(values):
    v = sorted(values)
    if not v:
        return None
    mid = len(v) // 2
    return v[mid] if len(v) % 2 else (v[mid - 1] + v[mid]) / 2


def _p90(values):
    v = sorted(values)
    return v[min(len(v) - 1, int(len(v) * 0.9))] if v else None


def _secs(ms_list):
    return round(sum(ms_list) / len(ms_list) / 1000, 1) if ms_list else None


def _insight_stats(users, sets, attempts, active, exclude_emails, start: date, today: date) -> dict:
    """Engagement, drop-off and AI-quality signals for the period."""
    excluded_ids = {u.id for u in User.query.all() if (u.email or "").lower() in exclude_emails}
    in_period = lambda dt: dt is not None and local_day(dt) >= start  # noqa: E731
    ev = [e for e in SiteEvent.query.order_by(SiteEvent.created_at).all()
          if e.user_id not in excluded_ids and in_period(e.created_at)]
    by_kind = defaultdict(list)
    for e in ev:
        by_kind[e.kind].append((e, parse_kv(e.detail)))
    email_of = {u.id: u.email for u in users}
    title_of = {st.id: st.title for st in sets}

    # --- Quiz engagement ---------------------------------------------------------
    starts, dones, quits = by_kind["quiz_start"], by_kind["quiz_done"], by_kind["quiz_abandon"]
    modes = ["full", "part", "notes", "missed", "shared", "mock", "weak"]
    mode_labels = {"full": "Whole quiz", "part": "Chosen number of questions", "notes": "Notes only",
                   "missed": "Retry missed", "shared": "Shared link", "mock": "Mock exam", "weak": "Weak spots"}
    start_by_mode = Counter(d.get("mode", "full") for _, d in starts)
    quit_by_mode = Counter({"quiz": "full"}.get(d.get("mode"), d.get("mode", "full")) for _, d in quits)
    mode_rows = [{"mode": mode_labels.get(m, m), "started": start_by_mode.get(m, 0), "left": quit_by_mode.get(m, 0)}
                 for m in modes if start_by_mode.get(m) or quit_by_mode.get(m)]
    for r in mode_rows:
        r["left_pct"] = _pct(r["left"], r["started"])

    quit_points = Counter()
    quit_kinds = Counter()
    for _, d in quits:
        answered, of = int(d.get("answered", 0) or 0), int(d.get("of", 0) or 0)
        if d.get("stage") == "notes" and answered == 0:
            quit_points["While reading the notes"] += 1
        elif of == 0:
            quit_points["Notes-only reading"] += 1
        else:
            frac = answered / of
            label = ("Before answering anything" if answered == 0 else "In the first quarter" if frac < .25
                     else "In the second quarter" if frac < .5 else "In the third quarter" if frac < .75
                     else "Near the end")
            quit_points[label] += 1
        if d.get("qkind"):
            quit_kinds[d["qkind"]] += 1
    point_order = ["While reading the notes", "Before answering anything", "In the first quarter",
                   "In the second quarter", "In the third quarter", "Near the end", "Notes-only reading"]
    quit_rows = [{"label": p, "n": quit_points[p]} for p in point_order if quit_points.get(p)]

    durations = [int(d["secs"]) for _, d in dones if d.get("secs", "").isdigit()]
    per_q = [int(d["secs"]) / max(1, int(d.get("n", 1) or 1)) for _, d in dones
             if d.get("secs", "").isdigit() and d.get("n", "").isdigit()]

    # --- Retention by sign-up week ------------------------------------------------
    def week_start(d):
        return d - timedelta(days=d.weekday())
    cohorts = defaultdict(list)
    for u in users:
        cohorts[week_start(local_day(u.created_at))].append(u)
    cohort_rows = []
    for wk in sorted(cohorts, reverse=True)[:10]:
        members = cohorts[wk]
        row = {"week": wk, "size": len(members), "cells": []}
        for k in range(5):
            lo, hi = wk + timedelta(days=7 * k), wk + timedelta(days=7 * k + 6)
            if lo > today:
                row["cells"].append(None)
                continue
            back = sum(1 for u in members if any(lo <= d <= hi for d in active[u.id] - ({local_day(u.created_at)} if k == 0 else set())))
            row["cells"].append(_pct(back, len(members)))
        cohort_rows.append(row)

    # --- Gone quiet: users not seen for a week, and the last thing they did -----------
    last_event = {}
    for e in SiteEvent.query.filter(SiteEvent.user_id.isnot(None)).order_by(SiteEvent.created_at).all():
        if e.kind != "landing":
            last_event[e.user_id] = e
    labels = {"quiz_abandon": "Left a quiz part-way", "quiz_done": "Finished a quiz", "quiz_start": "Started a quiz",
              "notes_made": "Made notes", "quiz_made": "Generated a quiz", "notes_edit": "Edited notes",
              "error_upload": "Upload was rejected", "error_ai": "Hit an AI error", "q_report": "Reported a question",
              "card_edit": "Edited questions", "card_delete": "Deleted questions", "ai_edit_done": "Used Simplify/Improve",
              "share_open": "Opened a shared quiz", "ai_undo": "Undid an AI edit"}
    quiet = []
    for u in users:
        last = max(active[u.id]) if active[u.id] else None
        if last and (today - last).days >= 7:
            e = last_event.get(u.id)
            quiet.append({"id": u.id, "email": u.email, "joined": local_day(u.created_at), "last_active": last,
                          "days_away": (today - last).days, "active_days": len(active[u.id]),
                          "last_did": labels.get(e.kind, e.kind) if e else "–"})
    quiet.sort(key=lambda r: r["days_away"])

    # --- AI quality --------------------------------------------------------------------
    made = by_kind["notes_made"]
    made_sets = {d.get("set") for _, d in made}
    edits_before_quiz = defaultdict(lambda: {"changed": 0, "added": 0, "removed": 0, "saves": 0})
    for _, d in by_kind["notes_edit"]:
        if d.get("quiz") == "0":
            row = edits_before_quiz[d.get("set")]
            row["saves"] += 1
            for k in ("changed", "added", "removed"):
                row[k] += int(d.get(k, 0) or 0)
    edited_sets = [sid for sid in made_sets if sid in edits_before_quiz]
    points_made = {d.get("set"): int(d.get("points", 0) or 0) for _, d in made}
    removed_share = [min(100, round(edits_before_quiz[sid]["removed"] / points_made[sid] * 100))
                     for sid in edited_sets if points_made.get(sid)]
    sources = Counter(d.get("src", "?") for _, d in made)
    pages = [int(d["pages"]) for _, d in made if d.get("pages", "").isdigit()]
    quiz_made = by_kind["quiz_made"]
    regen = [d for _, d in quiz_made if d.get("gen", "1").isdigit() and int(d["gen"]) > 1]
    ai_edits = Counter(d.get("mode") for _, d in by_kind["ai_edit_done"])
    undos = Counter(d.get("mode") for _, d in by_kind["ai_undo"])
    shrink = [1 - int(d["after"]) / int(d["before"]) for _, d in by_kind["ai_edit_done"]
              if d.get("mode") == "simplify" and d.get("before", "0").isdigit() and int(d["before"]) > 0]

    edits_kind = Counter(d.get("kind") for _, d in by_kind["card_edit"])
    deletes_kind = Counter(d.get("kind") for _, d in by_kind["card_delete"])
    reports_kind = Counter(d.get("kind") for _, d in by_kind["q_report"])
    reasons = Counter(d.get("reason") for _, d in by_kind["q_report"])
    reason_labels = {"wrong": "Answer is wrong", "unclear": "Question is unclear", "not_in_notes": "Not in my notes",
                     "too_easy": "Too easy", "other": "Something else"}
    reports = [{"when": e.created_at, "who": email_of.get(e.user_id, "–"), "set_id": int(d["set"]) if d.get("set", "").isdigit() else None,
                "title": title_of.get(int(d["set"])) if d.get("set", "").isdigit() else None,
                "kind": d.get("kind"), "reason": reason_labels.get(d.get("reason"), d.get("reason"))}
               for e, d in reversed(by_kind["q_report"][-30:])]

    def ms_of(kind):
        return [int(d["ms"]) for _, d in by_kind[kind] if d.get("ms", "").isdigit()]
    speed = [
        {"label": "Writing notes from an upload", "n": len(ms_of("notes_made")), "avg": _secs(ms_of("notes_made")),
         "p90": round(_p90(ms_of("notes_made")) / 1000, 1) if ms_of("notes_made") else None},
        {"label": "Writing a quiz", "n": len(ms_of("quiz_made")), "avg": _secs(ms_of("quiz_made")),
         "p90": round(_p90(ms_of("quiz_made")) / 1000, 1) if ms_of("quiz_made") else None},
        {"label": "Simplify / Improve", "n": len(ms_of("ai_edit_done")), "avg": _secs(ms_of("ai_edit_done")),
         "p90": round(_p90(ms_of("ai_edit_done")) / 1000, 1) if ms_of("ai_edit_done") else None},
    ]
    ai_calls = len(made) + len(quiz_made) + len(by_kind["ai_edit_done"])
    ai_fail = len(by_kind["error_ai"]) + len(by_kind["error_demo"])

    return {
        "eng": {
            "started": len(starts), "finished": len(dones), "left": len(quits),
            "finish_pct": _pct(len(dones), len(starts)),
            "median_secs": _median(durations), "secs_per_q": round(_median(per_q)) if per_q else None,
            "mode_rows": mode_rows, "quit_rows": quit_rows, "quit_max": max([r["n"] for r in quit_rows] + [1]),
            "quit_kinds": quit_kinds,
        },
        "cohorts": cohort_rows,
        "quiet": quiet,
        "quality": {
            "sets_made": len(made), "edited_pct": _pct(len(edited_sets), len(made_sets)),
            "removed_pct": round(sum(removed_share) / len(removed_share)) if removed_share else None,
            "avg_points": round(sum(points_made.values()) / len(points_made)) if points_made else None,
            "sources": sorted(sources.items(), key=lambda kv_: -kv_[1]),
            "avg_pages": round(sum(pages) / len(pages)) if pages else None,
            "quizzes_made": len(quiz_made), "regen_pct": _pct(len(regen), len(quiz_made)),
            "simplify": ai_edits.get("simplify", 0), "improve": ai_edits.get("improve", 0),
            "simplify_undo_pct": _pct(undos.get("simplify", 0), ai_edits.get("simplify", 0)),
            "improve_undo_pct": _pct(undos.get("improve", 0), ai_edits.get("improve", 0)),
            "simplify_cut_pct": round(sum(shrink) / len(shrink) * 100) if shrink else None,
            "edits_kind": edits_kind, "deletes_kind": deletes_kind, "reports_kind": reports_kind,
            "reasons": [(reason_labels.get(k, k), v) for k, v in reasons.most_common()],
            "reports": reports, "speed": speed,
            "ai_calls": ai_calls, "ai_fail": ai_fail, "fail_pct": _pct(ai_fail, ai_calls + ai_fail),
        },
    }
