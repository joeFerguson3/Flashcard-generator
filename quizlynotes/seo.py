"""Content for the public, indexable pages.

Each landing page targets a distinct search intent seen in Search Console
("quiz notes", "turn notes into quiz questions", "make a quiz out of my notes")
plus closely related ones (PDF to quiz, notes to flashcards). The copy is
unique per page to avoid duplicate-content issues.
"""

QUESTION_TYPES = [
    ("Multiple choice", "Four options with believable distractors, so you have to know the answer, not guess it."),
    ("True or false", "Statements with one detail changed, which catches half-learned facts."),
    ("Fill in the blank", "Key terms removed from a sentence, so you practise recalling the exact word."),
    ("Short answer", "Type the answer from memory. Small typos and alternative wordings still count."),
    ("Ordering", "Put stages, steps or events in sequence. Made only when your notes describe a real process."),
    ("Matching", "Pair key terms with their definitions, so you learn how ideas connect."),
    ("Select all that apply", "Questions with more than one right answer, which test whether you really know the topic."),
    ("Sort into groups", "Put each item in the right category, for comparing and classifying."),
    ("Numeric", "Calculation and number answers, with sensible rounding allowed."),
    ("Odd one out", "Spot the item that doesn't belong, which tests whether you know what links the others."),
    ("Flashcards", "One idea per card, reviewed with spaced repetition so you see hard cards more often."),
]

HOME_FAQ = [
    ("What is QuizlyNotes?",
     "QuizlyNotes is a free AI study tool that turns your notes into quizzes and flashcards. Upload lecture "
     "slides, a PDF, a Word document or paste your notes, and it writes revision notes, practice questions "
     "and flashcards for you to study."),
    ("Is QuizlyNotes free?",
     "Yes. Studying is free and unlimited: quizzes, flashcards, spaced repetition and games. The free plan "
     "includes 5 new AI study sets a month, and every new account starts with a 7-day Pro trial. Pro removes "
     "the AI limits and adds mock exams and weak-spot review."),
    ("How is QuizlyNotes different from Quizlet or ChatGPT?",
     "QuizlyNotes is built around your own material. One upload becomes revision notes, a quiz with ten question "
     "types and an explanation for every answer, and a spaced-repetition flashcard deck, all saved and scored by "
     "subject. Quizlet is best known for shared flashcard sets, and a chatbot's quiz isn't saved or scheduled for "
     "review. See the full comparison on the Compare page."),
    ("What files can I upload?",
     "PDFs (including lecture slides and scanned pages), Word documents (.docx), PowerPoint files (.pptx) and "
     "plain text. You can also paste notes directly. Free accounts can upload PDFs up to 30 pages; Pro handles up to 150 pages and 30MB."),
    ("How accurate are the questions?",
     "Questions are written only from your material, and every answer comes with a short explanation. You can "
     "review and edit the notes before the quiz is made, and edit or delete any question afterwards."),
    ("Can AI read diagrams and slides?",
     "Yes. PDFs are read page by page as a whole document, so labelled diagrams, tables and slide text are "
     "understood in context, not just the raw text."),
    ("What happens to my files?",
     "Your file is sent to the AI model to write your notes and is not stored by QuizlyNotes. The notes, "
     "questions and scores are saved to your account so you can come back to them. You can export or delete "
     "everything at any time from Settings."),
]

