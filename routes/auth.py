from flask import Blueprint, redirect, url_for, render_template, session
from flask_dance.contrib.google import google
from models import User
from extensions import db

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/")
def home():
    session["user_id"] = 1  # Simulate a logged-in user for testing
    session["user-id"] = session["user_id"]
    simulated_user = User.query.get(session["user_id"])
    if simulated_user:
        session["user_email"] = simulated_user.email
    if('user_id' in session):
        return redirect("/home")
    if not google.authorized:
        return render_template("index.html")
    # Get user info from Google
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return "Failed to fetch user info", 400

    user_info = resp.json()
    email = user_info["email"]

    # Check if user already exists
    user = User.query.filter_by(email=email).first()

    if not user:
        # Signup: create new user
        user = User(
            email=email,
            name=user_info.get("name"),
            picture=user_info.get("picture"),
        )
        db.session.add(user)
        db.session.commit()

    # Save user ID in session (logged in)
    session["user_id"] = user.id
    session["user-id"] = user.id
    session["user_email"] = user.email

    return redirect("/home")


@auth_bp.route("/delete_account", methods=["POST"])
def delete_account():
    user_id = session.get("user_id") or session.get("user-id")
    if not user_id:
        return redirect(url_for("auth.home"))

    user = User.query.get(user_id)

    if user:
        for note_set in list(user.note_sets):
            db.session.delete(note_set)
        for flashcard_set in list(user.flashcard_sets):
            db.session.delete(flashcard_set)
        db.session.delete(user)
        db.session.commit()

    session.clear()
    return redirect(url_for("auth.home"))


@auth_bp.route("/settings")
def settings():
    user_id = session.get("user_id") or session.get("user-id")
    if not user_id:
        return redirect(url_for("auth.home"))

    user = User.query.get(user_id)
    if not user:
        session.clear()
        return redirect(url_for("auth.home"))

    if user.email and not session.get("user_email"):
        session["user_email"] = user.email

    return render_template("settings.html", user=user)
