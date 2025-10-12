# Flashcard-generator

 Generate flashcards from uploaded slides / lecture notes. Create lessons and quizzes utilising flash cards, tracking user progression.

## Input and output sanitisation

The application applies consistent sanitisation to user supplied fields, session mutations, and AI generated content to minimise the risk of cross-site scripting and data pollution:

- All text fields from HTML forms (set names, questions, answers, scores, and identifiers) are cleaned via the shared `sanitize_text` helper, removing control characters and HTML tags while enforcing sensible length limits before storage or rendering.
- JSON payloads exchanged with the SPA features (note editing, quiz generation, and AI powered helpers) are normalised recursively through `sanitize_structure`, ensuring nested strings are stripped of tags and truncated before use.
- Model outputs from `utils.ai_utils` are run through the same helpers before being persisted to the database or sent back to the browser, preventing unexpected markup in generated questions or notes.
- Legacy database values are re-sanitised on read, so previously stored strings also pass through the new filters before being rendered in templates.

These defences complement Flask/Jinja's auto-escaping and keep rendered templates free from unsanitised text, even if earlier data ingestion predates the new safeguards.

