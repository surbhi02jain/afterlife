"""Family memories: "he paid something to an insurance company every March".

Gemini listens to the recording (or reads what the family typed) and turns it into clues: what kind of account,
which institution, any months or amounts mentioned. Code then does the checking, deterministically:
  - each clue is matched against transactions already read from the documents (institution named in the narration,
    or for an unnamed institution, words typical of that kind of payment), narrowed by any month or amount mentioned;
  - the clue is merged through the same upsert() dedup path as documents and inference, always as PROBABLE;
  - confidence comes from the evidence, never from the model: a memory alone is low, a memory backed by one
    matching payment is medium, by two or more is high.
"""

import re
from datetime import date

from google.genai import errors, types
from pydantic import ValidationError

from agent.guardrails import redact_secrets
from app.config import get_settings
from app.gemini import GeminiUnreachable, generate, get_client
from app.models import (Case, Confidence, Evidence, Memory, MemoryClue, MemoryReading, MemoryResult,
                        mask_long_numbers)
from tools.asset_map import Candidate, refresh_recurring, upsert
from tools.finance import institution_tokens, parse_date
from tools.i18n import pick
from tools.inference import FAMILY_TOO_EN, FAMILY_TOO_HI, RANK, TxnRef, collect_transactions

AUDIO_MIME_TYPES = {"audio/wav", "audio/x-wav", "audio/webm", "audio/ogg", "audio/mpeg", "audio/mp3", "audio/mp4",
                    "audio/m4a", "audio/aac", "audio/flac"}
# Names Gemini documents for the same formats (https://ai.google.dev/gemini-api/docs/audio, checked 2026-10-18).
GEMINI_AUDIO_NAMES = {"audio/x-wav": "audio/wav", "audio/mp4": "audio/m4a"}
MAX_TYPED_CHARS = 2000

MEMORY_PROMPT = """\
A family in India has lost {name}. The {relationship} of the deceased is telling you, in their own words, what they
remember about {name}'s money: accounts, insurance, investments, loans, lockers, payments. They may speak Hindi,
English or a mix. They are grieving; what they say may be vague or unsure.

Write out what they said (transcript), then list one clue per account, policy, investment or loan they mention.
- type: the closest kind. A locker or anything that is not listed is other_asset.
- institution: only if they name one (a bank, insurer, fund house, post office, employer for EPF), written in
  English letters the way it would appear on a bank statement (कवच लाइफ -> Kavach Life). Else null.
- what_they_said: a short quote or close paraphrase, in the language they spoke.
- months / amount_hint: only what they actually said.
- Do not add anything they did not mention. Do not guess institutions or numbers.
- Never write down a PIN, OTP, password or card number, even if they say one: write [removed] instead.
"""

# Narration words that point to a kind of payment when the family didn't name the institution.
TYPE_WORDS = {
    "life_insurance": r"\b(?:LIFE|INS|INSURANCE|PREM|PREMIUM|POLICY|LIC)\b",
    "demat_account": r"\b(?:DIV|DIVIDEND|DP|DEMAT|BROKING|STOCKBROKING|SECURITIES)\b",
    "mutual_fund": r"\b(?:SIP|MF|MUTUAL)\b",
    "home_loan": r"\b(?:EMI|LOAN|HFL|HOUSING)\b",
    "personal_loan": r"\b(?:EMI|LOAN)\b",
    "vehicle_loan": r"\b(?:EMI|LOAN|AUTO|VEHICLE)\b",
    "other_loan": r"\b(?:EMI|LOAN)\b",
    "credit_card": r"\b(?:CREDIT CARD|CC PAYMENT)\b",
    "ppf": r"\b(?:PPF|POST OFFICE|INDIA POST)\b",
    "epf": r"\b(?:EPF|EPFO|PROVIDENT)\b",
    "fixed_deposit": r"\b(?:FD|FIXED DEPOSIT|TERM DEPOSIT)\b",
}


class MemoryReadError(RuntimeError):
    """Gemini could not read the memory. Message is safe to show the user."""


def read_memory(case: Case, *, audio: bytes | None = None, mime_type: str | None = None, text: str | None = None,
                client=None, model: str | None = None) -> tuple[MemoryReading, str, str]:
    """(reading, raw reply, model). Exactly one of audio or text."""
    if bool(audio) == bool(text):
        raise MemoryReadError("Please record a message or type what you remember.")
    if audio and mime_type not in AUDIO_MIME_TYPES:
        raise MemoryReadError(f"Unsupported recording type {mime_type}. Please try recording again.")
    client = client or get_client()
    model = model or get_settings().extraction_model  # listening is a reading task, like documents
    mime_type = GEMINI_AUDIO_NAMES.get(mime_type, mime_type)
    content = (types.Part.from_bytes(data=audio, mime_type=mime_type) if audio
               else f"WHAT THE FAMILY TYPED:\n{text[:MAX_TYPED_CHARS]}")
    try:
        response = generate(
            client, model=model, contents=[content, "List the clues in what the family remembers."],
            config=types.GenerateContentConfig(
                system_instruction=MEMORY_PROMPT.format(name=case.deceased_name, relationship=case.relationship),
                response_mime_type="application/json",
                response_json_schema=MemoryReading.model_json_schema(),
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
            ),
        )
    except errors.APIError as exc:
        raise MemoryReadError(f"Gemini request failed ({exc.code}): {exc.message}") from exc
    except GeminiUnreachable as exc:
        raise MemoryReadError(str(exc)) from exc
    if not response.text:
        raise MemoryReadError("Gemini returned an empty response for this memory.")
    return parse_memory(response.text), response.text, model


