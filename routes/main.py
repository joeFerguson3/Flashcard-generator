from flask import Blueprint, render_template, session
from models import FlashcardSet

main_bp = Blueprint("main", __name__)

@main_bp.route("/sets")
def sets():
    
    user_id = session.get("user_id")
    flashcards = FlashcardSet.query.filter_by(user_id=user_id).all()
    
      # Optional: print each set's name
    for card_set in flashcards:
        print(card_set.name)
    return render_template("sets.html", flashcards=flashcards)
