"""AI providers: Gemini for real use, Fake for local development and tests."""
from __future__ import annotations

import io
import logging
import time

from flask import current_app

from . import prompts
from .extract import Source
from .schemas import CardDeck, NoteSections, NotesDoc, QuickStudy
from .validate import clean_cards, clean_notes

log = logging.getLogger(__name__)

# Above this size a PDF goes through the Files API instead of inline bytes
# (inline requests are capped at 20MB including the prompt).
INLINE_PDF_LIMIT = 15 * 1024 * 1024


class AIError(RuntimeError):
    """Generation failed. The message is safe to show to users."""


def plan_counts(sections: list[dict], quiz_count: int | None) -> tuple[int, int]:
    """Pick sensible card numbers when the user chooses 'Auto'."""
    points = sum(len(s.get("points", [])) for s in sections)
    if not quiz_count:
        quiz_count = max(6, min(40, round(len(sections) * 1.5 + points / 12)))
    flash_count = max(6, min(50, round(points / 3)))
    return quiz_count, flash_count


class BaseProvider:
    def make_notes(self, source: Source) -> dict:
        raise NotImplementedError

    def make_cards(self, sections, quiz_count, flash_count, kinds, difficulty) -> list[dict]:
        raise NotImplementedError

    def enhance(self, heading: str, sections: list[dict], mode: str = "improve") -> list[dict]:
        raise NotImplementedError

    def quick_study(self, text: str) -> dict:
        raise NotImplementedError


class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str, model: str, fast_model: str, fallback_model: str = ""):
        from google import genai
        from google.genai import types

        self.types = types
        self.model = model
        self.fast_model = fast_model or model
        # Used when the main model is overloaded (503) or rate limited (429).
        self.fallback_model = fallback_model if fallback_model and fallback_model != model else ""
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=240_000,  # ms
                retry_options=types.HttpRetryOptions(attempts=3, initial_delay=2.0, max_delay=20.0),
            ),
        )

    # -- helpers ---------------------------------------------------------
    def _generate(self, *, model: str, contents, system: str, schema, temperature: float):
        types = self.types
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
            max_output_tokens=32768,
        )
        models = [model] + ([self.fallback_model] if self.fallback_model and self.fallback_model != model else [])
        last_error: Exception | None = None
        for attempt, current in enumerate(models + [models[-1]]):
            try:
                response = self.client.models.generate_content(
                    model=current, contents=contents, config=config
                )
                parsed = getattr(response, "parsed", None)
                if isinstance(parsed, schema):
                    return parsed
                if response.text:
                    return schema.model_validate_json(response.text)
                last_error = AIError("The AI returned an empty response.")
            except AIError as exc:
                last_error = exc
            except Exception as exc:  # network errors, invalid JSON, safety blocks
                code = getattr(exc, "code", None)
                log.warning("Gemini call failed (model %s, attempt %s): %s", current, attempt + 1, exc)
                last_error = exc
                if code in (400, 401, 402, 403, 404):
                    # Bad key, no credit, unknown model: retrying won't help.
                    log.error("Gemini configuration problem (HTTP %s). Check GEMINI_API_KEY, "
                              "billing/credits in AI Studio, and GEMINI_MODEL.", code)
                    break
            time.sleep(1.5)
        log.error("Gemini generation failed: %s", last_error)
        raise AIError("The AI couldn't process that just now. Please try again in a minute.")

    def _pdf_part(self, source: Source):
        types = self.types
        if len(source.pdf_bytes) <= INLINE_PDF_LIMIT:
            return types.Part.from_bytes(data=source.pdf_bytes, mime_type="application/pdf"), None
        uploaded = self.client.files.upload(
            file=io.BytesIO(source.pdf_bytes),
            config=types.UploadFileConfig(mime_type="application/pdf", display_name=source.name[:100]),
        )
        # Large files are processed asynchronously; wait until ready.
        for _ in range(60):
            state = getattr(getattr(uploaded, "state", None), "name", "ACTIVE")
            if state != "PROCESSING":
                break
            time.sleep(2)
            uploaded = self.client.files.get(name=uploaded.name)
        if getattr(getattr(uploaded, "state", None), "name", "ACTIVE") == "FAILED":
            raise AIError("We couldn't read that PDF. Try exporting it again, or upload a smaller file.")
        return uploaded, uploaded.name

    # -- public API ------------------------------------------------------
    def make_notes(self, source: Source) -> dict:
        uploaded_name = None
        try:
            if source.is_pdf:
                part, uploaded_name = self._pdf_part(source)
                contents = [part, prompts.NOTES_USER]
            else:
                contents = prompts.NOTES_USER_TEXT.format(text=source.text)
            result = self._generate(
                model=self.model, contents=contents, system=prompts.NOTES_SYSTEM,
                schema=NotesDoc, temperature=0.3,
            )
        finally:
            if uploaded_name:
                try:
                    self.client.files.delete(name=uploaded_name)
                except Exception:  # pragma: no cover - best effort cleanup
                    pass
        data = result.model_dump()
        data["sections"] = clean_notes(data["sections"])
        if not data["sections"]:
            raise AIError("We couldn't find any study content in that file. Is it mostly images of text? Try a clearer copy.")
        return data

    def make_cards(self, sections, quiz_count, flash_count, kinds, difficulty) -> list[dict]:
        user = prompts.CARDS_USER.format(
            quiz_count=quiz_count,
            flash_count=flash_count,
            kinds=", ".join(kinds),
            difficulty_text=prompts.DIFFICULTY_TEXT.get(difficulty, prompts.DIFFICULTY_TEXT["medium"]),
            notes=prompts.format_notes_for_prompt(sections),
        )
        result = self._generate(
            model=self.model, contents=user, system=prompts.CARDS_SYSTEM,
            schema=CardDeck, temperature=0.6,
        )
        cards = [c.model_dump() for c in result.cards]
        allowed = set(kinds) | {"flashcard"}
        cards = [c for c in clean_cards(cards, len(sections)) if c["kind"] in allowed]
        if not cards:
            raise AIError("The AI didn't produce any usable questions. Please try again.")
        return cards

    def enhance(self, heading: str, sections: list[dict], mode: str = "improve") -> list[dict]:
        system, user = (
            (prompts.SIMPLIFY_SYSTEM, prompts.SIMPLIFY_USER) if mode == "simplify"
            else (prompts.ENHANCE_SYSTEM, prompts.ENHANCE_USER)
        )
        result = self._generate(
            model=self.fast_model,
            contents=user.format(heading=heading, notes=prompts.format_notes_for_prompt(sections)),
            system=system, schema=NoteSections, temperature=0.3,
        )
        cleaned = clean_notes([s.model_dump() for s in result.sections])
        for s in cleaned:
            s["heading"] = heading or s["heading"]
        return cleaned

    def quick_study(self, text: str) -> dict:
        result = self._generate(
            model=self.fast_model,
            contents=prompts.QUICK_USER.format(text=text, quiz_count=6, flash_count=6),
            system=prompts.QUICK_SYSTEM, schema=QuickStudy, temperature=0.5,
        )
        data = result.model_dump()
        data["sections"] = clean_notes(data["sections"])
        data["cards"] = clean_cards(data["cards"], len(data["sections"]))
        if not data["sections"] or not data["cards"]:
            raise AIError("We couldn't make a quiz from that text. Try pasting a longer passage.")
        return data