def parse_memory(raw: str) -> MemoryReading:
    try:
        return MemoryReading.model_validate_json(raw)
    except ValidationError as exc:
        raise MemoryReadError(f"Gemini's reply did not match the memory schema: {exc.errors()[:3]}") from exc


def _mentions_institution(narration: str, institution: str | None) -> bool:
    tokens = {t for t in institution_tokens(institution) if len(t) >= 4}
    words = set(re.findall(r"[a-z]+", narration.lower()))
    return bool(tokens) and len(tokens & words) / len(tokens) >= 0.5


def matching_transactions(clue, refs: list[TxnRef]) -> list[TxnRef]:
    """Transactions that back a clue. Deterministic, and deliberately strict: a wrong match would make a guess look
    like evidence. Named institution -> its name must be in the narration. Unnamed -> words typical of that kind
    of payment, and the family must have given a month or an amount to narrow it down."""
    if clue.institution and institution_tokens(clue.institution):
        found = [r for r in refs if _mentions_institution(r.description, clue.institution)]
    elif clue.type in TYPE_WORDS and (clue.months or clue.amount_hint):
        pattern = re.compile(TYPE_WORDS[clue.type], re.I)
        found = [r for r in refs if pattern.search(r.description)]
    else:
        return []
    if clue.months:
        found = [r for r in found if (d := parse_date(r.date)) and d.month in clue.months]
    if clue.amount_hint:
        found = [r for r in found if abs(r.amount - clue.amount_hint) <= max(1.0, 0.1 * clue.amount_hint)]
    unique, seen = [], set()
    for r in found:  # the same payment in a statement and a UPI screenshot counts once
        if (r.date, r.amount) not in seen:
            seen.add((r.date, r.amount))
            unique.append(r)
    return unique


def _confidence(matches: int) -> Confidence:
    return "high" if matches >= 2 else "medium" if matches == 1 else "low"


def apply_memory(case: Case, reading: MemoryReading, model: str, source: str) -> Memory:
    """Keep the clues (secrets removed) and check every memory against the transactions read so far. Mutates case."""
    clues = [c.model_copy(update={"what_they_said": said})
             for c in reading.clues if (said := mask_long_numbers(redact_secrets(c.what_they_said)).strip())]
    memory = Memory(source=source, transcript=mask_long_numbers(redact_secrets(reading.transcript)), model=model,
                    clues=clues)
    case.memories.append(memory)
    match_memories(case)
    return memory


def match_memories(case: Case) -> None:
    """Check what the family remembers against every transaction read so far. Runs when a memory arrives and again
    at each analysis: documents read since then may back it up. Merges each clue as a PROBABLE item. Mutates case."""
    refs = collect_transactions(case)
    for item in [*case.assets, *case.liabilities]:  # items only memories made: their confidence is re-earned below
        if item.origin == "family" and item.status == "probable" and not item.decided_by_user:
            item.confidence = "low"
    for memory in case.memories:
        if not memory.clues:
            continue  # memories saved before clues were kept: their results stand
        made = {r.item_id for r in memory.results if r.created}
        memory.results = [_merge_clue(case, memory, clue, refs, made) for clue in memory.clues]
    refresh_recurring(case, date.today())


def _merge_clue(case: Case, memory: Memory, clue: MemoryClue, refs: list[TxnRef], made: set[str]) -> MemoryResult:
    lang = case.language
    matches = matching_transactions(clue, refs)
    confidence = _confidence(len(matches))
    quote = Evidence(document_id=f"memory:{memory.id}", document_name=pick(lang, "What the family remembers",
                                                                            "परिवार की याद"), description=clue.what_they_said)
    found = (pick(lang, f" We found {len(matches)} matching payment{'s' if len(matches) != 1 else ''} in the "
                        "statements.", f" बैंक रिकॉर्ड में इससे मेल खाते {len(matches)} भुगतान मिले।") if matches
             else pick(lang, " We found no payment for it in the papers yet, so please ask the institution.",
                       " कागज़ों में अभी इसका कोई भुगतान नहीं मिला, इसलिए कृपया संस्था से पूछें।"))
    reason = pick(lang, "Your family remembers this.", "आपके परिवार को यह याद है।") + found  # the quote shows as evidence
    cand = Candidate(
        type=clue.type,
        institution=clue.institution,
        identifier=None,  # a number heard in a recording is never treated as an account number
        confidence=confidence,
        origin="family",
        evidence=[quote, *(r.evidence() for r in matches)],
        reason=reason,
    )
    item, created = upsert(case, cand)
    if not created and item.status == "probable" and not item.decided_by_user:
        # more evidence makes the item more likely, never less
        if RANK[confidence] > RANK[item.confidence]:
            item.confidence = confidence
        if item.origin == "family":
            item.reason = reason  # only memories back it: say what the papers show now
        else:
            also = pick(lang, FAMILY_TOO_EN, FAMILY_TOO_HI)
            if also not in (item.reason or ""):
                item.reason = f"{item.reason or ''} {also}".strip()
    return MemoryResult(item_id=item.id, type=item.type, institution=item.institution, said=clue.what_they_said,
                        matched_transactions=len(matches), created=created or item.id in made)


def summary(memory: Memory) -> tuple[str, str]:
    """Activity-log line (en, hi)."""
    new = sum(1 for r in memory.results if r.created)
    backed = len(memory.results) - new
    en = f"Listened to the family's memory: {new} new thing{'s' if new != 1 else ''} to check"
    hi = f"परिवार की याद सुनी: जाँचने के लिए {new} नई चीज़ें"
    if backed:
        en += f", {backed} that support{'s' if backed == 1 else ''} what we found"
        hi += f", {backed} जो हमारी खोज की पुष्टि करती हैं"
    return en, hi