LANDING_PAGES = {
    "notes-to-quiz": {
        "path": "/notes-to-quiz",
        "title": "Turn Notes into Quiz Questions with AI (Free) | QuizlyNotes",
        "description": "Make a quiz out of your notes in seconds. Paste or upload notes and get multiple choice, "
                       "true/false and fill-in-the-blank questions with answers. Free.",
        "eyebrow": "Notes to quiz",
        "h1": "Turn your notes into quiz questions",
        "lede": "Paste your class notes or upload a file, and get a ready-to-take quiz with answers and "
                "explanations. It's the fastest way to make a quiz out of your notes and find out what "
                "you actually know.",
        "sections": [
            ("Why quizzing yourself beats re-reading",
             ["Re-reading notes feels productive, but it mostly builds familiarity. Answering questions forces "
              "you to recall the information, and that act of retrieval is what makes it stick. Learning "
              "researchers call this the testing effect.",
              "The catch is that writing good questions takes time. QuizlyNotes does that part for you, so your "
              "study time goes on answering, not on making the quiz."]),
            ("How to make a quiz out of your notes",
             ["1. Paste your notes into the box above, or sign in and upload a PDF, Word or PowerPoint file.",
              "2. QuizlyNotes organises them into clean revision notes grouped by topic. Edit anything you like.",
              "3. Choose how many questions you want, the difficulty, and which question types to include.",
              "4. Take the quiz. You'll study each topic's notes, answer questions on it, and get your score, "
              "with explanations for anything you missed."]),
            ("Questions that test understanding",
             ["The questions cover every topic in your notes in proportion to how much there is to learn. "
              "Multiple choice options are written to be believable, true/false statements change one key "
              "detail, and fill-in-the-blank questions remove the terms that matter. Each answer has a "
              "one-line explanation, so a wrong answer still teaches you something."]),
        ],
        "faq": [
            ("Can I turn handwritten notes into a quiz?",
             "Yes, if you scan or photograph them into a PDF. The AI reads scanned pages, though clear, "
             "well-lit scans give the best results."),
            ("How many questions can I make?",
             "Choose Auto and the number is based on how much material there is, or pick a number: up to 15 questions on the free plan, or up to 60 on Pro."),
            ("Can I edit the questions?",
             "Yes. You can edit the notes before the quiz is made, and edit, delete or add cards afterwards."),
            ("Does it work for any subject?",
             "It works best for subjects with facts, definitions and processes to learn, such as biology, "
             "psychology, history, law, business and computer science. It also works for languages and humanities "
             "notes, with more short-answer and flashcard questions."),
        ],
    },
    "pdf-to-quiz": {
        "path": "/pdf-to-quiz",
        "title": "PDF to Quiz: Quiz from Lecture Slides & PDFs | QuizlyNotes",
        "description": "Upload a PDF or lecture slides and get a practice quiz with answers in seconds. Reads "
                       "text, diagrams and scanned pages. Free AI quiz generator for students.",
        "eyebrow": "PDF to quiz",
        "h1": "Make a quiz from any PDF or lecture slides",
        "lede": "Upload your lecture slides, textbook chapter or handout as a PDF. QuizlyNotes reads every page, "
                "including diagrams and scanned slides, and turns it into revision notes and a practice quiz.",
        "sections": [
            ("Built for lecture slides",
             ["Slides are hard to revise from: bullet points out of context, diagrams with labels, the same title "
              "slide five times. QuizlyNotes reads the whole deck at once, ignores the admin (module codes, image "
              "credits, reading-list prices) and rewrites the content as structured notes before writing any "
              "questions."]),
            ("Reads diagrams and scanned pages",
             ["Your PDF is read page by page as a whole document, not just the text layer. Labelled diagrams, tables "
              "and charts become notes and questions, and scanned or image-only PDFs work too."]),
            ("From PDF to practice test in four steps",
             ["1. Sign in with Google and upload your PDF (up to 30 pages free, or 150 pages on Pro).",
              "2. Review the generated notes, organised by topic. Fix or delete anything you don't need.",
              "3. Generate a quiz with the question types and difficulty you want.",
              "4. Study the notes and answer questions topic by topic, then review flashcards on the days they're due."]),
        ],
        "faq": [
            ("Is there a page limit?",
             "Free accounts can upload PDFs up to 30 pages and 10MB; Pro takes up to 150 pages and 30MB. For a whole textbook, upload one chapter at a time. Each "
             "chapter becomes its own quiz, grouped under the same subject."),
            ("Can I upload PowerPoint instead of PDF?",
             "Yes, .pptx files work, including speaker notes. If your slides are mostly diagrams, export them "
             "to PDF first so the AI can see the images."),
            ("Will it include the module code and admin slides?",
             "No. The AI is told to skip course admin, credits and repeated title slides and to focus on what "
             "you'll be examined on."),
            ("Is my PDF stored?",
             "No. The file is processed to create your notes and is not kept by QuizlyNotes. Only the notes and "
             "questions are saved to your account."),
        ],
    },
    "notes-to-flashcards": {
        "path": "/notes-to-flashcards",
        "title": "AI Flashcard Maker: Turn Notes into Flashcards | QuizlyNotes",
        "description": "Turn notes, PDFs and slides into flashcards automatically. Study with spaced repetition "
                       "so hard cards come back more often. Free AI flashcard generator.",
        "eyebrow": "Notes to flashcards",
        "h1": "Turn your notes into flashcards automatically",
        "lede": "Stop copying definitions onto cards by hand. QuizlyNotes pulls the key terms and ideas out of your "
                "notes, writes one clear flashcard for each, and schedules reviews so you remember them.",
        "sections": [
            ("Good flashcards follow a few rules",
             ["The most effective flashcards test one idea, have a short answer you can recall from memory, and "
              "make sense on their own. Most homemade cards break these rules by cramming a paragraph onto the back. "
              "The AI is instructed to keep every card atomic and the answer under 25 words."]),
            ("Spaced repetition built in",
             ["After you flip a card, rate how well you knew it: Again, Hard, Good or Easy. Cards you find hard come "
              "back within minutes or a day, and cards you know well are spaced out over days and weeks. Your "
              "library shows how many cards are due, so a short daily review is enough."]),
            ("Flashcards and a quiz from the same notes",
             ["Every set comes with a practice quiz as well. Use flashcards for daily recall and the quiz to check "
              "you can apply what you know before an exam."]),
        ],
        "faq": [
            ("How many flashcards will I get?",
             "It depends on how much material there is, typically one card for every few key points, up to 50 per set. "
             "You can add your own cards at any time."),
            ("Can I edit the flashcards?",
             "Yes. Edit the front or back of any card, delete cards you don't need, or add new ones."),
            ("What is spaced repetition?",
             "A way of scheduling reviews so each card comes back just before you're likely to forget it. It's one "
             "of the most reliable ways to remember facts long term."),
            ("Can I use it on my phone?",
             "Yes. QuizlyNotes works in any modern mobile browser, and flashcards can be flipped with a tap."),
        ],
    },
    "ai-quiz-generator": {
        "path": "/ai-quiz-generator",
        "title": "AI Quiz Generator from Notes, PDFs & Slides (Free) | QuizlyNotes",
        "description": "Free AI quiz and flashcard generator. Upload notes, a PDF or lecture slides and get "
                       "10 question types with explained answers, plus spaced-repetition flashcards.",
        "eyebrow": "AI quiz generator",
        "h1": "The AI quiz generator that starts from your notes",
        "lede": "Most AI quiz makers write generic questions about a topic. QuizlyNotes writes them from your own "
                "notes, slides and PDFs, so you're tested on what your course actually covers, with an "
                "explanation for every answer.",
        "sections": [
            ("What makes a good AI quiz generator",
             ["A quiz is only useful if it tests the right things. QuizlyNotes first turns your material into "
              "revision notes grouped by topic, which you can check and edit. Questions are then written from "
              "those notes only, spread across every topic in proportion to how much there is to learn.",
              "That two-step approach means fewer made-up facts, no questions on things your course never "
              "mentioned, and a quiz you can trust the night before an exam."]),
            ("Ten question types, not just multiple choice",
             ["QuizlyNotes writes multiple choice, true or false, fill in the blank, short answer, ordering, "
              "matching, select all that apply, sort into groups, numeric and odd one out questions, plus "
              "flashcards. Mixing formats makes you recall information in different ways, which is closer to "
              "how real exams test you.",
              "Short answers are marked generously, so small typos and alternative wordings still count. "
              "Every question is marked automatically, so you get your score straight away."]),
            ("A flashcard and quiz generator in one",
             ["Every set comes with both a practice quiz and a deck of flashcards made from the same notes. "
              "Flashcards use spaced repetition, so cards you find hard come back sooner. There are also quick "
              "games (Match, Speed and Write) for when you want something lighter."]),
            ("Free to use",
             ["Studying is free and unlimited. The free plan includes 5 new AI study sets a month, and every new "
              "account gets a 7-day Pro trial with no card needed. Pro (£4.99 a month or £29.99 a year) removes "
              "the AI limits and adds mock exams and weak-spot review."]),
        ],
        "faq": [
            ("Which AI model does QuizlyNotes use?",
             "QuizlyNotes uses Google's Gemini Flash models, which read PDFs natively, including diagrams and "
             "scanned pages. Answers are checked against a strict format before you see them, so broken or "
             "half-written questions are filtered out."),
            ("Can I choose the question types and difficulty?",
             "Yes. Pick any mix of the ten question types, choose easy, medium or hard, and set how many questions "
             "you want, or leave it on Auto."),
            ("Does it make up facts?",
             "Questions are written only from the notes made from your material, and you can review and edit those "
             "notes first. Like any AI tool it can occasionally get something wrong, so every question can be "
             "edited or deleted."),
            ("Is it free?",
             "Yes. You can study as much as you like for free, with 5 new AI study sets a month. You can also try "
             "it without an account on the home page."),
        ],
    },
}

