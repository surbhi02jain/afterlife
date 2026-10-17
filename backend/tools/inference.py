"""Hidden-asset inference: Gemini proposes, deterministic code verifies and merges.

Gemini sees every extracted transaction (with an id like T7) plus the items already documented, and proposes
assets/liabilities that probably exist. Code then enforces the guardrails:
  - every proposal must cite transaction ids that really exist, or it is discarded (and logged);
  - a proposal backed by a single transaction can't be "high" confidence;
  - proposals are added as status=probable only, through the same dedup path as documents.
"""

import re
from dataclasses import dataclass
from datetime import date

from google.genai import errors, types
from pydantic import ValidationError

from app.config import get_settings
from app.gemini import GeminiUnreachable, generate, get_client
from app.models import Case, Evidence, InferenceResult, InferenceRun
from tools.asset_map import Candidate, refresh_recurring, upsert

INFERENCE_PROMPT = """\
You help a grieving family in India find financial assets and loans of a person who has died.
You are given every transaction we could read from their uploaded documents, and the list of items
that are ALREADY documented. Propose assets or liabilities that PROBABLY exist but have no document yet.

Clues to look for:
- A recurring premium debit to an insurer (NACH/ECS/auto-debit, "PREM", "LIFE INS") -> a life insurance policy.
- Dividend credits from companies ("DIV", "DIVIDEND"), depository/DP charges, or payments to a stockbroker
  -> a demat / trading account (shares are held in a demat account).
- A recurring EMI or loan debit -> a loan (liability).
- Credits from EPFO, or regular salary credits from an employer -> an EPF account.
- A SIP or mutual fund debit -> a mutual fund folio.
- PPF or post-office deposits -> a PPF / small-savings account.

Rules:
- Only propose something when specific transactions point to it. Cite their ids in evidence_transaction_ids
  (cite every relevant one, e.g. all monthly premium debits). Never invent ids.
- Do NOT propose anything already in ALREADY DOCUMENTED (same institution and type). Ignore it even if
  its transactions also appear.
- Ignore everyday spending: groceries, utilities, medical, ATM cash, transfers to/from family, salary itself
  (except as a clue for EPF), savings interest.
- One proposal per institution and type. Use the institution name as written in the narration.
- identifier_hint: only a policy, folio, loan or account number. NOT a mandate reference (UMRN), UPI/NEFT
  reference, cheque number or DP charge reference. Use null if unsure.
- confidence: high = several consistent transactions that clearly name the institution; medium = one clear
  transaction or a less direct clue; low = a weak hint.
- reason: one or two short, warm, plain sentences for a family member who is not a finance expert. Say
  "probably" or "looks like"; never state it as a fact. Write it in {language}.
- If nothing is hidden, return an empty list.
"""


# Transactions that by themselves prove part of the case for an inferred type; added to the model's citations.
SUPPORTING_EVIDENCE = {"demat_account": re.compile(r"\bDIV(IDEND)?\b", re.I)}


class InferenceError(RuntimeError):
    """Inference could not produce a valid result. Message is safe to show the user."""


@dataclass
class TxnRef:
    id: str
    document_id: str
    document_name: str
    date: str | None
    description: str
    amount: float
    direction: str

    def evidence(self) -> Evidence:
        return Evidence(document_id=self.document_id, document_name=self.document_name, date=self.date,
                        description=self.description, amount=self.amount, direction=self.direction)


def collect_transactions(case: Case) -> list[TxnRef]:
    refs = []
    for doc in case.documents:
        if doc.status != "extracted" or not doc.extraction:
            continue
        for t in doc.extraction.transactions:
            refs.append(TxnRef(f"T{len(refs) + 1}", doc.id, doc.filename, t.date, t.description, t.amount,
                               t.direction))
    return refs


