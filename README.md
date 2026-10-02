# QuizlyNotes

Turn notes, PDFs and lecture slides into revision notes, practice quizzes and spaced-repetition flashcards.

Live at [quizlynotes.com](https://quizlynotes.com).

## What changed in v2

| Area | v1 | v2 |
|---|---|---|
| **Data loss** | SQLite file inside the Cloud Run container. Wiped whenever the instance scaled to zero or redeployed, which is why sets disappeared. | Hosted Postgres (Neon/Supabase) via `DATABASE_URL`. Survives restarts and redeploys. Notes are saved as soon as they're generated and autosave while editing. |
| **AI** | `gpt-4o-mini`, text-only extraction, notes from arbitrary 850-character slices, one API call per question, unvalidated JSON (a bad response crashed the request). | Gemini reads the **whole PDF natively** (diagrams, scanned slides). Schema-enforced JSON, server-side validation (e.g. the right answer must be one of the options), retries, friendly errors. Two calls per set: notes, then cards. |
| **Question quality** | Random sampling of sections, generic prompt. | Coverage across every section, plausible distractors, explanations on every answer, difficulty and question-type controls, atomic flashcards. |
| **Security** | Any signed-in user could delete or edit another user's set by ID. No CSRF protection. Fallback secret key. `.env` copied into the Docker image. | Ownership enforced on every query (404 otherwise), CSRF on all forms and API calls, a secret key is required in production, `.dockerignore`, rate limits on AI endpoints. |
| **Navigation** | Current set stored in the session (`set-id`), so back and refresh broke and pages were unbookmarkable. | Real URLs: `/sets/<id>`, `/sets/<id>/quiz` and so on. Old URLs redirect. |
| **Quiz** | Apostrophes in answers broke the true/false and multiple-choice buttons. Answer checking depended on a CDN. Ordering was desktop drag-only. | Renders from JSON with safe escaping, forgiving answer matching (typos, plurals, articles), "I was right" override, ordering works on touch and with the keyboard, review of missed questions, "retry missed". |
| **Flashcards** | The `/sets` library existed but nothing created flashcards any more. | Generated with every quiz, flip cards with spaced repetition (Again/Hard/Good/Easy), due counts in the library. |
| **Design** | Indigo-violet gradient "AI app" look. | Paper, ink and highlighter. Light and dark themes, mobile-first. |
| **SEO** | One landing page with no meta description, no sitemap, invented stats and testimonials, and FAQ answers promising features that didn't exist. | Keyword-targeted landing pages, meta and OG tags, JSON-LD (WebApplication, FAQPage, Breadcrumbs), sitemap.xml, robots.txt, an honest FAQ, a guest "try it" box, and privacy and terms pages. |
| **Other** | Settings toggles that did nothing. | Export all data (JSON), delete account with confirmation. Upload PDF, DOCX, PPTX or TXT, or paste text. |

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env          # then edit
flask --app wsgi run --debug
```

With `AI_PROVIDER=fake` and `ENABLE_DEV_LOGIN=true` you don't need any keys. Go to <http://localhost:5000/dev-login>. Leave `DATABASE_URL` blank to use a local SQLite file.

Tests: `pytest`

## Deploy (Cloud Run)

### 1. Database: Neon (free)

1. Create a project at [neon.tech](https://neon.tech) in a region near your Cloud Run region (e.g. `europe-west2` → AWS London).
2. Copy the connection string (`postgresql://...?sslmode=require`). That's your `DATABASE_URL`.
3. Tables are created automatically on deploy (`flask db upgrade` runs before the server starts).

### 2. Gemini API key

Create a key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey). **Turn on billing for the key's project.** On the free tier, Google may use prompts to improve its products, which you don't want for students' uploads, and the rate limits are low. A typical lecture costs a few cents to process.

The model is set with `GEMINI_MODEL` (default `gemini-3.8-flash`). Change it there when Google releases a newer Flash model; no code changes are needed.

### 3. Google sign-in

The callback URL is unchanged: `https://quizlynotes.com/login/google/authorized`. The existing OAuth client works as it is.

### 4. Deploy

```bash
gcloud run deploy quizlynotes --source . --region europe-west2 \
  --timeout 300 --memory 1Gi \
  --set-env-vars APP_ENV=production,SITE_URL=https://quizlynotes.com,GEMINI_MODEL=gemini-3.8-flash \
  --set-secrets FLASK_SECRET_KEY=flask-secret:latest,DATABASE_URL=database-url:latest,GEMINI_API_KEY=gemini-key:latest,GOOGLE_CLIENT_ID=google-client-id:latest,GOOGLE_CLIENT_SECRET=google-client-secret:latest
```

(Or set them as plain env vars in the Cloud Run console.) `--timeout 300` matters: a long PDF can take a minute or two to generate.

### 5. After deploying (SEO)

1. In Search Console, submit `https://quizlynotes.com/sitemap.xml`.
2. Use URL Inspection → Request indexing for `/`, `/notes-to-quiz`, `/pdf-to-quiz` and `/notes-to-flashcards`.
3. Check the rich results with Google's Rich Results Test (FAQ, breadcrumbs).

## Configuration

See `.env.example` for every option. Key ones:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string (required in production) |
| `GEMINI_API_KEY` / `GEMINI_MODEL` / `GEMINI_FAST_MODEL` | AI provider. The fast model is used for the guest demo and "Improve" |
| `GENERATION_LIMIT` / `GUEST_LIMIT` | Rate limits (per user / per IP) |
| `ENABLE_GUEST_DEMO` | Show the "try it" box on landing pages |
| `RATELIMIT_STORAGE_URI` | Defaults to in-memory, which is per instance. Use Redis if you scale out |

## Project layout

```
quizlynotes/
  ai/            extract.py (files → model input), prompts.py, schemas.py (structured output),
                 validate.py (checks model output), providers.py (Gemini + offline fake)
  services/      study.py: create/update sets, scoring, spaced repetition
  views/         public.py (landing/SEO/guest), study.py (app pages), api.py (JSON)
  templates/     public/, app/, partials/
  static/        css/app.css, js/ (one small file per page, no build step)
  seo.py         landing page copy and FAQs
migrations/      Alembic (flask db migrate / upgrade)
tests/
```

Schema changes: edit `models.py`, then `flask --app wsgi db migrate -m "describe change"` and commit the generated file.
