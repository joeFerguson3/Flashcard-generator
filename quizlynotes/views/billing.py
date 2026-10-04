"""Pricing page, Stripe checkout / portal / webhook, promo codes, referrals."""
from __future__ import annotations

import logging

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_login import current_user, login_required

from .. import billing
from ..extensions import csrf, db
from ..models import User
from ..sanitize import clean_text

log = logging.getLogger(__name__)

billing_bp = Blueprint("billing", __name__)

PRICING_FAQ = [
    ("Is QuizlyNotes really free?",
     "Yes. Studying is unlimited on the free plan: quizzes, flashcards, spaced repetition and games, with "
     "no caps on how much you revise. The free plan includes 5 new AI study sets every month."),
    ("What do I get with Pro?",
     "Unlimited AI study sets, bigger uploads (up to 150-page PDFs), up to 60 questions per quiz, unlimited "
     "Simplify and Improve for your notes, mock exams that mix every set in a subject, and a Weak spots review "
     "of the questions you keep getting wrong."),
    ("Is there a free trial?",
     "Every new account gets 7 days of Pro free, no card needed. If a friend invites you, you get 14 days."),
    ("Can I cancel any time?",
     "Yes. Cancel in a couple of clicks from Settings. You keep Pro until the end of the period you've paid "
     "for, and all your sets stay in your account on the free plan."),
    ("What happens to my sets if I go back to free?",
     "Nothing is deleted. You can keep studying every set you've made; only new AI generations are limited."),
    ("Do you offer discounts?",
     "The yearly plan is half the price of paying monthly. You can also earn free Pro weeks by inviting friends."),
]


def _plain(obj):
    """Stripe objects aren't dicts in stripe-python 13+; convert for .get()."""
    to_dict = getattr(obj, "to_dict", None)
    return to_dict() if callable(to_dict) else obj


@billing_bp.route("/pricing")
def pricing():
    status = billing.plan_status(current_user) if current_user.is_authenticated else None
    return render_template(
        "public/pricing.html", status=status, free=billing.FREE, pro=billing.PRO,
        stripe_on=billing.stripe_enabled(), faq=PRICING_FAQ, feature=request.args.get("feature"),
    )


@billing_bp.route("/billing/checkout", methods=["POST"])
@login_required
def checkout():
    if not billing.stripe_enabled():
        flash("Payments aren't open yet. Have a code? Redeem it below.", "info")
        return redirect(url_for("billing.pricing"))
    interval = "year" if request.form.get("interval") == "year" else "month"
    cfg = current_app.config
    price = cfg["STRIPE_PRICE_YEARLY"] if interval == "year" else cfg["STRIPE_PRICE_MONTHLY"]
    user = current_user._get_current_object()
    params = {
        "mode": "subscription",
        "line_items": [{"price": price, "quantity": 1}],
        "success_url": cfg["SITE_URL"] + url_for("billing.success") + "?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": cfg["SITE_URL"] + url_for("billing.pricing"),
        "client_reference_id": str(user.id),
        "allow_promotion_codes": True,
        "subscription_data": {"metadata": {"user_id": str(user.id)}},
        "metadata": {"user_id": str(user.id)},
    }
    if user.stripe_customer_id:
        params["customer"] = user.stripe_customer_id
    else:
        params["customer_email"] = user.email
    try:
        session_obj = billing.stripe_client().v1.checkout.sessions.create(params)
    except Exception as exc:  # pragma: no cover - network
        log.error("Stripe checkout failed: %s", exc)
        flash("We couldn't start checkout. Please try again.", "error")
        return redirect(url_for("billing.pricing"))
    return redirect(session_obj.url, code=303)