RELATED_LINKS = [
    ("notes-to-quiz", "Turn notes into a quiz"),
    ("pdf-to-quiz", "PDF and slides to quiz"),
    ("notes-to-flashcards", "Notes to flashcards"),
    ("ai-quiz-generator", "AI quiz generator"),
]

# Facts used by /about, /llms.txt and structured data, kept in one place so
# every description of QuizlyNotes says the same thing.
PRODUCT_SUMMARY = (
    "QuizlyNotes (quizlynotes.com) is a free AI study tool that turns your own notes, PDFs, lecture slides, "
    "Word documents and PowerPoint files into revision notes, practice quizzes and spaced-repetition flashcards."
)

KEY_FACTS = [
    ("Input", "PDFs (including scanned pages and lecture slides), Word (.docx), PowerPoint (.pptx), plain text, or pasted notes."),
    ("Output", "Revision notes grouped by topic, a practice quiz with explained answers, and a flashcard deck."),
    ("Question types", "Multiple choice, true or false, fill in the blank, short answer, ordering, matching, "
                       "select all that apply, sort into groups, numeric and odd one out, plus flashcards. Every question is marked automatically."),
    ("Study modes", "Topic-by-topic quiz, flashcards with spaced repetition (Again, Hard, Good, Easy), and Match, "
                    "Speed and Write games. Pro adds timed mock exams across a subject and weak-spot review."),
    ("AI model", "Google Gemini Flash. Questions are written only from the notes made from your material."),
    ("Price", "Free: unlimited studying and 5 new AI study sets a month. Pro: £4.99 a month or £29.99 a year. "
              "New accounts get a 7-day Pro trial with no card."),
    ("Privacy", "Uploaded files are not stored. Notes and scores can be exported or deleted at any time."),
    ("Works on", "Any modern web browser on desktop, tablet or phone. Sign in with Google."),
    ("Made for", "Secondary school, sixth form, college and university students revising for exams."),
]

