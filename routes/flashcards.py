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
    notes = extract_text()
    # flashcards = {"questions": flashcards}
    return render_template("notes.html", sections=notes)

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
    data = json.loads(request.form.get("notes"))

    questions = [{'type': 'fill-in-blank', 'question': 'The definition and exploration of intelligence in AI is referred to as {blank}.', 'answer': ['intelligence in AI'], 'title': 'Machines and Intelligence'},
    {'type': 'short-answer', 'question': 'What are the key similarities and differences between human brains and computers in terms of processing information?', 'answer': 'Both process information, but brains use neural networks while computers use binary code.', 'title': 'Machines and Intelligence'},
    {'type': 'fill-in-blank', 'question': 'The fundamental components necessary for {blank}.', 'answer': ['intelligence'], 'title': 'Machines and Intelligence'},
    {'type': 'short-answer', 'question': 'How does learning in neural networks compare to human learning?', 'answer': 'Learning in neural networks occurs in ways that parallel human learning processes.', 'title': 'Machines and Intelligence'},
    {'type': 'short-answer', 'question': 'What are some of the progress and challenges in developing Artificial General Intelligence (AGI)?', 'answer': 'Progress includes advancements in machine learning and neural networks, while challenges involve ethical considerations and ensuring safety.', 'title': 'Machines and Intelligence'},
    {'type': 'short-answer', 'question': 'What are some implications of artificial intelligence in everyday life?', 'answer': 'Interactions with AI in various daily activities and its impact on lifestyle.', 'title': 'How Vision Works'},
    {'type': 'short-answer', 'question': 'Why is the exploration of human visual perception important for creating artificial visual systems?', 'answer': 'It is essential for understanding how to replicate visual functions in machines.', 'title': 'How Vision Works'},
    {'type': 'multiple-choice', 'question': 'What limitation is associated with the Inner Screen Theory of Seeing?', 'options': ['It successfully explains vision', 'It leads to infinite regress problem', 'It is widely accepted', 'It does not involve the brain'], 'answer': 'It leads to infinite regress problem', 'title': 'How Vision Works'},
    {'type': 'fill-in-blank', 'question': 'The human retina contains approximately {blank} rod cells and about {blank} cone cells.', 'answer': ['120 million', '6 million'], 'title': 'How Vision Works'},
    {'type': 'fill-in-blank', 'question': 'The Left Visual Field represents {blank}°, while the Right Visual Field represents {blank}°.', 'answer': ['200', '135'], 'title': 'How Vision Works'},
    {'type': 'fill-in-blank', 'question': 'Numerous areas in the brain are organized as {blank}.', 'answer': ['retinotopic maps'], 'title': 'How Vision Works'}]

    data = [{'main_title': 'Machines and Intelligence', 'sub_title': 'What is Intelligence?', 'content': ['- Definition and exploration of intelligence in AI.']}, {'main_title': 'Machines and Intelligence', 'sub_title': 'Brains and Computers', 'content': ['- Comparison of human brains and computers in terms of processing information.']}, {'main_title': 'Machines and Intelligence', 'sub_title': 'The Building Blocks of Intelligence', 'content': ['- Fundamental components necessary for intelligence.']}, {'main_title': 'Machines and Intelligence', 'sub_title': 'Learning in Neural Networks', 'content': ['- How learning occurs in neural networks and parallels with human learning.']}, {'main_title': 'Machines and Intelligence', 'sub_title': 'Towards Artificial General Intelligence (AI)', 'content': ['- Progress and challenges in developing AGI.']}, {'main_title': 'How Vision Works', 'sub_title': 'Living with Artificial Intelligence', 'content': ['- Implications and interactions with AI in everyday life.']}, {'main_title': 'How Vision Works', 'sub_title': 'Overview', 'content': ['- Exploration of human visual perception essential for creating artificial visual systems.']}, {'main_title': 'How Vision Works', 'sub_title': 'The Inner Screen Theory of Seeing', 'content': ['- **Concept**: Proposes brain representation akin to a movie theater (Cartesian Theatre).', '- **Limitation**: Fails due to infinite regress problem.']}, {'main_title': 'How Vision Works', 'sub_title': 'Anatomy of the Eye', 'content': ['- Human retina is an extension of the brain:', '  - Contains approximately 120 million rod cells.', '  - Contains about 6 million cone cells.']}, {'main_title': 'How Vision Works', 'sub_title': 'The Human Visual System as Two Hemifields', 'content': ['- Visual fields represent:', '  - Left Visual Field: 200°', '  - Right Visual Field: 135°', '  - Overlap and distortion in perception.']}, {'main_title': 'How Vision Works', 'sub_title': 'Retinotopic Maps in the Brain', 'content': ['- Numerous areas in the brain are organized as retinotopic maps.']}, {'main_title': 'How Vision Works', 'sub_title': 'Cortical Processing of Vision', 'content': ['- Originates from the back of the brain and involves multiple pathways.']}, {'main_title': 'How Vision Works', 'sub_title': 'Edge Detector Cells in Visual Cortex', 'content': ['- Hubel & Wiesel (1959) found single V1 cells respond to moving lines at preferred orientations.']}, {'main_title': 'How Vision Works', 'sub_title': 'High-Level Concepts in Vision', 'content': ['- Neurons in the temporal lobe respond to complex stimulus properties associated with high-level concepts (e.g., people, places).']}, {'main_title': 'How Vision Works', 'sub_title': 'Deep Learning and Computer Vision', 'content': ['- **Convolutional Neural Networks**:', '  - Successive layers act as feature detectors.', '- Complexity of features increases through layers.']}, {'main_title': 'Gestalt Principles', 'sub_title': 'Visual Cortical Areas and Deep Networks', 'content': ['- Activity in human visual cortex matches layers in artificial deep networks:', '  - Early areas (V1, V2) match simpler feature layers.', '  - Later areas (V3, V4, LO) correspond to complex feature layers.']}, {'main_title': 'Interim Summary', 'sub_title': 'Key Principles of Perception', 'content': ['- **Emergence**: Percepts form from simpler shapes.', '- **Multistability**: Perceptions can shift between interpretations.', '- **Reification**: Recognition of whole forms.', '- **Other Principles**:', '  - Closure', '  - Similarity', '  - Proximity', '  - Continuity', '- **Inner Screen Theory**: Lacks a physical "inner eye."', '- **Retinotopic Maps**: Upside-down, flipped, and distorted.', '- **Information Extraction**: Separated streams for "what" and "where."', '- **Neural Responses**: Comparisons with artificial neurons in deep networks.', '- **Perceptual Principles**: Brain utilizes powerful principles including closure, similarity, proximity, and continuity in visual processing.']}]
    # for d in data:
    #     main = d.get("main_title", "")
    #     sub = d.get("sub_title", "")
    #     content = "\n".join(d.get("content", []))
    #     formatted_text = f"{main} - {sub}\n{content}"
    #     questions.append(question(formatted_text, main))

    return render_template("quiz.html", data=data, questions=questions)