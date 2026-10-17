"""Build and maintain a case's asset map. Deterministic: no model calls here.

- sync_documents(): turns each extracted document into a confirmed asset/liability, merging duplicates
  (e.g. two pages of the same bank statement) and promoting a probable item once a document proves it.
- upsert(): the single merge path used by both documents and inference.
- User decisions (confirmed / rejected via the API) are never overwritten.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from app.models import Asset, Case, Confidence, Document, DocumentType, Evidence, Liability
from tools.finance import (
    check_identifier,
    identifier_digits,
    institution_tokens,
    mask_identifier,
    next_expected,
    parse_date,
    same_institution,
)

LIABILITY_TYPES = {"home_loan", "personal_loan", "vehicle_loan", "credit_card", "other_loan"}
SINGLETON_TYPES = {"epf", "ppf"}  # one per person, so any two are the same account

DOC_TYPE_TO_ITEM = {
    DocumentType.bank_statement: "savings_account",
    DocumentType.passbook: "savings_account",
    DocumentType.insurance_policy: "life_insurance",
    DocumentType.premium_receipt: "life_insurance",
    DocumentType.mutual_fund_statement: "mutual_fund",
    DocumentType.demat_statement: "demat_account",
    DocumentType.epf_passbook: "epf",
    DocumentType.upi_history: None,  # payment history, not an account of its own
}

# Which printed amount best represents each item, in priority order (regex on the amount label).
AMOUNT_LABELS = {
    "savings_account": [r"closing", r"avail|avl", r"balance"],
    "fixed_deposit": [r"maturity", r"principal|deposit amount|amount"],
    "life_insurance": [r"sum assured|cover|death benefit"],
    "mutual_fund": [r"total|portfolio"],
    "demat_account": [r"total|holding|portfolio"],
    "epf": [r"total", r"epf balance|employee.*employer"],  # never the pension (EPS) balance
    "ppf": [r"balance"],
    "home_loan": [r"outstanding"],
    "personal_loan": [r"outstanding"],
    "vehicle_loan": [r"outstanding"],
    "other_loan": [r"outstanding"],
}


@dataclass
class Candidate:
    type: str
    institution: str | None
    identifier: str | None  # full value; only used here for matching and masking, never stored
    confidence: Confidence
    origin: str
    evidence: list[Evidence] = field(default_factory=list)
    source_document_id: str | None = None
    amount: float | None = None
    amount_label: str | None = None
    amount_as_of: str | None = None
    nominee: str | None = None
    reason: str | None = None

    @property
    def is_liability(self) -> bool:
        return self.type in LIABILITY_TYPES


# ---------------------------------------------------------------------------
# Document -> candidate
# ---------------------------------------------------------------------------

def _doc_text(doc: Document) -> str:
    e = doc.extraction
    parts = [e.institution or "", e.identifier or "", *(a.label for a in e.amounts), *(d.label for d in e.dates),
             *(t.description for t in e.transactions)]
    return " ".join(parts).lower()


def _loan_type(text: str) -> str:
    if re.search(r"home|housing|griha", text):
        return "home_loan"
    if re.search(r"vehicle|car|auto|two.?wheeler", text):
        return "vehicle_loan"
    if re.search(r"credit card", text):
        return "credit_card"
    if re.search(r"personal", text):
        return "personal_loan"
    return "other_loan"


def item_type_for(doc: Document) -> str | None:
    e = doc.extraction
    text = _doc_text(doc)
    if e.document_type == DocumentType.loan_sms:
        return _loan_type(text)
    if e.document_type in DOC_TYPE_TO_ITEM:
        return DOC_TYPE_TO_ITEM[e.document_type]
    # document_type == other: classify by what is printed
    if re.search(r"fixed deposit|term deposit|\bfd\b|maturity", text):
        return "fixed_deposit"
    if re.search(r"\bppf\b|public provident", text):
        return "ppf"
    if re.search(r"\bloan\b|\bemi\b", text):
        return _loan_type(text)
    if re.search(r"sum assured|insurance|policy", text):
        return "life_insurance"
    return "other_asset"


def as_of_date(doc: Document, today: date | None = None) -> str | None:
    """Latest date on the document that isn't in the future (maturity / next-due dates are not "as of")."""
    e = doc.extraction
    limit = (today or date.today()).isoformat()
    dates = [d for d in [*(x.date for x in e.dates), *(t.date for t in e.transactions)] if d and d <= limit]
    return max(dates) if dates else None


