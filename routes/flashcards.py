from flask import Blueprint, render_template, request, redirect, session, url_for
from utils.pdf_utils import extract_text
from utils.notes import parse_notes
from utils.ai_utils import question, extract_definitions
from utils.sanitization import sanitize_text, sanitize_structure
from models import Flashcard, FlashcardSet, Note, NoteSet, Question
from extensions import db  
import json
import random
from concurrent.futures import ThreadPoolExecutor
flashcards_bp = Blueprint("flashcards", __name__)

@flashcards_bp.route("/upload", methods=["GET", "POST"])
def upload():
    if "user_id" not in session:
        return redirect("/")
    if request.method == "POST":
        file = request.files.get("pdfUpload")
        if not file or not file.filename.endswith(".pdf"):
            return "Invalid file type."
        
        file.seek(0, 2)  # move to end
        size = file.tell()
        file.seek(0)
        if size > 25 * 1024 * 1024:
            return "File too large. Limit is 25 MB."

        notes = extract_text(file)
        notes = sanitize_structure(notes, max_length=4096)
        return render_template("notes.html", data=notes)

    return render_template("pdf-upload.html")

# # Creates flash cards from uploaded pdf
# @flashcards_bp.route("/flashcards")
# def flashcards():
#     notes = extract_text(file)
#     # flashcards = {"questions": flashcards}
#     if('notes' in session):
#         notes = session['notes']
#         return render_template("notes.html", data=notes)
    
    
#     return render_template("notes.html", data=notes)

# Saves flashcards to database
@flashcards_bp.route("/save-flashcards", methods=["POST"])
def save_flashcards():
    if "user_id" not in session:
        return redirect("/")

    # Checks if editing or creating new set
    if('set_id' in session):
        # Update set name
        set_id = session['set_id']
        set = FlashcardSet.query.filter_by(id=set_id).first()
        if not set:
            return redirect(url_for("main.sets"))
        set_name = sanitize_text(request.form.get("set_name"), max_length=255)
        set.name = set_name
        db.session.commit()
        session.pop('set_id')

        # Update flashcard values
        flashcards = Flashcard.query.filter_by(set_id=set_id).all()
        flashcard_ids = [card.id for card in flashcards]
        i = 1
        while True:
            question = sanitize_text(request.form.get(f"question-{i}"), max_length=2048)
            answer = sanitize_text(request.form.get(f"answer-{i}"), max_length=2048)
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
        set_name = sanitize_text(request.form.get("set_name"), max_length=255)
        flashcard_set = FlashcardSet(name=set_name, user_id=session["user_id"])
        db.session.add(flashcard_set)
        db.session.commit()

        set_id = flashcard_set.id
        i = 1
        while True:
            question = sanitize_text(request.form.get(f"question-{i}"), max_length=2048)
            answer = sanitize_text(request.form.get(f"answer-{i}"), max_length=2048)
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
    if "user_id" not in session:
        return redirect("/")

    set_id_raw = sanitize_text(request.form.get('set-id'), max_length=32)
    set_name = sanitize_text(request.form.get('set-name'), max_length=255)
    try:
        set_id = int(set_id_raw)
    except (TypeError, ValueError):
        return redirect(url_for("main.sets"))

    # Get flash cards
    flashcards = Flashcard.query.filter_by(set_id=set_id).all()
    flashcards_data = [
        {
            "question": sanitize_text(f.question, max_length=2048),
            "answer": sanitize_text(f.answer, max_length=2048),
        }
        for f in flashcards
    ]

    flashcards = {"questions": json.loads(json.dumps(flashcards_data))}

    session['set_id'] = set_id
    return render_template("flashcards.html", flashcards=flashcards, set_name=set_name)
    
@flashcards_bp.route("/notes")
def notes():
    if "user_id" not in session:
        return redirect("/")
    
    return render_template("notes.html", sections=parse_notes())

# Regenerates edited notes
@flashcards_bp.route("/regenerate-notes", methods=['POST'])
def regenerate_notes():
    if "user_id" not in session:
        return redirect("/")
    
    # Data to regenerate
    data = request.get_json()
    data = data.get("notes")

    
    session['notes'] = notes
    return redirect("/flashcards")

