"""Plans, limits and entitlements.

Free keeps studying unlimited and caps AI usage (the expensive part).
Pro removes the caps and unlocks cross-set study tools.

Pro access comes from any of: ADMIN_EMAILS, a lifetime promo code, or
`pro_until` in the future (signup trial, referral bonus, day-based promo
code, or a paid Stripe period).
"""
from __future__ import annotations

import hashlib
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta

from flask import current_app

from .extensions import db
from .models import PromoCode, PromoRedemption, UsageEvent, User, utcnow


@dataclass(frozen=True)
class Limits:
    sets_per_month: int
    regenerations_per_set: int | None  # None = unlimited
    ai_edits_per_month: int
    max_pages: int
    max_upload_mb: int
    max_questions: int
    max_text_chars: int
    mock_exam: bool
    weak_spots: bool


FREE = Limits(
    sets_per_month=5, regenerations_per_set=2, ai_edits_per_month=15,
    max_pages=30, max_upload_mb=10, max_questions=15, max_text_chars=60_000,
    mock_exam=False, weak_spots=False,
)
# "Unlimited" in the UI; generous fair-use caps protect against abuse.
PRO = Limits(
    sets_per_month=300, regenerations_per_set=None, ai_edits_per_month=1000,
    max_pages=150, max_upload_mb=30, max_questions=60, max_text_chars=300_000,
    mock_exam=True, weak_spots=True,
)


class LimitReached(Exception):
    """Raised when a free-plan limit blocks an action."""

    def __init__(self, message: str, feature: str):
        super().__init__(message)
        self.message = message
        self.feature = feature


# --- Entitlements -----------------------------------------------------------

def enabled() -> bool:
    """Whether plans and payments are switched on (MONETISATION_ENABLED)."""
    return bool(current_app.config.get("MONETISATION_ENABLED", True))


def is_admin(user: User) -> bool:
    return bool(user and user.email and user.email.lower() in current_app.config["ADMIN_EMAILS"])


def is_pro(user: User | None) -> bool:
    if user is None or not getattr(user, "is_authenticated", True):
        return False
    if not enabled():
        return True
    if user.lifetime_pro or is_admin(user):
        return True
    return bool(user.pro_until and user.pro_until > utcnow())


def limits_for(user: User | None) -> Limits:
    return PRO if is_pro(user) else FREE


def plan_status(user: User) -> dict:
    """Everything templates need to show plan state."""
    now = utcnow()
    pro = is_pro(user)
    if not enabled():
        lim = PRO
        return {"enabled": False, "pro": True, "paid": False, "lifetime": False, "on_trial": False,
                "days_left": None, "pro_until": None, "interval": None, "cancel_pending": False,
                "limits": lim, "sets_used": 0, "sets_left": lim.sets_per_month, "edits_used": 0,
                "resets_on": next_month_start(now)}
    paid = user.subscription_status in ("active", "trialing", "past_due", "canceling")
    on_trial = pro and not paid and not user.lifetime_pro and not is_admin(user) and bool(
        user.trial_started_at and user.pro_until and user.pro_until > now
    )
    days_left = None
    if pro and user.pro_until and not user.lifetime_pro and not is_admin(user):
        days_left = max(0, (user.pro_until - now).days + (1 if (user.pro_until - now).seconds else 0))
    lim = limits_for(user)
    used = sets_this_month(user)
    return {
        "enabled": True,
        "pro": pro,
        "paid": paid,
        "lifetime": user.lifetime_pro or is_admin(user),
        "on_trial": on_trial,
        "days_left": days_left,
        "pro_until": user.pro_until,
        "interval": user.subscription_interval,
        "cancel_pending": user.subscription_status == "canceling",
        "limits": lim,
        "sets_used": used,
        "sets_left": max(0, lim.sets_per_month - used),
        "edits_used": usage_this_month(user, "ai_edit"),
        "resets_on": next_month_start(now),
    }