def build_prompt(case: Case, refs: list[TxnRef]) -> str:
    known = [f"- {i.type} | {i.institution or 'unknown'} | {i.identifier_masked or 'no number'} | {i.status}"
             for i in [*case.assets, *case.liabilities] if i.status != "rejected"]
    docs = {d.id: d for d in case.documents}
    lines = []
    for r in refs:
        source = docs[r.document_id].extraction
        lines.append(f"{r.id} | {r.date or 'no date'} | {r.direction} | {r.amount:.2f} | {r.description} | "
                     f"in {source.document_type.value} from {source.institution or 'unknown'}")
    return (f"Date of death: {case.date_of_death.isoformat()}\n\n"
            "ALREADY DOCUMENTED:\n" + ("\n".join(known) or "- nothing yet") +
            "\n\nTRANSACTIONS:\n" + "\n".join(lines))


def propose(case: Case, refs: list[TxnRef], *, client=None, model: str | None = None) -> tuple[InferenceResult, str]:
    client = client or get_client()
    model = model or get_settings().reasoning_model
    language = "Hindi (Devanagari script)" if case.language == "hi" else "English"
    try:
        response = generate(
            client,
            model=model,
            contents=build_prompt(case, refs),
            config=types.GenerateContentConfig(
                system_instruction=INFERENCE_PROMPT.format(language=language),
                response_mime_type="application/json",
                response_json_schema=InferenceResult.model_json_schema(),
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MEDIUM),
            ),
        )
    except errors.APIError as exc:
        raise InferenceError(f"Gemini request failed ({exc.code}): {exc.message}") from exc
    except GeminiUnreachable as exc:
        raise InferenceError(str(exc)) from exc
    if not response.text:
        raise InferenceError("Gemini returned an empty response for inference.")
    try:
        return InferenceResult.model_validate_json(response.text), model
    except ValidationError as exc:
        raise InferenceError(f"Gemini's inference reply did not match the schema: {exc.errors()[:3]}") from exc


def _real_identifier(hint: str | None, evidence: list[TxnRef]) -> str | None:
    """Drop hints that are really payment references (e.g. 'UMRN SNB70002315'), not account numbers."""
    if not hint:
        return None
    for r in evidence:
        if re.search(r"(UMRN|UTR|REF|RRN)\W*" + re.escape(hint), r.description, re.I):
            return None
    return hint


def apply_proposals(case: Case, result: InferenceResult, refs: list[TxnRef], model: str,
                    today: date | None = None) -> InferenceRun:
    """Verify each proposal against real transactions and merge it in as probable. Mutates case."""
    by_id = {r.id: r for r in refs}
    run = InferenceRun(model=model, proposed=len(result.items))
    for p in result.items:
        label = f"{p.type} at {p.institution}"
        cited = list(dict.fromkeys(p.evidence_transaction_ids))  # dedupe, keep order
        valid = [by_id[i] for i in cited if i in by_id]
        if valid and p.type in SUPPORTING_EVIDENCE:  # deterministic: e.g. every dividend credit backs a demat account
            pattern = SUPPORTING_EVIDENCE[p.type]
            valid += [r for r in refs if r not in valid and r.direction == "credit" and pattern.search(r.description)]
        if not valid:
            run.discarded.append(f"{label}: no valid transaction evidence (cited {cited})")
            continue
        confidence = p.confidence
        if confidence == "high" and len({(r.date, r.description) for r in valid}) < 2:
            confidence = "medium"  # one transaction is a clue, not a pattern
        cand = Candidate(
            type=p.type,  # type decides asset vs liability, whatever `kind` said
            institution=p.institution,
            identifier=_real_identifier(p.identifier_hint, valid),
            confidence=confidence,
            origin="inference",
            evidence=[r.evidence() for r in valid],
            reason=p.reason,
        )
        item, created = upsert(case, cand)
        (run.added if created else run.merged).append(item.id)
    refresh_recurring(case, today or date.today())
    case.inference_runs.append(run)
    return run