@billing_bp.route("/billing/success")
@login_required
def success():
    # Apply the subscription immediately; the webhook does the same thing.
    session_id = request.args.get("session_id", "")
    if session_id and billing.stripe_enabled():
        try:
            client = billing.stripe_client()
            cs = _plain(client.v1.checkout.sessions.retrieve(session_id))
            if cs.get("client_reference_id") == str(current_user.id) and cs.get("subscription"):
                sub = _plain(client.v1.subscriptions.retrieve(cs["subscription"]))
                billing.apply_subscription(current_user, sub)
                db.session.commit()
        except Exception as exc:  # pragma: no cover - network
            log.warning("Could not confirm checkout %s: %s", session_id, exc)
    flash("Welcome to QuizlyNotes Pro! Thanks for supporting the site.", "success")
    return redirect(url_for("study.library"))


@billing_bp.route("/billing/portal", methods=["POST"])
@login_required
def portal():
    if not (billing.stripe_enabled() and current_user.stripe_customer_id):
        return redirect(url_for("study.settings"))
    try:
        portal_session = billing.stripe_client().v1.billing_portal.sessions.create({
            "customer": current_user.stripe_customer_id,
            "return_url": current_app.config["SITE_URL"] + url_for("study.settings"),
        })
    except Exception as exc:  # pragma: no cover - network
        log.error("Stripe portal failed: %s", exc)
        flash("We couldn't open billing right now. Please try again.", "error")
        return redirect(url_for("study.settings"))
    return redirect(portal_session.url, code=303)


@billing_bp.route("/billing/webhook", methods=["POST"])
@csrf.exempt
def webhook():
    secret = current_app.config["STRIPE_WEBHOOK_SECRET"]
    if not secret:
        abort(404)
    import stripe

    try:
        event = stripe.Webhook.construct_event(
            request.get_data(), request.headers.get("Stripe-Signature"), secret
        )
    except Exception:
        return jsonify(error="invalid signature"), 400

    kind = event["type"]
    obj = _plain(event["data"]["object"])
    user = None
    if kind == "checkout.session.completed":
        user_id = obj.get("client_reference_id") or (obj.get("metadata") or {}).get("user_id")
        user = db.session.get(User, int(user_id)) if user_id and str(user_id).isdigit() else None
        if user and obj.get("customer"):
            user.stripe_customer_id = obj["customer"]
        if user and obj.get("subscription") and billing.stripe_enabled():
            try:
                sub = _plain(billing.stripe_client().v1.subscriptions.retrieve(obj["subscription"]))
                billing.apply_subscription(user, sub)
            except Exception as exc:  # pragma: no cover - network
                log.warning("Could not fetch subscription: %s", exc)
    elif kind in ("customer.subscription.created", "customer.subscription.updated",
                  "customer.subscription.deleted"):
        meta_id = (obj.get("metadata") or {}).get("user_id")
        if meta_id and str(meta_id).isdigit():
            user = db.session.get(User, int(meta_id))
        if user is None and obj.get("customer"):
            user = User.query.filter_by(stripe_customer_id=obj["customer"]).first()
        if user:
            billing.apply_subscription(user, obj)
    if user is not None:
        db.session.commit()
        log.info("Stripe %s applied to user %s", kind, user.id)
    return jsonify(received=True)


@billing_bp.route("/redeem", methods=["POST"])
@login_required
def redeem():
    code = clean_text(request.form.get("code"), 64)
    try:
        message = billing.redeem(current_user, code)
        db.session.commit()
        flash(message, "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    return redirect(request.form.get("next") or url_for("study.settings"))


@billing_bp.route("/r/<code>")
def referral(code: str):
    """Invite link: remember who invited this visitor, then show the home page."""
    referrer = User.query.filter_by(referral_code=code.lower()[:16]).first()
    if referrer and not (current_user.is_authenticated and current_user.id == referrer.id):
        session["ref"] = referrer.referral_code
        if not current_user.is_authenticated:
            flash(f"{referrer.display_name.split(' ')[0]} invited you: sign up and get 14 days of Pro free.", "success")
    return redirect(url_for("public.home"))
