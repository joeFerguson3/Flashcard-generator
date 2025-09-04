from flask import Blueprint, render_template, request, redirect, session
from utils.pdf_utils import extract_text
from utils.notes import parse_notes
from utils.ai_utils import question
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

    # Checks if editing or creating new set
    if('set_id' in session):
        # Update set name
        set_id = session['set_id']
        set = FlashcardSet.query.filter_by(id=set_id).first()
        set.name = request.form.get("set_name")
        db.session.commit()
        session.pop('set_id')

        # Update flashcard values
        flashcards = Flashcard.query.filter_by(set_id=set_id).all()
        flashcard_ids = [card.id for card in flashcards]
        i = 1
        while True:
            question = request.form.get(f"question-{i}")
            answer = request.form.get(f"answer-{i}")
            print(answer)
            if not question or not answer:
                print("empty")
                break
           
            if(i < len(flashcard_ids)):
                flashcard = Flashcard.query.get(flashcard_ids[i - 1])
                flashcard.question = question
                flashcard.answer = answer
            else:
                new_card = Flashcard(question=question, answer=answer, set_id=set_id)
                db.session.add(new_card)
            i += 1

        db.session.commit()
    else:
        # Create new flashcard set
        flashcard_set = FlashcardSet(name=request.form.get("set_name"), user_id=session["user_id"])
        db.session.add(flashcard_set)
        db.session.commit()

        set_id = flashcard_set.id
        i = 1
        while True:
            question = request.form.get(f"question-{i}")
            answer = request.form.get(f"answer-{i}")
            if not question or not answer:
                break
            new_card = Flashcard(question=question, answer=answer, set_id=set_id)
            db.session.add(new_card)
            i += 1

        db.session.commit()

    return redirect("/sets")

# Edit flashcard set
@flashcards_bp.route("/edit-set", methods=["POST"])
def flashcards_edit():
    set_id = request.form.get('set-id')
    set_name = request.form.get('set-name')

    # Get flash cards
    flashcards = Flashcard.query.filter_by(set_id=set_id).all()
    flashcards_data = [
        {"question": f.question, "answer": f.answer}
        for f in flashcards
    ]

    flashcards = {"questions": json.loads(json.dumps(flashcards_data))}

    session['set_id'] = set_id
    return render_template("flashcards.html", flashcards=flashcards, set_name=set_name)
    
@flashcards_bp.route("/notes")
def notes():
    return render_template("notes.html", sections=parse_notes())

@flashcards_bp.route("/generate-quiz", methods=["POST"])
def save_notes():
    
    questions = []
    # Compiles notes together
    # data = json.loads(request.form.get("notes"))
    data = [
  {
    "content": ["- Key Topics:", "  - What is intelligence?", "  - Brains and computers"],
    "main_title": "Anatomy of the Eye",
    "sub_title": "The Psychology of AI"
  },
  {
    "content": ["- Human retina:", "  - 120 million rod cells", "  - 6 million cone cells"],
    "main_title": "Anatomy of the Eye",
    "sub_title": "Structure"
  },
  {
    "content": ["- Topic:", "  - Cognitive science basics", "  - AI applications"],
    "main_title": "Cognitive Science",
    "sub_title": "Introduction"
  }
]

    # for d in data:
    #     main = d.get("main_title", "")
    #     sub = d.get("sub_title", "")
    #     content = "\n".join(d.get("content", []))
    #     formatted_text = f"{main} - {sub}\n{content}"
    #     # questions.append(question(formatted_text, main))

    return render_template("quiz.html", data=data, questions=questions)