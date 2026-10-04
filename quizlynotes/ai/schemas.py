"""Structured-output schemas.

These are passed to Gemini as response schemas, so the model can only return
JSON that matches them. Kept deliberately flat (no unions) because flat
schemas are the most reliable across models.
"""
from typing import Literal

from pydantic import BaseModel, Field


class Point(BaseModel):
    text: str = Field(description="One concise revision point. Plain text, no markdown.")
    level: int = Field(description="Indent level: 1 = main point, 2 = supporting detail, 3 = example/sub-detail.")


class NoteSection(BaseModel):
    heading: str = Field(description="Topic heading shared by related sections (like a chapter title).")
    subheading: str = Field(description="The specific concept this section covers.")
    points: list[Point]


class NotesDoc(BaseModel):
    title: str = Field(description="Short, specific title for these notes (max 8 words).")
    subject: str = Field(description="Broad academic subject, e.g. 'Psychology', 'Biology', 'Computer Science'.")
    sections: list[NoteSection]


class NoteSections(BaseModel):
    sections: list[NoteSection]


CardKind = Literal[
    "flashcard", "multiple_choice", "true_false", "fill_blank", "short_answer", "ordering",
    "matching", "multi_select", "categorize", "numeric", "odd_one_out",
]


class GenCard(BaseModel):
    section: int = Field(description="Index (0-based) of the notes section this card tests.")
    kind: CardKind
    prompt: str = Field(
        description=(
            "flashcard: the front (question or term). multiple_choice/short_answer: the question. "
            "true_false: a statement. fill_blank: a sentence with each missing term written as {blank}. "
            "ordering: instruction such as 'Put these stages in order'."
        )
    )
    options: list[str] = Field(
        description=(
            "multiple_choice: 4 answer options. ordering: the items in the CORRECT order "
            "(they are shuffled for the student). matching: the terms (left column). "
            "multi_select: 4-6 options. categorize: the items to sort. odd_one_out: 4 items. "
            "Empty list for every other kind."
        )
    )
    answers: list[str] = Field(
        description=(
            "flashcard: [back of card]. multiple_choice: [the exact correct option]. "
            "true_false: ['true'] or ['false']. fill_blank: one entry per {blank}, in order. "
            "short_answer: [best answer, then acceptable alternative phrasings]. ordering: []. "
            "matching: the matching definition for each term, same order as options. "
            "multi_select: every correct option, copied exactly. "
            "categorize: the category name for each item, same order as options. "
            "numeric: [the number only, then optionally the unit]. "
            "odd_one_out: [the item that doesn't belong, copied exactly]."
        )
    )
    explanation: str = Field(description="One or two sentences explaining why the answer is correct.")


class CardDeck(BaseModel):
    cards: list[GenCard]


class QuickStudy(BaseModel):
    """Notes and cards in one response, for the public demo."""

    title: str
    subject: str
    sections: list[NoteSection]
    cards: list[GenCard]