@flashcards_bp.route("/generate-quiz", methods=["POST"])
def save_notes():
    if "user_id" not in session:
        return redirect("/")
    
    print("generating quiz")
    payload = sanitize_structure(request.get_json() or {}, max_length=4096)
    data = payload.get("notes", [])
    title = sanitize_text(payload.get("title"), max_length=255)
    subject = sanitize_text(payload.get("subject"), max_length=255)
    questions = []

    questions = []
    futures = []
    prev_main = ""
    main = ""
    data_array = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        for d in data:
            main = sanitize_text(d.get("main_title", ""), max_length=255)

            if main != prev_main and data_array:
                num_of_q = max(round(len(data_array)/3), 1)
                for _ in range(num_of_q):
                    rand_q = random.randint(0, len(data_array)-1)
                    formatted_text = f"{data_array[rand_q]['main']} - {data_array[rand_q]['sub']}\n{data_array[rand_q]['content']}"
                    # submit only the question creation
                    futures.append(executor.submit(question, formatted_text, prev_main))

                data_array = []

            prev_main = main
            sub = sanitize_text(d.get("sub_title", ""), max_length=255)
            content_list = [sanitize_text(line, max_length=4096) for line in d.get("content", [])]
            content = "\n".join(content_list)
            data_array.append({"main":main, "sub":sub, "content":content})

        # handle last heading after loop
        if data_array:
            num_of_q = max(round(len(data_array)/3), 1)
            for _ in range(num_of_q):
                rand_q = random.randint(0, len(data_array)-1)
                formatted_text = f"{data_array[rand_q]['main']} - {data_array[rand_q]['sub']}\n{data_array[rand_q]['content']}"
                futures.append(executor.submit(question, formatted_text, prev_main))

        # collect results in order
        for f in futures:
            questions.append(sanitize_structure(f.result(), max_length=2048))

    # Saves notes and questions to database
    note_set = NoteSet(name=title, user_id=session.get("user_id"), subject=subject)

    for d in data:
        note = Note(
            main_title=sanitize_text(d.get("main_title", ""), max_length=255),
            sub_title=sanitize_text(d.get("sub_title", ""), max_length=255),
            content=json.dumps([
                sanitize_text(line, max_length=4096)
                for line in d.get("content", [])
            ])
        )
        note_set.notes.append(note)

    for q in questions:

        question_db = Question(
            question=sanitize_text(q.get("question"), max_length=2048),
            answer=json.dumps(sanitize_structure(q.get("answer"), max_length=2048)),
            title=sanitize_text(q.get('title'), max_length=255),
            type=sanitize_text(q.get('type'), max_length=64),
            options=(
                json.dumps(sanitize_structure(q.get("options"), max_length=1024))
                if q.get("options") is not None
                else None
            ),
        )
        note_set.questions.append(question_db)

    db.session.add(note_set)
    db.session.commit()
    session['set-id'] = note_set.id
    # Deletes previous notes and quiz
    if('set-edit' in session):
        note_set = NoteSet.query.get(int(session.get('set-edit')))
        db.session.delete(note_set)
        db.session.commit()
       
    session.pop("set-edit", None)
    return redirect("/quiz")

@flashcards_bp.route("/quiz")
def quiz():
    if "user_id" not in session:
        return redirect("/")
    set_id = session.get('set-id')
    note_set = NoteSet.query.filter_by(id=set_id, user_id=session.get("user_id")).first()
    if not note_set:
        return redirect(url_for("flashcards.quiz_sets"))

    notes = [
        {
            "main_title": sanitize_text(note.main_title, max_length=255),
            "sub_title": sanitize_text(note.sub_title, max_length=255),
            "content": [
                sanitize_text(line, max_length=4096)
                for line in json.loads(note.content)
            ],
        }
        for note in note_set.notes
    ]

    questions = [
        {
            "question": sanitize_text(q.question, max_length=2048),
            "answer": sanitize_structure(json.loads(q.answer), max_length=2048),
            "title": sanitize_text(q.title, max_length=255),
            "type": sanitize_text(q.type, max_length=64),
            "options": sanitize_structure(json.loads(q.options), max_length=1024)
            if q.options
            else None,
        }
        for q in note_set.questions
    ]
    print(questions)
    return render_template("quiz.html", data=notes, questions=questions,set_id=set_id)


