from flask import Blueprint, render_template, request, redirect, session
from utils.pdf_utils import extract_text
from models import Flashcard, FlashcardSet
from extensions import db  
import json

flashcards_bp = Blueprint("flashcards", __name__)

@flashcards_bp.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files.get("pdfUpload")
        if not file or not file.filename.endswith(".pdf"):
            return "Invalid file type."
        return redirect("/flashcards")
    return render_template("pdf-upload.html")

# Creates flash cards from uploaded pdf
@flashcards_bp.route("/flashcards")
def flashcards():
    flashcards = extract_text()
    flashcards = {"questions": flashcards}
    return render_template("flashcards.html", flashcards=flashcards)

# Saves flashcards to database
@flashcards_bp.route("/save-flashcards", methods=["POST"])
def save_flashcards():
    flashcard_set = FlashcardSet(name="test name", user_id=session["user_id"])
    db.session.add(flashcard_set)
    db.session.commit()


    data = json.loads(request.form['flashcards'])
    for card in data["questions"]:
        new_card = Flashcard(question=card["question"], answer=card["answer"], set_id=flashcard_set.id)
        db.session.add(new_card)
    db.session.commit()

    return redirect("/sets")

# Edit flashcard set
@flashcards_bp.route("/edit-set", methods=["POST"])
def flashcards_edit():
    set_id = request.form.get('set-id')

    # Get flash cards
    flashcards = Flashcard.query.filter_by(set_id=set_id).all()
    flashcards_data = [
        {"question": f.question, "answer": f.answer}
        for f in flashcards
    ]

    flashcards = {"questions": json.loads(json.dumps(flashcards_data))}

    return render_template("flashcards.html", flashcards=flashcards)
    