class FakeProvider(BaseProvider):
    """Deterministic offline provider, so the app runs without an API key."""

    def make_notes(self, source: Source) -> dict:
        title = source.name.rsplit(".", 1)[0] if source.name else "Sample notes"
        return {
            "title": title[:80] or "Sample notes",
            "subject": "Biology",
            "sections": clean_notes(_SAMPLE_SECTIONS),
        }

    def make_cards(self, sections, quiz_count, flash_count, kinds, difficulty) -> list[dict]:
        pool = [c for c in _SAMPLE_CARDS if c["kind"] in set(kinds) | {"flashcard"}]
        cards = clean_cards(pool, len(sections))
        quiz = [c for c in cards if c["kind"] != "flashcard"][:quiz_count]
        flash = [c for c in cards if c["kind"] == "flashcard"][:flash_count]
        return quiz + flash

    def enhance(self, heading, sections, mode="improve"):
        out = clean_notes(sections)
        for s in out:
            if mode == "simplify":
                s["points"] = [p for p in s["points"] if p["level"] == 1][:3] or s["points"][:1]
            else:
                s["points"].append({"text": "Example: added by the offline demo provider.", "level": 2})
        return out

    def quick_study(self, text: str) -> dict:
        sections = clean_notes(_SAMPLE_SECTIONS)
        return {
            "title": "Cell respiration",
            "subject": "Biology",
            "sections": sections,
            "cards": clean_cards(_SAMPLE_CARDS, len(sections)),
        }


_SAMPLE_SECTIONS = [
    {"heading": "Cell respiration", "subheading": "Overview", "points": [
        {"text": "Cellular respiration releases energy from glucose to make ATP.", "level": 1},
        {"text": "Aerobic respiration needs oxygen and produces carbon dioxide and water.", "level": 1},
        {"text": "Overall: C6H12O6 + 6O2 -> 6CO2 + 6H2O + energy", "level": 2},
    ]},
    {"heading": "Cell respiration", "subheading": "Stages", "points": [
        {"text": "Glycolysis happens in the cytoplasm and splits glucose into two pyruvate.", "level": 1},
        {"text": "The Krebs cycle happens in the mitochondrial matrix.", "level": 1},
        {"text": "Oxidative phosphorylation produces most of the ATP.", "level": 1},
        {"text": "It uses the electron transport chain on the inner mitochondrial membrane.", "level": 2},
    ]},
    {"heading": "Anaerobic respiration", "subheading": "In muscles", "points": [
        {"text": "Without oxygen, muscle cells convert pyruvate to lactate.", "level": 1},
        {"text": "This produces far less ATP than aerobic respiration (2 vs about 30-32).", "level": 2},
    ]},
]