# The comparison page. Competitor details are summarised from their public
# pricing pages; keep the "checked" date honest when updating.
COMPARE_CHECKED = "October 2026"
COMPARE_ROWS = [
    # (feature, QuizlyNotes, Quizlet, Knowt, ChatGPT / general chatbots)
    ("Starts from your own notes and files", "Yes: PDF, slides, Word, PowerPoint, text", "Yes, with its AI tools (some paid)",
     "Yes", "Yes, if you upload them"),
    ("Writes revision notes first", "Yes, editable before the quiz", "With its AI notes tools", "Yes", "If you ask"),
    ("Question types", "10, plus flashcards", "Several in Learn and Test", "Several", "Whatever you prompt"),
    ("Explanation for every answer", "Yes, on every question", "Varies by mode", "Varies", "If you ask"),
    ("Spaced-repetition flashcards", "Yes", "Yes", "Yes", "No"),
    ("Saves scores and progress by subject", "Yes", "Yes", "Yes", "No"),
    ("Free studying limits", "None: studying is unlimited", "Some study modes are limited on the free plan",
     "Unlimited studying, AI on an allowance", "Usage limits on free plans"),
    ("Paid plan", "£4.99/month or £29.99/year", "Quizlet Plus", "Knowt paid plans", "Chatbot subscription"),
]

COMPARE_PICKS = [
    ("QuizlyNotes",
     "Best if you have lecture slides, PDFs or class notes and want a proper quiz on exactly that material, with "
     "explanations, several question types and flashcards, without writing anything yourself."),
    ("Quizlet",
     "Best if you want ready-made sets other students have already made for common courses, or you prefer typing "
     "your own term and definition cards. It also has AI tools for notes, some on paid plans."),
    ("Knowt",
     "A good all-round alternative with AI notes and flashcards, plus a large library of shared sets."),
    ("A general chatbot",
     "Fine for a quick one-off quiz, but questions aren't saved, scored or scheduled for review, and you have to "
     "write a good prompt each time."),
]