def extend_pro(user: User, days: int) -> None:
    start = max(user.pro_until or utcnow(), utcnow())
    user.pro_until = start + timedelta(days=days)


def start_trial(user: User, referred: bool = False) -> None:
    if user.trial_started_at is not None or not enabled():
        return
    cfg = current_app.config
    user.trial_started_at = utcnow()
    extend_pro(user, cfg["REFERRED_TRIAL_DAYS"] if referred else cfg["TRIAL_DAYS"])


# --- Usage ----------------------------------------------------------------------

def month_start(now: datetime | None = None) -> datetime:
    now = now or utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def next_month_start(now: datetime | None = None) -> datetime:
    start = month_start(now)
    return (start + timedelta(days=32)).replace(day=1)


def usage_this_month(user: User, kind: str) -> int:
    return UsageEvent.query.filter(
        UsageEvent.user_id == user.id, UsageEvent.kind == kind,
        UsageEvent.created_at >= month_start(),
    ).count()


def sets_this_month(user: User) -> int:
    return usage_this_month(user, "new_set")


def record(user: User, kind: str) -> None:
    db.session.add(UsageEvent(user_id=user.id, kind=kind))


def upgrade_hint(user: User) -> str:
    return "Upgrade to Pro" if not is_pro(user) else ""


def check_new_set(user: User) -> None:
    lim = limits_for(user)
    if sets_this_month(user) >= lim.sets_per_month:
        if is_pro(user):
            raise LimitReached("You've reached this month's fair-use limit. It resets on the 1st.", "sets")
        raise LimitReached(
            f"You've used your {lim.sets_per_month} free study sets this month. "
            "Upgrade to Pro for unlimited sets, or wait until it resets on the 1st.", "sets")


def check_regenerate(user: User, study_set) -> None:
    lim = limits_for(user)
    # The first generation is part of creating the set; later ones are regenerations.
    if lim.regenerations_per_set is not None and study_set.generations > lim.regenerations_per_set:
        raise LimitReached(
            f"Free accounts can regenerate a quiz {lim.regenerations_per_set} times per set. "
            "Upgrade to Pro for unlimited regenerations.", "regenerate")


def check_ai_edit(user: User) -> None:
    lim = limits_for(user)
    if usage_this_month(user, "ai_edit") >= lim.ai_edits_per_month:
        if is_pro(user):
            raise LimitReached("You've reached this month's fair-use limit for AI edits. It resets on the 1st.", "ai_edit")
        raise LimitReached(
            f"You've used your {lim.ai_edits_per_month} free AI note edits this month. "
            "Upgrade to Pro for unlimited Simplify and Improve.", "ai_edit")


def check_feature(user: User, feature: str) -> None:
    if not getattr(limits_for(user), feature):
        names = {"mock_exam": "Mock exams", "weak_spots": "Weak spots review"}
        raise LimitReached(f"{names.get(feature, 'This feature')} is part of QuizlyNotes Pro.", feature)


# --- Promo codes ------------------------------------------------------------

def hash_code(code: str) -> str:
    normalised = "".join(code.split()).upper()
    return hashlib.sha256(normalised.encode()).hexdigest()


def create_promo(label: str, days: int | None = None, max_redemptions: int | None = None,
                 code: str | None = None, expires_at: datetime | None = None) -> tuple[PromoCode, str]:
    if code is None:
        alphabet = string.ascii_uppercase + string.digits
        code = "QN-" + "".join(secrets.choice(alphabet) for _ in range(4)) + "-" + \
            "".join(secrets.choice(alphabet) for _ in range(4))
    promo = PromoCode(code_hash=hash_code(code), label=label, days=days,
                      max_redemptions=max_redemptions, expires_at=expires_at)
    db.session.add(promo)
    db.session.flush()
    return promo, code


