from flask import Blueprint, redirect, url_for, render_template
from flask_dance.contrib.google import google

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/")
def home():
    if not google.authorized:
        return render_template("index.html")
    return redirect(url_for("main.sets"))
