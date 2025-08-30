from flask import Blueprint, render_template
from models import Flashcard

main_bp = Blueprint("main", __name__)

@main_bp.route("/sets")
def sets():
    flashcards = Flashcard.query.all()
    return render_template("sets.html", flashcards=flashcards)
