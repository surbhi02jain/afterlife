"""Replies from institutions: the family uploads the letter (or message) a bank or insurer sent back.

Gemini reads it: what they decided, what they ask for, any time limit, and anything a genuine institution would never
ask (a fee to release money, an OTP). Code then acts on it, deterministically:
  - scam signals are checked in code too (agent.guardrails.scam_signals), on top of what Gemini reports. A letter with
    any red flag changes NOTHING in the case: no item is confirmed, no task moves, no cover letter is drafted;
  - the respond-by date is the letter date plus the days they gave (date arithmetic in code, never the model);
  - a letter confirming an account (confirms_account) turns the matching probable item into a confirmed one, with the letter as evidence
    (unless the family already decided about that item themselves);
  - the task moves to "in progress" (or "done" once the claim is settled), and a cover letter listing what they asked
    for is drafted (tools.letters.draft_reply_letter).
"""

from datetime import date, timedelta

from google.genai import errors, types
from pydantic import ValidationError

from agent.guardrails import SCAM_LABEL, redact_secrets, scam_signals
from app.config import get_settings
from app.gemini import GeminiUnreachable, generate, get_client
from app.models import Case, Evidence, InstitutionReply, ReplyReading, Requirement, mask_long_numbers
from tools.extraction import SUPPORTED_MIME_TYPES
from tools.finance import mask_identifier, parse_date
from tools.i18n import pick

REPLY_PROMPT = """\
A family in India wrote to banks, insurers and other institutions after {name} died. This is a reply they received
(a letter, email, SMS or chat message; a photo, scan or screenshot). Read it carefully and accurately.

- Copy only what is there. Use null when something is not stated. Never guess numbers, names or amounts.
- requirements: every document or action they ask the family for, one per item, in plain words.
- letter_date: YYYY-MM-DD; Indian dates are day first (05/10/2026 is 5 October 2026).
- red_flags: list anything a genuine bank or insurer would not ask: a fee, charge or tax to release the money, an
  OTP/PIN/password, installing an app or sharing the screen, paying to a personal UPI id, QR code or account,
  threats or pressure to act within hours. Quote the words briefly. Empty list if none.
- summary: two or three warm, plain sentences in {language}, for a grieving family member who is not a finance expert.
"""


class ReplyError(RuntimeError):
    """Gemini could not read the reply. Message is safe to show the user."""


def read_reply(data: bytes, mime_type: str, case: Case, *, client=None, model: str | None = None
               ) -> tuple[ReplyReading, str, str]:
    """(reading, raw reply, model)."""
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise ReplyError(f"Unsupported file type {mime_type}. Please upload a photo (PNG/JPEG) or a PDF.")
    if not data:
        raise ReplyError("The file is empty.")
    client = client or get_client()
    model = model or get_settings().extraction_model
    language = "Hindi (Devanagari script)" if case.language == "hi" else "English"
    try:
        response = generate(
            client, model=model,
            contents=[types.Part.from_bytes(data=data, mime_type=mime_type), "Read this reply."],
            config=types.GenerateContentConfig(
                system_instruction=REPLY_PROMPT.format(name=case.deceased_name, language=language),
                response_mime_type="application/json",
                response_json_schema=ReplyReading.model_json_schema(),
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
            ),
        )
    except errors.APIError as exc:
        raise ReplyError(f"Gemini request failed ({exc.code}): {exc.message}") from exc
    except GeminiUnreachable as exc:
        raise ReplyError(str(exc)) from exc
    if not response.text:
        raise ReplyError("Gemini returned an empty response for this reply.")
    return parse_reply(response.text), response.text, model


def parse_reply(raw: str) -> ReplyReading:
    try:
        return ReplyReading.model_validate_json(raw)
    except ValidationError as exc:
        raise ReplyError(f"Gemini's reading of the reply did not match the schema: {exc.errors()[:3]}") from exc


def respond_by(letter_date: str | None, days: int | None, received: date) -> str | None:
    if not days or days <= 0:
        return None
    start = parse_date(letter_date) or received
    return (start + timedelta(days=days)).isoformat()


