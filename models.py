# models.py
from extensions import db

# Users table (Google login info)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    picture = db.Column(db.String(250))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    
    flashcards = db.relationship("Flashcard", secondary="user_flashcards", back_populates="users")
    sets = db.relationship("FlashcardSet", back_populates="owner")

# Flashcard table
class Flashcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    
    users = db.relationship("User", secondary="user_flashcards", back_populates="flashcards")
    sets = db.relationship("FlashcardSet", secondary="set_flashcards", back_populates="flashcards")

# FlashcardSet table (group of flashcards)
class FlashcardSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    
    owner = db.relationship("User", back_populates="sets")
    flashcards = db.relationship("Flashcard", secondary="set_flashcards", back_populates="sets")

# Link table: User ↔ Flashcards (for ownership or shared cards)
user_flashcards = db.Table(
    "user_flashcards",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("flashcard_id", db.Integer, db.ForeignKey("flashcard.id"), primary_key=True)
)

# Link table: FlashcardSet ↔ Flashcards
set_flashcards = db.Table(
    "set_flashcards",
    db.Column("set_id", db.Integer, db.ForeignKey("flashcard_set.id"), primary_key=True),
    db.Column("flashcard_id", db.Integer, db.ForeignKey("flashcard.id"), primary_key=True)
)