# Displays different Subjects
@flashcards_bp.route("/home")
def home_page():
    if "user_id" not in session:
        return redirect("/")
    subjects = (
        db.session.query(NoteSet.subject)
        .filter_by(user_id=session.get("user_id"))
        .distinct()
        .all()
    )
    subjects_clean = [
        (sanitize_text(subject[0], max_length=255),)
        for subject in subjects
    ]
    return render_template("/home.html", subjects=subjects_clean)


# Display quizzes for a class
@flashcards_bp.route("/quiz-sets")
def quiz_sets():
    if "user_id" not in session:
        return redirect("/")
    subject = sanitize_text(session.get('subject-name'), max_length=255)
    quizzes = NoteSet.query.filter_by(user_id=session.get("user_id"), subject=subject).all()
    quizzes_data = [
        {"id": quiz.id, "name": sanitize_text(quiz.name, max_length=255)}
        for quiz in quizzes
    ]
    return render_template("quiz-sets.html", quizzes=quizzes_data, subject=subject)

# Redirects to subject quiz
@flashcards_bp.route("/open-subject-folder", methods=["POST"])
def subject_folder():
    if "user_id" not in session:
        return redirect("/")
    session['subject-name'] = sanitize_text(request.form.get('subject-name'), max_length=255)
    return redirect("/quiz-sets")

# Opens selected quiz
@flashcards_bp.route("/open-quiz", methods=["POST"])
def open_quiz():
    if "user_id" not in session:
        return redirect("/")
    set_id_raw = sanitize_text(request.form.get('set-id'), max_length=32)
    try:
        session['set-id'] = int(set_id_raw)
    except (TypeError, ValueError):
        return redirect(url_for("flashcards.quiz_sets"))
    return redirect("/quiz")

# Edit notes
@flashcards_bp.route("/edit-quiz", methods=["POST"])
def edit_quiz():
    if "user_id" not in session:
        return redirect("/")
    set_id_raw = sanitize_text(request.form.get('set-id'), max_length=32)
    try:
        session['set-id'] = int(set_id_raw)
    except (TypeError, ValueError):
        return redirect(url_for("flashcards.quiz_sets"))
    return redirect('/edit-notes')

@flashcards_bp.route("/edit-notes")
def edit_notes():
    if "user_id" not in session:
        return redirect("/")
    set_id = session.get('set-id')

    note_set = NoteSet.query.filter_by(id=set_id, user_id=session.get("user_id")).first()
    if not note_set:
        return redirect(url_for("flashcards.quiz_sets"))

    notes = [
        {
            "main_title": sanitize_text(note.main_title, max_length=255),
            "sub_title": sanitize_text(note.sub_title, max_length=255),
            "content": [
                sanitize_text(line, max_length=4096)
                for line in json.loads(note.content)
            ],
        }
        for note in note_set.notes
    ]

    session['set-edit'] = set_id
    return render_template("notes.html", data=notes)


# Opens quiz preview
@flashcards_bp.route("/quiz-preview", methods=["POST"])
def quiz_preview():
    if "user_id" not in session:
        return redirect("/")
    set_id_raw = sanitize_text(request.form.get('set-id'), max_length=32)
    try:
        set_id = int(set_id_raw)
    except (TypeError, ValueError):
        return redirect(url_for("flashcards.quiz_sets"))
    note_set = NoteSet.query.filter_by(id=set_id, user_id=session.get("user_id")).first()
    if not note_set:
        return redirect(url_for("flashcards.quiz_sets"))

    sanitized_set = {
        "id": note_set.id,
        "name": sanitize_text(note_set.name, max_length=255),
        "subject": sanitize_text(note_set.subject, max_length=255),
        "score": note_set.score or 0,
    }
    all_sets = NoteSet.query.filter_by(user_id=session.get("user_id"), subject=note_set.subject).all()
    all_set_info = [
        {
            "name": sanitize_text(set.name, max_length=255),
            "id": set.id,
        }
        for set in all_sets
    ]

    return render_template("quiz-preview.html", set=sanitized_set, other_sets=all_set_info)

