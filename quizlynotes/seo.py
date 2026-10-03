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
    ("Explain", "Write a short explanation, then check it against the key points a good answer covers."),
    ("Flashcards", "One idea per card, reviewed with spaced repetition so you see hard cards more often."),
]

HOME_FAQ = [
    ("What is QuizlyNotes?",
     "QuizlyNotes is a free AI study tool that turns your notes into quizzes and flashcards. Upload lecture "
     "slides, a PDF, a Word document or paste your notes, and it writes revision notes, practice questions "
     "and flashcards for you to study."),
    ("Is QuizlyNotes free?",
     "Yes. You can create and study quiz notes for free with a Google account. There are fair-use limits on "
     "how many quizzes you can generate per hour, to keep the service running for everyone."),
    ("What files can I upload?",
     "PDFs (including lecture slides and scanned pages), Word documents (.docx), PowerPoint files (.pptx) and "
     "plain text. You can also paste notes directly. Files can be up to 30MB."),
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
             "Choose Auto and the number is based on how much material there is, or pick between 5 and 60 questions."),
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
             ["1. Sign in with Google and upload your PDF (up to 30MB and 150 pages).",
              "2. Review the generated notes, organised by topic. Fix or delete anything you don't need.",
              "3. Generate a quiz with the question types and difficulty you want.",
              "4. Study the notes and answer questions topic by topic, then review flashcards on the days they're due."]),
        ],
        "faq": [
            ("Is there a page limit?",
             "PDFs can be up to 150 pages and 30MB. For a whole textbook, upload one chapter at a time. Each "
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
}

RELATED_LINKS = [
    ("notes-to-quiz", "Turn notes into a quiz"),
    ("pdf-to-quiz", "PDF and slides to quiz"),
    ("notes-to-flashcards", "Notes to flashcards"),
]