def pick_amount(item_type: str, doc: Document) -> tuple[float | None, str | None]:
    amounts = doc.extraction.amounts
    for pattern in AMOUNT_LABELS.get(item_type, []):
        matches = [a for a in amounts if re.search(pattern, a.label, re.I)]
        if matches:
            return matches[-1].value, matches[-1].label  # last = usually the closing / total figure
    if item_type == "mutual_fund":  # no total printed: add up per-scheme market values
        values = [a for a in amounts if re.search(r"market value|current value|valuation", a.label, re.I)]
        if values:
            return round(sum(a.value for a in values), 2), "sum of scheme values"
    if item_type == "epf":  # no combined figure printed: employee + employer closing balances
        shares = [a for a in amounts if re.search(r"employee|employer", a.label, re.I)
                  and re.search(r"closing|balance", a.label, re.I) and not re.search(r"pension|eps", a.label, re.I)]
        if len(shares) == 2:
            return round(sum(a.value for a in shares), 2), "employee + employer share"
    return None, None


def candidate_from_document(doc: Document) -> Candidate | None:
    if doc.status != "extracted" or doc.extraction is None:
        return None
    item_type = item_type_for(doc)
    if item_type is None:
        return None
    e = doc.extraction
    amount, label = pick_amount(item_type, doc)
    as_of = as_of_date(doc)
    summary = f"{e.document_type.value.replace('_', ' ')} from {e.institution or 'unknown institution'}"
    return Candidate(
        type=item_type,
        institution=e.institution,
        identifier=e.identifier,
        confidence=e.confidence,
        origin="document",
        source_document_id=doc.id,
        evidence=[Evidence(document_id=doc.id, document_name=doc.filename, date=as_of, description=summary,
                           amount=amount)],
        amount=amount,
        amount_label=label,
        amount_as_of=as_of,
        nominee=e.nominee,
    )


# ---------------------------------------------------------------------------
# Matching and merging
# ---------------------------------------------------------------------------

def _known_digits(case: Case, item: Asset | Liability) -> set[str]:
    """Every identifier we can compare against: full numbers from source documents + the masked last 4."""
    digits = set()
    for doc_id in item.source_document_ids:
        doc = case.get_document(doc_id)
        if doc and doc.extraction:
            digits.add(identifier_digits(doc.extraction.identifier))
    digits.add(identifier_digits(item.identifier_masked))
    return {d for d in digits if len(d) >= 4}


def _ids_match(candidate_digits: str, known: set[str]) -> str | None:
    """'full' when one number contains the other (5+ digits), 'last4' when only the last 4 digits agree,
    'differ' when both sides have numbers that don't agree, None when they can't be compared."""
    if len(candidate_digits) < 4 or not known:
        return None
    result = "differ"
    for d in known:
        shorter, longer = sorted([d, candidate_digits], key=len)
        if len(shorter) >= 5 and shorter in longer:
            return "full"
        if d[-4:] == candidate_digits[-4:]:
            result = "last4"
    return result


def _institutions_compatible(a: str | None, b: str | None) -> bool:
    """Same institution, or one side doesn't name one we can compare."""
    return same_institution(a, b) or not institution_tokens(a) or not institution_tokens(b)


def find_match(case: Case, cand: Candidate) -> Asset | Liability | None:
    items = case.liabilities if cand.is_liability else case.assets
    cand_digits = identifier_digits(cand.identifier)
    for item in items:
        if item.type != cand.type:
            continue
        if cand.type in SINGLETON_TYPES:
            return item
        ids = _ids_match(cand_digits, _known_digits(case, item))
        if ids == "full":
            return item
        # 4 matching digits are common across banks: only trust them when the institution doesn't disagree
        if ids == "last4" and _institutions_compatible(item.institution, cand.institution):
            return item
        if ids is None and same_institution(item.institution, cand.institution):
            return item
    return None


def _add_evidence(item: Asset | Liability, evidence: list[Evidence]) -> None:
    seen = {e.key() for e in item.evidence}
    for ev in evidence:
        if ev.key() not in seen:
            item.evidence.append(ev)
            seen.add(ev.key())