def red_flags(reading: ReplyReading, lang: str) -> list[str]:
    """Plain-language warnings: what code finds in the letter as read (and in Gemini's own flags). If Gemini flagged
    something code has no rule for, it still counts."""
    # Not the summary: it is Gemini's note for the family and repeats the bank's own "never share your OTP" warnings.
    found = [pick(lang, *SCAM_LABEL[key]) for key in scam_signals(
        *(r.document for r in reading.requirements), *(r.detail for r in reading.requirements), *reading.red_flags)]
    if not found and any(f.strip() for f in reading.red_flags):
        found = [pick(lang, "asks for something a genuine bank or insurer would not",
                      "कुछ ऐसा माँगता है जो असली बैंक या बीमा कंपनी नहीं माँगती")]
    return found


def apply_reply(case: Case, task_id: str, reading: ReplyReading, filename: str, model: str,
                today: date | None = None) -> InstitutionReply:
    """Record the reply and act on it. Mutates case. Raises KeyError for an unknown task."""
    today = today or date.today()
    task = next((t for t in (case.plan.tasks if case.plan else []) if t.id == task_id), None)
    if task is None:
        raise KeyError(task_id)
    flags = red_flags(reading, case.language)
    reply = InstitutionReply(
        task_id=task.id,
        institution=(reading.institution or "").strip() or task.institution,  # as they print it, for the cover letter
        filename=filename,
        letter_date=reading.letter_date if parse_date(reading.letter_date) else None,
        reference_masked=mask_long_numbers(reading.reference_number) if reading.reference_number else None,
        outcome=reading.outcome,
        summary=mask_long_numbers(redact_secrets(reading.summary)),
        requirements=[Requirement(document=mask_long_numbers(r.document.strip()),
                                  detail=mask_long_numbers(r.detail.strip()) if r.detail else None)
                      for r in reading.requirements if r.document.strip()],
        respond_by=respond_by(reading.letter_date, reading.respond_within_days, today),
        red_flags=flags,
        red_flag_quotes=[mask_long_numbers(f.strip()) for f in reading.red_flags if f.strip()] if flags else [],
        model=model,
    )
    case.replies.append(reply)
    if flags:  # a suspicious letter changes nothing: the family is warned, and gets no checklist or deadline from it
        reply.requirements, reply.respond_by = [], None
        return reply

    if reading.confirms_account and reading.outcome != "no_record_found":
        reply.confirmed_item_id = _confirm_item(case, task, reading, reply, filename)
    if reading.outcome == "claim_settled":
        task.board_status = "done"
    elif task.board_status == "todo":
        task.board_status = "in_progress"
    return reply


def _confirm_item(case: Case, task, reading: ReplyReading, reply: InstitutionReply, filename: str) -> str | None:
    """The institution confirmed in writing that the account or policy exists: the probable item becomes confirmed."""
    items = [case.get_item(ref.item_id) for ref in task.items]
    items = [i for i in items if i is not None]
    same_type = [i for i in items if reading.item_type and i.type == reading.item_type]
    item = next((i for i in [*same_type, *items] if i.status == "probable"), None)
    if item is None or item.decided_by_user:
        return None
    item.status, item.confidence = "confirmed", "high"
    item.evidence.append(Evidence(
        document_id=f"reply:{reply.id}", document_name=filename, date=reply.letter_date,
        description=pick(case.language, f"{task.institution} confirmed it in writing",
                         f"{task.institution} ने लिखित में पुष्टि की"), amount=reading.amount))
    if reading.identifier and not item.identifier_masked:
        item.identifier_masked = mask_identifier(reading.identifier)  # only the last 4 are kept
    if reading.nominee and not item.nominee:
        item.nominee = reading.nominee.strip()
    if reading.amount is not None and item.amount is None:
        item.amount, item.amount_as_of = reading.amount, reply.letter_date
        item.amount_label = pick(case.language, "as stated in their letter", "उनके पत्र के अनुसार")
    return item.id
