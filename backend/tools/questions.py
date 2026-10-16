"""Follow-up questions about gaps in the case.

find_gaps() decides WHAT is missing (deterministic). Gemini only phrases 2 to 4 of those gaps as warm, plain
questions, citing gap ids we gave it. apply_answer() updates the case deterministically.
"""

from dataclasses import dataclass

from google.genai import errors, types
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings
from app.gemini import generate, get_client
from app.models import Case, Question, QuestionTarget, utc_now
from tools.i18n import inr, label, nice_date, pick

MAX_QUESTIONS = 4


@dataclass
class Gap:
    id: str
    target: QuestionTarget
    item_id: str | None
    fact: str  # English description of what is missing, for the model
    options: list[str]


def _options(target: str, lang: str) -> list[str]:
    if target == "confirm_item":
        return [pick(lang, "Yes", "हाँ"), pick(lang, "No", "नहीं"), pick(lang, "Not sure", "पक्का नहीं")]
    if target == "death_certificate":
        return [pick(lang, "Yes", "हाँ"), pick(lang, "Not yet", "अभी नहीं"), pick(lang, "Applied for it", "आवेदन किया है")]
    return []


def find_gaps(case: Case) -> list[Gap]:
    """Most important first. Excludes anything already asked and still open, or already answered."""
    asked = {(q.target, q.item_id) for q in case.questions}
    gaps: list[Gap] = []

    def add(target, item_id, fact):
        if (target, item_id) not in asked:
            gap_id = f"{target}:{item_id[:8]}" if item_id else target  # stable while the case changes
            gaps.append(Gap(gap_id, target, item_id, fact, _options(target, case.language)))

    for item in [*case.assets, *case.liabilities]:
        if item.status == "probable" and not item.decided_by_user:
            clues = "; ".join(f"{e.date} {e.description} {inr(e.amount)}" for e in item.evidence[:3])
            add("confirm_item", item.id, f"We think there may be a {label(item.type, 'en')} with {item.institution}, "
                                         f"based on: {clues}. Does the family know about it?")
    if case.facts.death_certificate is None:
        add("death_certificate", None, "Whether the family already has the death certificate.")
    for item in [*case.assets, *case.liabilities]:
        if item.status == "confirmed" and not item.nominee and item.type not in ("home_loan", "personal_loan",
                                                                                   "vehicle_loan", "other_loan"):
            add("item_nominee", item.id, f"Who is the nominee for the {label(item.type, 'en')} with "
                                         f"{item.institution}? It is not shown on the document.")
    if not case.facts.claimant_name:
        add("claimant_name", None, "The full name of the family member who will sign letters and claims.")
    if not case.facts.claimant_address:
        add("claimant_address", None, "The postal address to put on the letters.")
    return gaps


# --- Gemini phrasing -----------------------------------------------------------------------------

class QuestionDraft(BaseModel):
    gap_id: str = Field(description="The id of the gap this question is about, exactly as given.")
    text: str = Field(description="The question, warm and plain, one sentence, in the requested language.")
    why: str = Field(description="Very short reason we are asking, in the requested language.")


class QuestionDrafts(BaseModel):
    questions: list[QuestionDraft]


QUESTION_PROMPT = """\
You write follow-up questions for a family that has just lost {name}, who died on {dod}.
The person answering is the deceased's {relationship}. They are grieving and not finance experts.
Pick the {n} most useful gaps below (earlier ones matter more) and write one question for each.
- Be gentle, short and concrete. No jargon; explain any term in a few words.
- Refer to the deceased by name. Never ask for passwords, PINs, OTPs or card numbers.
- Something we only THINK exists must be asked as a question, never stated as fact.
- Write in {language}. Use only the gap ids given.
"""