_SAMPLE_CARDS = [
    {"section": 1, "kind": "matching", "prompt": "Match each stage to where it happens.",
     "options": ["Glycolysis", "Krebs cycle", "Electron transport chain"],
     "answers": ["Cytoplasm", "Mitochondrial matrix", "Inner mitochondrial membrane"],
     "explanation": "Glycolysis is cytoplasmic; the later stages happen in the mitochondria."},
    {"section": 0, "kind": "multi_select", "prompt": "Which are products of aerobic respiration? Select all that apply.",
     "options": ["Carbon dioxide", "Water", "ATP", "Oxygen", "Glucose"],
     "answers": ["Carbon dioxide", "Water", "ATP"],
     "explanation": "Oxygen and glucose are reactants; CO2, water and ATP are produced."},
    {"section": 2, "kind": "categorize", "prompt": "Sort each feature into aerobic or anaerobic respiration.",
     "options": ["Needs oxygen", "Produces lactate", "About 30-32 ATP", "2 ATP per glucose"],
     "answers": ["Aerobic", "Anaerobic", "Aerobic", "Anaerobic"],
     "explanation": "Aerobic respiration uses oxygen and yields far more ATP than anaerobic."},
    {"section": 2, "kind": "numeric", "prompt": "How many ATP does anaerobic respiration produce per glucose?",
     "options": [], "answers": ["2", "ATP"], "explanation": "Only glycolysis runs, giving a net 2 ATP."},
    {"section": 0, "kind": "odd_one_out", "prompt": "Which of these is NOT a product of aerobic respiration?",
     "options": ["Carbon dioxide", "Water", "ATP", "Lactate"], "answers": ["Lactate"],
     "explanation": "Lactate is made in anaerobic respiration; aerobic respiration makes CO2, water and ATP."},
    {"section": 0, "kind": "multiple_choice", "prompt": "What is the main purpose of cellular respiration?",
     "options": ["To make ATP", "To make glucose", "To absorb light", "To store oxygen"],
     "answers": ["To make ATP"], "explanation": "Respiration releases energy from glucose and stores it as ATP."},
    {"section": 1, "kind": "true_false", "prompt": "Glycolysis takes place in the mitochondria.",
     "options": [], "answers": ["false"], "explanation": "Glycolysis happens in the cytoplasm; the Krebs cycle is in the mitochondria."},
    {"section": 1, "kind": "fill_blank", "prompt": "The Krebs cycle takes place in the mitochondrial {blank}.",
     "options": [], "answers": ["matrix"], "explanation": "The enzymes of the Krebs cycle are in the matrix."},
    {"section": 1, "kind": "ordering", "prompt": "Put the stages of aerobic respiration in order.",
     "options": ["Glycolysis", "Krebs cycle", "Oxidative phosphorylation"], "answers": [],
     "explanation": "Glucose is split first, then pyruvate is oxidised, then the electron transport chain makes ATP."},
    {"section": 2, "kind": "short_answer", "prompt": "What do muscle cells convert pyruvate into without oxygen?",
     "options": [], "answers": ["lactate", "lactic acid"], "explanation": "Anaerobic respiration in animals produces lactate."},
    {"section": 0, "kind": "true_false", "prompt": "Aerobic respiration produces carbon dioxide and water.",
     "options": [], "answers": ["true"], "explanation": "Glucose and oxygen become CO2 and water, releasing energy."},
    {"section": 0, "kind": "flashcard", "prompt": "What is ATP?", "options": [],
     "answers": ["The cell's energy currency (adenosine triphosphate)."], "explanation": ""},
    {"section": 1, "kind": "flashcard", "prompt": "Where does glycolysis happen?", "options": [],
     "answers": ["In the cytoplasm."], "explanation": ""},
    {"section": 1, "kind": "flashcard", "prompt": "Which stage makes most ATP?", "options": [],
     "answers": ["Oxidative phosphorylation (electron transport chain)."], "explanation": ""},
    {"section": 2, "kind": "flashcard", "prompt": "Anaerobic respiration in muscles produces...", "options": [],
     "answers": ["Lactate, and only 2 ATP per glucose."], "explanation": ""},
]



def get_provider() -> BaseProvider:
    app_provider = current_app.extensions.get("ai_provider")
    if app_provider is not None:
        return app_provider
    cfg = current_app.config
    if cfg["AI_PROVIDER"] == "fake" or not cfg.get("GEMINI_API_KEY"):
        if cfg.get("IS_PRODUCTION") and cfg["AI_PROVIDER"] != "fake":
            raise AIError("AI generation isn't configured on the server.")
        provider: BaseProvider = FakeProvider()
    else:
        provider = GeminiProvider(cfg["GEMINI_API_KEY"], cfg["GEMINI_MODEL"], cfg["GEMINI_FAST_MODEL"],
                                  cfg["GEMINI_FALLBACK_MODEL"])
    current_app.extensions["ai_provider"] = provider
    return provider