def upsert(case: Case, cand: Candidate) -> tuple[Asset | Liability, bool]:
    """Merge the candidate into a matching item or add it. Returns (item, created)."""
    existing = find_match(case, cand)
    if existing is None:
        cls = Liability if cand.is_liability else Asset
        item = cls(
            type=cand.type,
            status="confirmed" if cand.origin == "document" else "probable",
            institution=cand.institution,
            identifier_masked=mask_identifier(cand.identifier),
            identifier_check=check_identifier(cand.type, cand.identifier) if cand.origin == "document" else "unchecked",
            amount=cand.amount,
            amount_label=cand.amount_label,
            amount_as_of=cand.amount_as_of,
            nominee=cand.nominee,
            source_document_ids=[cand.source_document_id] if cand.source_document_id else [],
            evidence=list(cand.evidence),
            confidence=cand.confidence,
            reason=cand.reason,
            origin=cand.origin,
        )
        (case.liabilities if cand.is_liability else case.assets).append(item)
        return item, True

    item = existing
    _add_evidence(item, cand.evidence)
    if cand.origin == "document":
        if cand.source_document_id and cand.source_document_id not in item.source_document_ids:
            item.source_document_ids.append(cand.source_document_id)
        if item.status == "probable" and not item.decided_by_user:
            item.status, item.origin, item.confidence = "confirmed", "document", cand.confidence  # proven by a document
        newer = (cand.amount_as_of or "") >= (item.amount_as_of or "")
        if cand.amount is not None and (item.amount is None or newer):
            item.amount, item.amount_label, item.amount_as_of = cand.amount, cand.amount_label, cand.amount_as_of
        item.nominee = item.nominee or cand.nominee
        if item.identifier_masked is None and cand.identifier:
            item.identifier_masked = mask_identifier(cand.identifier)
            item.identifier_check = check_identifier(cand.type, cand.identifier)
        if item.origin == "document" and cand.institution and not item.institution:
            item.institution = cand.institution
    else:
        if item.identifier_masked is None and cand.identifier:
            item.identifier_masked = mask_identifier(cand.identifier)
    return item, False


def refresh_recurring(case: Case, today: date) -> None:
    """Set next_expected_debit for items backed by a repeating debit (premiums, EMIs, SIPs)."""
    for item in [*case.assets, *case.liabilities]:
        dates = [parse_date(e.date) for e in item.evidence if e.direction == "debit"]
        nxt = next_expected([d for d in dates if d], today)
        item.next_expected_debit = nxt.isoformat() if nxt else None


def _names_item(narration: str, item, digits: set[str]) -> bool:
    words = set(re.findall(r"[a-z]+", narration.lower()))
    tokens = institution_tokens(item.institution)
    if tokens and len(tokens & words) / len(tokens) >= 0.5 and any(len(t) >= 4 for t in tokens & words):
        return True
    narration_digits = re.sub(r"\D", " ", narration).split()
    return any(len(d) >= 6 and d in narration_digits for d in digits)


def link_transactions(case: Case) -> None:
    """Attach transactions from OTHER documents that name a documented item (e.g. EMI debits in the bank
    statement for a loan known from an SMS). This is what lets the plan see the next auto-debit date."""
    for item in [*case.assets, *case.liabilities]:
        if item.origin != "document":
            continue
        digits = {d for d in _known_digits(case, item) if len(d) >= 6}
        found = []
        for doc in case.documents:
            if doc.id in item.source_document_ids or doc.status != "extracted" or not doc.extraction:
                continue
            for t in doc.extraction.transactions:
                if _names_item(t.description, item, digits):
                    found.append(Evidence(document_id=doc.id, document_name=doc.filename, date=t.date,
                                          description=t.description, amount=t.amount, direction=t.direction))
        _add_evidence(item, found)


def sync_documents(case: Case, today: date | None = None) -> None:
    """Fold every extracted document into the asset map. Safe to run repeatedly."""
    for doc in case.documents:
        cand = candidate_from_document(doc)
        if cand:
            upsert(case, cand)
    link_transactions(case)
    refresh_recurring(case, today or date.today())


def forget_document(case: Case, document_id: str, today: date | None = None) -> list[str]:
    """Remove a document from the case and the asset map; returns the ids of items that went with it.

    Its evidence goes from every item. An item only that document proved is removed, and so is an inferred item
    with no transactions left to cite (a probable item without evidence would be a guess). Items the family
    confirmed or rejected themselves stay. Run analysis again to look for hidden assets afresh.
    """
    case.documents = [d for d in case.documents if d.id != document_id]
    removed = []
    for items in (case.assets, case.liabilities):
        for item in list(items):
            item.evidence = [e for e in item.evidence if e.document_id != document_id]
            if document_id in item.source_document_ids:
                item.source_document_ids.remove(document_id)
                # the balance may have come from the removed document; sync_documents re-reads the remaining ones
                item.amount = item.amount_label = item.amount_as_of = None
            if item.decided_by_user:
                continue
            unproven = item.origin == "document" and not item.source_document_ids
            if unproven or (item.origin == "inference" and not item.evidence):
                items.remove(item)
                removed.append(item.id)
    sync_documents(case, today)
    return removed


def asset_map_view(case: Case) -> dict:
    from tools.finance import totals

    def group(items):
        return {s: [i.model_dump(mode="json") for i in items if i.status == s] for s in ("confirmed", "probable", "rejected")}

    return {
        "case_id": case.id,
        "assets": group(case.assets),
        "liabilities": group(case.liabilities),
        "totals": totals(case),
        "last_inference": case.inference_runs[-1].model_dump(mode="json") if case.inference_runs else None,
    }