def redeem(user: User, code: str) -> str:
    """Apply a promo code. Returns a message; raises ValueError if invalid."""
    promo = PromoCode.query.filter_by(code_hash=hash_code(code or ""), active=True).first()
    if promo is None or (promo.expires_at and promo.expires_at < utcnow()):
        raise ValueError("That code isn't valid.")
    if PromoRedemption.query.filter_by(code_id=promo.id, user_id=user.id).first():
        raise ValueError("You've already used this code.")
    if promo.max_redemptions is not None and promo.redemptions >= promo.max_redemptions:
        raise ValueError("This code has been fully used.")
    promo.redemptions += 1
    db.session.add(PromoRedemption(code_id=promo.id, user_id=user.id))
    if promo.days is None:
        user.lifetime_pro = True
        return "Code applied: you have Pro for life."
    extend_pro(user, promo.days)
    return f"Code applied: {promo.days} days of Pro added."


# --- Referrals ----------------------------------------------------------------

def ensure_referral_code(user: User) -> str:
    if not user.referral_code:
        alphabet = string.ascii_lowercase + string.digits
        while True:
            candidate = "".join(secrets.choice(alphabet) for _ in range(7))
            if not User.query.filter_by(referral_code=candidate).first():
                break
        user.referral_code = candidate
    return user.referral_code


def reward_referrer(user: User) -> None:
    """Called when a referred user creates their first set (anti-abuse)."""
    if not enabled() or not user.referred_by_id or user.referral_rewarded:
        return
    referrer = db.session.get(User, user.referred_by_id)
    user.referral_rewarded = True
    if referrer is None:
        return
    cfg = current_app.config
    # Cap how far ahead referral rewards can push Pro.
    horizon = utcnow() + timedelta(days=cfg["REFERRAL_MAX_REWARD_DAYS"])
    if referrer.pro_until and referrer.pro_until >= horizon:
        return
    extend_pro(referrer, cfg["REFERRAL_REWARD_DAYS"])
    if referrer.pro_until > horizon:
        referrer.pro_until = horizon


def referral_count(user: User) -> int:
    return User.query.filter_by(referred_by_id=user.id, referral_rewarded=True).count()


# --- Stripe -------------------------------------------------------------------

def stripe_enabled() -> bool:
    cfg = current_app.config
    return bool(cfg["STRIPE_SECRET_KEY"] and cfg["STRIPE_PRICE_MONTHLY"] and cfg["STRIPE_PRICE_YEARLY"])


def stripe_client():
    import stripe

    return stripe.StripeClient(current_app.config["STRIPE_SECRET_KEY"])


def _get(obj, key, default=None):
    try:
        value = obj[key]
    except (KeyError, TypeError, IndexError):
        value = getattr(obj, key, default)
    return default if value is None else value


def _period_end(subscription) -> datetime | None:
    end = _get(subscription, "current_period_end")
    if not end:  # newer API versions keep it on the subscription item
        items = _get(_get(subscription, "items", {}), "data", []) or []
        if items:
            end = _get(items[0], "current_period_end")
    return datetime.utcfromtimestamp(int(end)) if end else None


def apply_subscription(user: User, subscription) -> None:
    """Sync a Stripe subscription object onto the user."""
    status = _get(subscription, "status", "")
    user.stripe_subscription_id = _get(subscription, "id")
    customer = _get(subscription, "customer")
    if customer:
        user.stripe_customer_id = customer if isinstance(customer, str) else _get(customer, "id")
    items = _get(_get(subscription, "items", {}), "data", []) or []
    if items:
        interval = _get(_get(_get(items[0], "price", {}), "recurring", {}), "interval")
        user.subscription_interval = interval
    if status in ("active", "trialing", "past_due") and _get(subscription, "cancel_at_period_end", False):
        status = "canceling"
    user.subscription_status = status
    end = _period_end(subscription)
    if end and status in ("active", "trialing", "past_due", "canceling"):
        # Small grace period so renewals never cause a gap.
        grace = end + timedelta(days=2)
        if not user.pro_until or user.pro_until < grace:
            user.pro_until = grace