def draft_questions(case: Case, gaps: list[Gap], *, client=None, model: str | None = None) -> QuestionDrafts:
    client = client or get_client()
    model = model or get_settings().reasoning_model
    language = "Hindi (Devanagari script)" if case.language == "hi" else "English"
    listing = "\n".join(f"{g.id}: {g.fact}" for g in gaps)
    try:
        response = generate(
            client, model=model, contents=f"GAPS:\n{listing}",
            config=types.GenerateContentConfig(
                system_instruction=QUESTION_PROMPT.format(
                    name=case.deceased_name, dod=nice_date(case.date_of_death), relationship=case.relationship,
                    n=min(MAX_QUESTIONS, len(gaps)), language=language),
                response_mime_type="application/json",
                response_json_schema=QuestionDrafts.model_json_schema(),
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
            ),
        )
    except errors.APIError as exc:
        raise QuestionError(f"Gemini request failed ({exc.code}): {exc.message}") from exc
    try:
        return QuestionDrafts.model_validate_json(response.text or "")
    except ValidationError as exc:
        raise QuestionError(f"Gemini's questions did not match the schema: {exc.errors()[:3]}") from exc


class QuestionError(RuntimeError):
    pass


def add_questions(case: Case, gaps: list[Gap], drafts: list[QuestionDraft]) -> list[Question]:
    """Turn drafts into questions, keeping only ones that cite a real gap. Mutates case."""
    by_id = {g.id: g for g in gaps}
    created, used = [], set()
    for d in drafts:
        gap = by_id.get(d.gap_id)
        if gap is None or gap.id in used or not d.text.strip():
            continue
        used.add(gap.id)
        q = Question(text=d.text.strip(), why=d.why.strip() or None, target=gap.target, item_id=gap.item_id,
                     options=gap.options)
        case.questions.append(q)
        created.append(q)
        if len(created) == MAX_QUESTIONS:
            break
    return created


# --- answers ---------------------------------------------------------------------------------------

YES = {"yes", "y", "haan", "han", "हाँ", "हां"}
NO = {"no", "n", "nahin", "nahi", "नहीं", "not yet", "अभी नहीं"}


def apply_answer(case: Case, question_id: str, answer: str) -> Question:
    q = case.get_question(question_id)
    if q is None:
        raise KeyError(question_id)
    answer = answer.strip()
    normalized = answer.lower()
    item = case.get_item(q.item_id) if q.item_id else None

    if q.target == "confirm_item" and item:
        if normalized in YES:
            item.status, item.decided_by_user = "confirmed", True
        elif normalized in NO:
            item.status, item.decided_by_user = "rejected", True
    elif q.target == "item_nominee" and item:
        item.nominee = answer
    elif q.target == "claimant_name":
        case.facts.claimant_name = answer
    elif q.target == "claimant_address":
        case.facts.claimant_address = answer
    elif q.target == "death_certificate":
        case.facts.death_certificate = "yes" if normalized in YES else "applied" if "appl" in normalized or "आवेदन" in answer else "no"

    q.answer, q.status, q.answered_at = answer, "answered", utc_now()
    return q


def confirm_drafts_first(case: Case, gaps: list[Gap], drafts: list[QuestionDraft]) -> list[QuestionDraft]:
    """Guardrail: every probable item gets asked about, whatever the model chose. Missing ones get a templated
    question, and all confirm questions go first (add_questions then applies the cap)."""
    lang = case.language
    covered = {d.gap_id for d in drafts}
    templated = []
    for gap in gaps:
        if gap.target != "confirm_item" or gap.id in covered:
            continue
        item = case.get_item(gap.item_id)
        kind = label(item.type, lang)
        templated.append(QuestionDraft(
            gap_id=gap.id,
            text=pick(lang, f"Did {case.deceased_name} have a {kind} with {item.institution}?",
                      f"क्या {item.institution} में {case.deceased_name} के नाम पर कोई {kind} है?"),
            why=pick(lang, "We noticed payments that point to it, but found no document.",
                     "हमें इससे जुड़े भुगतान दिखे, पर कोई दस्तावेज़ नहीं मिला।")))
    confirm_ids = {g.id for g in gaps if g.target == "confirm_item"}
    model_confirm = [d for d in drafts if d.gap_id in confirm_ids]
    others = [d for d in drafts if d.gap_id not in confirm_ids]
    return [*model_confirm, *templated, *others]
