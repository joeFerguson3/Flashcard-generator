# models.py
from extensions import db

# Users table (Google login info)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    picture = db.Column(db.String(250))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # separate relationships
    note_sets = db.relationship("NoteSet", back_populates="owner")
    flashcard_sets = db.relationship("FlashcardSet", back_populates="owner")

# Note sets (groups of notes/questions)
class NoteSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    owner = db.relationship("User", back_populates="note_sets")
    notes = db.relationship("Note", back_populates="note_set", cascade="all, delete-orphan")
    questions = db.relationship("Question", back_populates="note_set", cascade="all, delete-orphan")


# Notes table
class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    set_id = db.Column(db.Integer, db.ForeignKey("note_set.id"), nullable=False)
    main_title = db.Column(db.String(255), nullable=False)
    sub_title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)  # JSON string

    note_set = db.relationship("NoteSet", back_populates="notes")


# Questions table (derived from notes)
class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    set_id = db.Column(db.Integer, db.ForeignKey("note_set.id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)

    note_set = db.relationship("NoteSet", back_populates="questions")


# Flashcard sets
class FlashcardSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    owner = db.relationship("User", back_populates="flashcard_sets")
    flashcards = db.relationship("Flashcard", back_populates="set", cascade="all, delete-orphan")


# Flashcards table
class Flashcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    set_id = db.Column(db.Integer, db.ForeignKey("flashcard_set.id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    set = db.relationship("FlashcardSet", back_populates="flashcards")