# Only updates quiz preview content
@flashcards_bp.route("/quiz-preview-content", methods=["POST"])
def quiz_preview_content():
    if "user_id" not in session:
        return redirect("/")
    set_id_raw = sanitize_text(request.form.get('set-id'), max_length=32)
    try:
        set_id = int(set_id_raw)
    except (TypeError, ValueError):
        return redirect(url_for("flashcards.quiz_sets"))
    note_set = NoteSet.query.filter_by(id=set_id, user_id=session.get("user_id")).first()
    if not note_set:
        return redirect(url_for("flashcards.quiz_sets"))

    sanitized_set = {
        "id": note_set.id,
        "name": sanitize_text(note_set.name, max_length=255),
        "subject": sanitize_text(note_set.subject, max_length=255),
        "score": note_set.score or 0,
    }
    all_sets = NoteSet.query.filter_by(user_id=session.get("user_id"), subject=note_set.subject).all()
    all_set_info = [
        {
            "name": sanitize_text(set.name, max_length=255),
            "id": set.id,
        }
        for set in all_sets
    ]

    return render_template("quiz-preview-content.html", set=sanitized_set, other_sets=all_set_info)



# Ends the quiz and directs to the next question
@flashcards_bp.route("/end-quiz", methods=["POST"])
def end_quiz():
    if "user_id" not in session:
        return redirect("/")
    current_set_raw = sanitize_text(request.form.get('set-id'), max_length=32)
    score_raw = sanitize_text(request.form.get('final-score'), max_length=16)
    try:
        current_set_id = int(current_set_raw)
    except (TypeError, ValueError):
        return redirect(url_for("flashcards.quiz_sets"))
    try:
        score = int(score_raw)
    except (TypeError, ValueError):
        score = 0
    current_set = NoteSet.query.filter_by(id=current_set_id, user_id=session.get("user_id")).first()
    if not current_set:
        return redirect(url_for("flashcards.quiz_sets"))
    
    all_sets = NoteSet.query.filter_by(user_id=session.get("user_id"), subject=current_set.subject).all()
    all_set_info = [
        {
            "name": sanitize_text(set.name, max_length=255),
            "id": set.id,
        }
        for set in all_sets
    ]

    current_set = NoteSet.query.get(int(current_set_id))
    current_set.score = score
    db.session.commit()

    next_set = (
        NoteSet.query
        .filter(
            NoteSet.user_id == session.get("user_id"),
            NoteSet.subject == current_set.subject,
            NoteSet.id > current_set.id
        )
        .order_by(NoteSet.created_at.asc())
        .first()
    )

    if not next_set:
        session['subject-name'] = sanitize_text(current_set.subject, max_length=255)
        return redirect('quiz-sets')
    return render_template("quiz-preview.html", set=next_set, other_sets=all_set_info)

# Enhances given notes
@flashcards_bp.route("/enhance-note", methods=["POST"])
def enhance_note():
    if "user_id" not in session:
        return redirect("/")
    payload = sanitize_structure(request.get_json() or {}, max_length=4096)
    note = sanitize_text(payload.get("note"), max_length=4096)
    enhanced_note = extract_definitions(note)
    return {"note": sanitize_structure(enhanced_note, max_length=4096)}

@flashcards_bp.route("/delete-quiz", methods=["POST"])
def delete_quiz():
    if "user_id" not in session:
        return redirect("/")
    set_id_raw = sanitize_text(request.form.get('set-id'), max_length=32)
    try:
        set_id = int(set_id_raw)
    except (TypeError, ValueError):
        return redirect(url_for("flashcards.quiz_sets"))

    note_set = NoteSet.query.get(int(set_id))
    if note_set:
        db.session.delete(note_set)
        db.session.commit()

    return redirect("/quiz-sets")
