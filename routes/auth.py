from flask import Blueprint, redirect, url_for, render_template, session
from flask_dance.contrib.google import google
from models import User
from extensions import db

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/")
def home():
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

    return redirect("/home")
