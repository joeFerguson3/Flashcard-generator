from flask import Blueprint, render_template, request, redirect, session, url_for
from utils.pdf_utils import extract_text
from utils.notes import parse_notes
from utils.ai_utils import question, extract_definitions
from models import Flashcard, FlashcardSet, Note, NoteSet, Question
from extensions import db  
import json
import random
from concurrent.futures import ThreadPoolExecutor
flashcards_bp = Blueprint("flashcards", __name__)

@flashcards_bp.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files.get("pdfUpload")
        if not file or not file.filename.endswith(".pdf"):
            return "Invalid file type."
        
        notes = extract_text(file)
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

# Regenerates edited notes
@flashcards_bp.route("/regenerate-notes", methods=['POST'])
def regenerate_notes():
    # Data to regenerate
    data = request.get_json()
    data = data.get("notes")

    
    session['notes'] = notes
    return redirect("/flashcards")

@flashcards_bp.route("/generate-quiz", methods=["POST"])
def save_notes():
    print("generating quiz")
    dict = request.get_json()
    data = dict.get("notes")
    title = dict.get("title")
    subject = dict.get("subject")
    questions = []

    questions = []
    futures = []
    prev_main = ""
    main = ""
    data_array = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        for d in data:
            main = d.get("main_title", "")

            if main != prev_main and data_array: 
                num_of_q = max(round(len(data_array)/3), 1)
                for _ in range(num_of_q):
                    rand_q = random.randint(0, len(data_array)-1)
                    formatted_text = f"{data_array[rand_q]['main']} - {data_array[rand_q]['sub']}\n{data_array[rand_q]['content']}"
                    # submit only the question creation
                    futures.append(executor.submit(question, formatted_text, prev_main))

                data_array = []

            prev_main = main
            sub = d.get("sub_title", "")
            content = "\n".join(d.get("content", []))
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
            questions.append(f.result())

    # Saves notes and questions to database
    note_set = NoteSet(name=title, user_id=session.get("user_id"), subject=subject)  
    
    for d in data:
        note = Note(
            main_title=d.get("main_title", ""),
            sub_title=d.get("sub_title", ""),
            content=json.dumps(d.get("content", ""))
        )
        note_set.notes.append(note)

    for q in questions:

        question_db = Question(
            question=q["question"],
            answer=json.dumps(q["answer"]),
            title=q['title'],
            type=q['type'],
            options = json.dumps(q.get("options")) if q.get("options") is not None else None
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
    set_id = session.get('set-id')
    note_set = NoteSet.query.filter_by(id=set_id, user_id=session.get("user_id")).first()

    notes = [
        {
            "main_title": note.main_title,
            "sub_title": note.sub_title,
            "content": json.loads(note.content)
        }
        for note in note_set.notes
    ]

    questions = [
    {
        "question": q.question,
        "answer": json.loads(q.answer),
        "title": q.title,
        "type": q.type,
        "options": json.loads(q.options) if q.options else None
    }
    for q in note_set.questions
    ]
    print(questions)
    return render_template("quiz.html", data=notes, questions=questions,set_id=set_id)


# Displays different Subjects
@flashcards_bp.route("/home")
def home_page():
    subjects = db.session.query(NoteSet.subject).filter_by(user_id=session.get("user_id")).distinct().all()
    return render_template("/home.html", subjects=subjects)


# Display quizzes for a class
@flashcards_bp.route("/quiz-sets")
def quiz_sets():
    subject = session.get('subject-name')
    quizzes = NoteSet.query.filter_by(user_id=session.get("user_id"), subject=subject).all()
    return render_template("quiz-sets.html", quizzes=quizzes, subject=subject)

# Redirects to subject quiz
@flashcards_bp.route("/open-subject-folder", methods=["POST"])
def subject_folder():
    session['subject-name'] = request.form.get('subject-name')
    return redirect("/quiz-sets")

# Opens selected quiz
@flashcards_bp.route("/open-quiz", methods=["POST"])
def open_quiz():
    session['set-id'] = request.form.get('set-id')
    return redirect("/quiz")

# Edit notes
@flashcards_bp.route("/edit-quiz", methods=["POST"])
def edit_quiz():
    session['set-id'] = request.form.get('set-id')
    return redirect('/edit-notes')

@flashcards_bp.route("/edit-notes")
def edit_notes():
    set_id = session.get('set-id')

    note_set = NoteSet.query.filter_by(id=set_id, user_id=session.get("user_id")).first()

    notes = [
        {
            "main_title": note.main_title,
            "sub_title": note.sub_title,
            "content": json.loads(note.content)
        }
        for note in note_set.notes
    ]

    session['set-edit'] = set_id
    return render_template("notes.html", data=notes)


# Opens quiz preview
@flashcards_bp.route("/quiz-preview", methods=["POST"])
def quiz_preview():
    set_id = request.form.get('set-id')
    note_set = NoteSet.query.filter_by(id=set_id, user_id=session.get("user_id")).first()

    all_sets = NoteSet.query.filter_by(user_id=session.get("user_id"), subject=note_set.subject).all()
    all_set_info = [
        {
            "name": set.name,
            "id": set.id
        }
        for set in all_sets
    ]

    return render_template("quiz-preview.html", set=note_set, other_sets=all_set_info)

# Only updates quiz preview content
@flashcards_bp.route("/quiz-preview-content", methods=["POST"])
def quiz_preview_content():
    set_id = request.form.get('set-id')
    note_set = NoteSet.query.filter_by(id=set_id, user_id=session.get("user_id")).first()

    all_sets = NoteSet.query.filter_by(user_id=session.get("user_id"), subject=note_set.subject).all()
    all_set_info = [
        {
            "name": set.name,
            "id": set.id
        }
        for set in all_sets
    ]

    return render_template("quiz-preview-content.html", set=note_set, other_sets=all_set_info)



# Ends the quiz and directs to the next question
@flashcards_bp.route("/end-quiz", methods=["POST"])
def end_quiz():
    current_set_id = request.form.get('set-id')
    current_set = NoteSet.query.filter_by(id=current_set_id, user_id=session.get("user_id")).first()
    
    all_sets = NoteSet.query.filter_by(user_id=session.get("user_id"), subject=current_set.subject).all()
    all_set_info = [
        {
            "name": set.name,
            "id": set.id
        }
        for set in all_sets
    ]

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
        session['subject-name'] = current_set.subject
        return redirect('quiz-sets')
    return render_template("quiz-preview.html", set=next_set, other_sets=all_set_info)

# Enhances given notes
@flashcards_bp.route("/enhance-note", methods=["POST"])
def enhance_note():
    dict = request.get_json()
    note = dict.get("note")
    enhanced_note = extract_definitions(note)
    return {"note": enhanced_note}