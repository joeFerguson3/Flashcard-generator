from flask import Blueprint, render_template, request, redirect
from utils.pdf_utils import extract_text
from models import Flashcard
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

@flashcards_bp.route("/flashcards")
def flashcards():
    flashcards = extract_text()
    return render_template("flashcards.html", flashcards=flashcards)

@flashcards_bp.route("/save-flashcards", methods=["POST"])
def save_flashcards():
    data = json.loads(request.form['flashcards'])
    for card in data["questions"]:
        new_card = Flashcard(question=card["question"], answer=card["answer"])
        db.session.add(new_card)
    db.session.commit()
    return redirect("/sets")