COMPARE_FAQ = [
    ("What is the best AI quiz generator for students?",
     "It depends on what you start from. If you have your own notes, slides or PDFs, a tool that writes questions "
     "from your material is best, because it tests what your course covers. QuizlyNotes is built for exactly that: "
     "it makes revision notes, a quiz with ten question types and flashcards from one upload, and it's free to use."),
    ("Is QuizlyNotes a free Quizlet alternative?",
     "Yes. QuizlyNotes is free, and unlike Quizlet's free plan it doesn't limit how much you study. The difference "
     "is that QuizlyNotes is built around your own notes: every upload becomes revision notes, a quiz with ten "
     "question types and a flashcard deck, whereas Quizlet is best known for its huge library of shared sets."),
    ("Can AI make flashcards and a quiz from the same notes?",
     "Yes. QuizlyNotes makes both from one upload: a practice quiz to check you understand, and a flashcard deck "
     "with spaced repetition for daily recall."),
    ("Why not just ask ChatGPT for a quiz?",
     "You can, but you'll need to paste your notes and write a prompt each time, and the questions aren't saved, "
     "scored or brought back when you're about to forget them. QuizlyNotes does all of that automatically."),
]


# --- Copy while monetisation is switched off ---------------------------------
# The constants above describe the Free/Pro plans. While MONETISATION_ENABLED
# is off, everything is free, so these replacements remove plan talk.

_FREE_MODE_FAQ = {
    "Is QuizlyNotes free?":
        "Yes, QuizlyNotes is completely free: notes, quizzes, flashcards, spaced repetition, games, mock exams "
        "and weak-spot review. Sign in with Google so your sets are saved to your library.",
    "What files can I upload?":
        "PDFs (including lecture slides and scanned pages), Word documents (.docx), PowerPoint files (.pptx) and "
        "plain text, up to 150 pages and 30MB. You can also paste notes directly.",
    "How many questions can I make?":
        "Choose Auto and the number is based on how much material there is, or pick between 5 and 60 questions.",
    "Is there a page limit?":
        "PDFs can be up to 150 pages and 30MB. For a whole textbook, upload one chapter at a time. Each chapter "
        "becomes its own quiz, grouped under the same subject.",
    "Is it free?":
        "Yes, it's free to use. You can also try it without an account on the home page.",
}
_FREE_MODE_TEXT = {
    "1. Sign in with Google and upload your PDF (up to 30 pages free, or 150 pages on Pro).":
        "1. Sign in with Google and upload your PDF (up to 150 pages and 30MB).",
    "Speed and Write games. Pro adds timed mock exams across a subject and weak-spot review.":
        "Speed and Write games, timed mock exams across a subject, and weak-spot review.",
}
_FREE_MODE_SECTION = ("Free to use",
                      ["QuizlyNotes is free. Make study sets, quizzes and flashcards from your own notes, and use "
                       "mock exams and weak-spot review across a whole subject. Sign in with Google to save "
                       "everything to your library."])
_FREE_MODE_FACTS = {"Price": "Free. Sign in with Google to save your sets."}


def _faq(items):
    return [(q, _FREE_MODE_FAQ.get(q, a)) for q, a in items]


def _text(t):
    if t in _FREE_MODE_TEXT:
        return _FREE_MODE_TEXT[t]
    return t.replace("Studying is free and unlimited.", "QuizlyNotes is free to use.")


def content(monetised: bool) -> dict:
    """Public-page copy for the current mode."""
    if monetised:
        return {"home_faq": HOME_FAQ, "landing_pages": LANDING_PAGES, "key_facts": KEY_FACTS,
                "compare_rows": COMPARE_ROWS, "compare_faq": COMPARE_FAQ}
    pages = {}
    for slug, page in LANDING_PAGES.items():
        sections = [(_FREE_MODE_SECTION if h == "Free to use" else (h, [_text(p) for p in ps]))
                    for h, ps in page["sections"]]
        pages[slug] = {**page, "sections": sections, "faq": _faq(page["faq"])}
    facts = [(k, _FREE_MODE_FACTS.get(k, _text(v))) for k, v in KEY_FACTS]
    rows = [r if r[0] != "Paid plan" else ("Price", "Free", "Free plan, plus Quizlet Plus",
                                           "Free plan, plus paid plans", "Free plan, plus subscriptions")
            for r in COMPARE_ROWS]
    rows = [r if r[0] != "Free studying limits" else (r[0], "None: free to use", *r[2:]) for r in rows]
    return {"home_faq": _faq(HOME_FAQ), "landing_pages": pages, "key_facts": facts,
            "compare_rows": rows, "compare_faq": _faq(COMPARE_FAQ)}
