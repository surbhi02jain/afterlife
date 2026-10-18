"""All Pydantic models: the API contract and the schemas we hand to Gemini."""

import re
import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

Confidence = Literal["high", "medium", "low"]


def new_id() -> str:
    return uuid.uuid4().hex


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _check_iso_date(value: str | None) -> str | None:
    if value is None:
        return None
    if not ISO_DATE.match(value):
        raise ValueError(f"date must be YYYY-MM-DD, got {value!r}")
    date.fromisoformat(value)  # rejects impossible dates like 2026-02-30
    return value


# ---------------------------------------------------------------------------
# Extraction schema (sent to Gemini as response_json_schema)
# ---------------------------------------------------------------------------

class DocumentType(str, Enum):
    bank_statement = "bank_statement"
    passbook = "passbook"
    insurance_policy = "insurance_policy"
    premium_receipt = "premium_receipt"
    mutual_fund_statement = "mutual_fund_statement"
    demat_statement = "demat_statement"
    epf_passbook = "epf_passbook"
    loan_sms = "loan_sms"
    upi_history = "upi_history"
    other = "other"


class Transaction(BaseModel):
    date: str | None = Field(description="Transaction date as YYYY-MM-DD, or null if not shown.")
    description: str = Field(description="Narration exactly as printed, e.g. 'NACH DR KAVACH LIFE PREM'.")
    amount: float = Field(description="Amount in rupees as a positive number, no commas or currency symbol.")
    direction: Literal["credit", "debit"] = Field(
        description="credit = money came into this account (Cr/deposit/received); "
        "debit = money went out (Dr/withdrawal/paid)."
    )

    @field_validator("date")
    @classmethod
    def check_date(cls, value):
        return _check_iso_date(value)


class Amount(BaseModel):
    label: str = Field(description="What the amount is, e.g. 'closing balance', 'sum assured', 'premium', 'EMI'.")
    value: float = Field(description="Amount in rupees as a plain number.")
    currency: str = Field(default="INR", description="ISO currency code, usually INR.")


class LabeledDate(BaseModel):
    label: str = Field(description="What the date is, e.g. 'statement from', 'next premium due', 'maturity'.")
    date: str = Field(description="YYYY-MM-DD")

    @field_validator("date")
    @classmethod
    def check_date(cls, value):
        return _check_iso_date(value)


class ExtractedDocument(BaseModel):
    institution: str | None = Field(description="Bank/insurer/fund/employer name as printed, or null.")
    document_type: DocumentType
    identifier: str | None = Field(
        description="Main account, policy, folio, loan, UAN or member number exactly as printed "
        "(keep any X-masking as shown), or null."
    )
    holder_name: str | None = Field(description="Name of the account/policy holder, or null.")
    nominee: str | None = Field(description="Nominee name if printed, else null. Never guess.")
    amounts: list[Amount] = Field(description="Key amounts on the document (balances, sum assured, premium, EMI).")
    dates: list[LabeledDate] = Field(description="Key dates on the document other than transaction dates.")
    transactions: list[Transaction] = Field(
        description="Every transaction row visible, in the order shown. Empty list if none."
    )
    language_detected: str = Field(description="ISO 639-1 code of the document's main language, e.g. 'en', 'hi'.")
    confidence: Confidence = Field(
        description="high = clear and complete; medium = some fields unclear; low = hard to read or unsure."
    )


# ---------------------------------------------------------------------------
# Cases and documents
# ---------------------------------------------------------------------------

def _not_in_future(value: date | None) -> date | None:
    if value is not None and value > date.today():
        raise ValueError("date of death cannot be in the future")
    return value


class CaseFields(BaseModel):
    deceased_name: str = Field(min_length=1, max_length=120)
    date_of_death: date
    relationship: str = Field(min_length=1, max_length=60, description="How the user is related to the deceased.")
    language: Literal["en", "hi"] = "en"


class CaseCreate(CaseFields):
    """Input only: the future-date check must not run when a stored Case is loaded."""

    @field_validator("date_of_death")
    @classmethod
    def not_in_future(cls, value: date) -> date:
        return _not_in_future(value)


class CaseUpdate(BaseModel):
    deceased_name: str | None = Field(default=None, min_length=1, max_length=120)
    date_of_death: date | None = None
    relationship: str | None = Field(default=None, min_length=1, max_length=60)
    language: Literal["en", "hi"] | None = None

    @field_validator("date_of_death")
    @classmethod
    def not_in_future(cls, value: date | None) -> date | None:
        return _not_in_future(value)


DocumentStatus = Literal["locked", "uploaded", "extracting", "extracted", "failed"]  # locked: PDF needs its password


class Document(BaseModel):
    id: str = Field(default_factory=new_id)
    filename: str
    content_type: str
    size_bytes: int
    storage_key: str
    uploaded_at: datetime = Field(default_factory=utc_now)
    status: DocumentStatus = "uploaded"
    error: str | None = None
    extraction: ExtractedDocument | None = None
    extracted_with_model: str | None = None


# ---------------------------------------------------------------------------
# Asset map
# ---------------------------------------------------------------------------

AssetType = Literal[
    "savings_account", "fixed_deposit", "life_insurance", "mutual_fund", "demat_account", "epf", "ppf", "other_asset"
]
LiabilityType = Literal["home_loan", "personal_loan", "vehicle_loan", "credit_card", "other_loan"]
ItemStatus = Literal["confirmed", "probable", "rejected"]
IdentifierCheck = Literal["valid", "invalid", "unchecked"]


# Aadhaar "1234 5678 9012", card "4111-1111-1111-1234". Dates (2026-08-05) don't fit the 4-4-4 shape.
_GROUPED_NUMBER = re.compile(r"(?<![\d-])\d{4}(?:[ -]\d{4}){2,3}(?![\d-])")
# A run of 6+ digits, optionally glued to a letter prefix of any length ("POLICYNO784512093").
_LONG_NUMBER = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]*)(\d{2,})(\d{4})(?!\d)")


def mask_long_numbers(text: str) -> str:
    """'POL 784512093' -> 'POL XXXX2093', 'HL0098817782' -> 'HLXXXX7782', '1234 5678 9012' -> 'XXXX9012'.
    Only runs of 6+ digits (or 4-digit groups) are masked."""
    text = _GROUPED_NUMBER.sub(lambda m: "XXXX" + m.group(0)[-4:], text)
    return _LONG_NUMBER.sub(lambda m: f"{m.group(1)}XXXX{m.group(3)}", text)


class Evidence(BaseModel):
    document_id: str
    document_name: str
    date: str | None = None
    description: str = Field(description="Narration with account/policy numbers masked to the last 4 digits.")
    amount: float | None = None
    direction: Literal["credit", "debit"] | None = None

    @field_validator("description")
    @classmethod
    def mask_numbers(cls, value: str) -> str:
        return mask_long_numbers(value)

    def key(self) -> tuple:
        return (self.document_id, self.date, self.description, self.amount)


class MapItem(BaseModel):
    """One asset or liability. `probable` items are inferred and must never be shown as facts."""

    id: str = Field(default_factory=new_id)
    status: ItemStatus
    institution: str | None = None
    identifier_masked: str | None = Field(default=None, description="Last 4 characters only, e.g. XXXX1931.")
    identifier_check: IdentifierCheck = "unchecked"
    amount: float | None = None
    amount_label: str | None = None
    amount_as_of: str | None = None
    nominee: str | None = None
    source_document_ids: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: Confidence
    reason: str | None = Field(default=None, description="Plain-language explanation, mainly for probable items.")
    origin: Literal["document", "inference", "family"]
    decided_by_user: bool = False
    next_expected_debit: str | None = Field(default=None, description="Next date a recurring debit is expected.")


class Asset(MapItem):
    type: AssetType


class Liability(MapItem):
    type: LiabilityType


class InferenceRun(BaseModel):
    at: datetime = Field(default_factory=utc_now)
    model: str
    proposed: int
    added: list[str] = Field(default_factory=list, description="ids of new probable items")
    merged: list[str] = Field(default_factory=list, description="ids of existing items that gained evidence")
    discarded: list[str] = Field(default_factory=list, description="why a proposal was dropped")


# --- Gemini schema for the inference tool ----------------------------------

class InferredItem(BaseModel):
    kind: Literal["asset", "liability"]
    type: Literal[
        "savings_account", "fixed_deposit", "life_insurance", "mutual_fund", "demat_account", "epf", "ppf",
        "other_asset", "home_loan", "personal_loan", "vehicle_loan", "credit_card", "other_loan",
    ]
    institution: str = Field(description="Institution name as it appears in the transactions.")
    identifier_hint: str | None = Field(
        description="Any policy/folio/loan/account number visible in the narrations, else null."
    )
    reason: str = Field(description="One or two warm, plain sentences explaining why this probably exists.")
    evidence_transaction_ids: list[str] = Field(description="IDs (like T7) of the transactions that point to it.")
    confidence: Confidence


class InferenceResult(BaseModel):
    items: list[InferredItem]


# ---------------------------------------------------------------------------
# Family memories (voice or typed): Gemini listens, code matches the clues to transactions
# ---------------------------------------------------------------------------

ItemTypeName = Literal[
    "savings_account", "fixed_deposit", "life_insurance", "mutual_fund", "demat_account", "epf", "ppf",
    "other_asset", "home_loan", "personal_loan", "vehicle_loan", "credit_card", "other_loan",
]


class MemoryClue(BaseModel):
    type: ItemTypeName = Field(description="The kind of account, policy, investment or loan the family describes.")
    institution: str | None = Field(description="The bank/insurer/fund/lender named, as said, or null if not named.")
    what_they_said: str = Field(description="A short quote or close paraphrase of what the family said about it, in "
                                            "the language they spoke.")
    months: list[int] = Field(description="Months (1-12) they mention for payments, e.g. 'every March' -> [3]. Empty "
                                          "if none or 'every month'.")
    amount_hint: float | None = Field(description="An amount in rupees they mention for it, or null.")


class MemoryReading(BaseModel):
    transcript: str = Field(description="What was said, written out in the language spoken. Replace any PIN, OTP, "
                                        "password or card number with [removed].")
    language_detected: str = Field(description="ISO 639-1 code of the main language spoken, e.g. 'hi', 'en'.")
    clues: list[MemoryClue] = Field(description="One per account, policy, investment or loan they mention. Empty if "
                                                "they mention none.")


class MemoryResult(BaseModel):
    item_id: str
    type: str
    institution: str | None = None
    said: str
    matched_transactions: int = 0
    created: bool = Field(description="True when this memory added a new probable item; False when it backed one "
                                      "we already had.")


class Memory(BaseModel):
    id: str = Field(default_factory=new_id)
    at: datetime = Field(default_factory=utc_now)
    source: Literal["voice", "typed"]
    transcript: str = Field(description="Numbers masked to the last 4; secrets removed.")
    model: str
    clues: list[MemoryClue] = Field(default_factory=list, description="Kept (secrets removed) so each analysis can "
                                                                      "check them again against every document read.")
    results: list[MemoryResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Name check across documents: Gemini compares names, code verifies every quote
# ---------------------------------------------------------------------------

class NameMention(BaseModel):
    ref: str = Field(description="Where the name appears: a document ref like D3, or FAMILY for the name the family "
                                 "typed, or CLAIMANT for the family member who will sign.")
    role: Literal["holder", "nominee", "deceased", "claimant"] = Field(
        description="holder/nominee for a document; deceased for FAMILY; claimant for CLAIMANT.")
    name: str = Field(description="The name exactly as given in the list, character for character.")


class NameFinding(BaseModel):
    kind: Literal["deceased_name_differs", "nominee_name_differs", "not_the_deceased"]
    mentions: list[NameMention] = Field(description="Every mention involved, including the one that differs.")
    explanation: str = Field(description="One or two warm, plain sentences on what differs and why an institution "
                                         "may ask about it. No legal advice.")


class NameCheckResult(BaseModel):
    findings: list[NameFinding]


class NameIssue(BaseModel):
    kind: Literal["deceased_name_differs", "nominee_name_differs", "not_the_deceased"]
    names: list[dict] = Field(description="[{name, where: [document filenames]}], one per way it is written.")
    explanation: str


class NameCheck(BaseModel):
    at: datetime = Field(default_factory=utc_now)
    model: str
    compared: int = Field(description="How many names were compared.")
    issues: list[NameIssue] = Field(default_factory=list)
    discarded: list[str] = Field(default_factory=list, description="Findings dropped because a quote didn't check out.")


# ---------------------------------------------------------------------------
# Replies from institutions: Gemini reads the letter, code updates the plan
# ---------------------------------------------------------------------------

ReplyOutcome = Literal["asks_for_documents", "no_record_found", "claim_settled", "other"]


class RequirementDraft(BaseModel):
    document: str = Field(description="One thing they ask for, in plain words, e.g. 'Original policy bond'.")
    detail: str | None = Field(description="Any detail they give about it (copies, attested, which form), or null.")


class ReplyReading(BaseModel):
    institution: str | None = Field(description="Who wrote the letter or message, as printed.")
    letter_date: str | None = Field(description="Date of the letter as YYYY-MM-DD, or null.")
    reference_number: str | None = Field(description="Their claim/reference number as printed, or null.")
    outcome: ReplyOutcome = Field(description="asks_for_documents = they list documents or steps for the family; "
                                              "no_record_found = they found nothing in the deceased's name; "
                                              "claim_settled = they paid or closed it; other.")
    confirms_account: bool = Field(description="True if the letter states that an account, policy, investment or loan "
                                               "of the deceased exists or was in force; else false.")
    item_type: ItemTypeName | None = Field(description="The kind of account/policy the letter is about, or null.")
    identifier: str | None = Field(description="The account/policy/loan number they state, as printed, or null.")
    nominee: str | None = Field(description="The nominee they state, or null. Never guess.")
    amount: float | None = Field(description="The main amount they state (sum assured, balance, settled amount), or "
                                             "null.")
    requirements: list[RequirementDraft] = Field(description="Everything they ask the family to send or do.")
    respond_within_days: int | None = Field(description="If they give a time limit in days ('within 30 days'), that "
                                                        "number; else null.")
    red_flags: list[str] = Field(description="Anything a genuine institution would not ask: a fee or payment to "
                                             "release the money, an OTP/PIN/password, remote-access apps, a personal "
                                             "UPI id or bank account to pay into, threats or extreme urgency. Empty "
                                             "if none.")
    summary: str = Field(description="Two or three warm, plain sentences: what they said and what they want next.")


class Requirement(BaseModel):
    id: str = Field(default_factory=new_id)
    document: str
    detail: str | None = None
    done: bool = False


class InstitutionReply(BaseModel):
    id: str = Field(default_factory=new_id)
    task_id: str
    institution: str
    filename: str
    received_at: datetime = Field(default_factory=utc_now)
    letter_date: str | None = None
    reference_masked: str | None = None
    outcome: ReplyOutcome
    summary: str
    requirements: list[Requirement] = Field(default_factory=list)
    respond_by: str | None = Field(default=None, description="Computed in code: letter date + days they gave.")
    red_flags: list[str] = Field(default_factory=list, description="Plain-language warnings, in the case language.")
    red_flag_quotes: list[str] = Field(default_factory=list, description="Their own words that raised the flags.")
    confirmed_item_id: str | None = Field(default=None, description="The probable item this letter confirmed.")
    model: str


# ---------------------------------------------------------------------------
# Agent activity, follow-up questions, action plan, letters
# ---------------------------------------------------------------------------

class ActivityEntry(BaseModel):
    at: datetime = Field(default_factory=utc_now)
    run_id: str | None = None
    tool: str
    ok: bool = True
    summary_en: str
    summary_hi: str
    detail: dict = Field(default_factory=dict, description="Compact args/result. Never full identifiers.")


QuestionTarget = Literal["confirm_item", "item_nominee", "claimant_name", "claimant_address", "death_certificate"]


class Question(BaseModel):
    id: str = Field(default_factory=new_id)
    text: str
    why: str | None = None
    target: QuestionTarget
    item_id: str | None = None
    options: list[str] = Field(default_factory=list, description="Choices to show; empty = free text.")
    status: Literal["open", "answered"] = "open"
    answer: str | None = None
    asked_at: datetime = Field(default_factory=utc_now)
    answered_at: datetime | None = None


class CaseFacts(BaseModel):
    claimant_name: str | None = None
    claimant_address: str | None = None
    death_certificate: Literal["yes", "no", "applied"] | None = None


class PlanItemRef(BaseModel):
    item_id: str
    kind: Literal["asset", "liability"]
    type: str
    status: ItemStatus
    identifier_masked: str | None = None
    amount: float | None = None


BoardStatus = Literal["todo", "in_progress", "done"]


class PlanTask(BaseModel):
    id: str = Field(description="Stable across rebuilds so the family board keeps its status.")
    order: int
    institution: str
    items: list[PlanItemRef]
    needs_confirmation: bool = Field(description="True when every item here is still probable.")
    nominee: str | None = None
    first_step: str
    steps: list[str]
    documents_required: list[str]
    typical_timeline: str | None = None
    time_sensitive: list[str] = Field(default_factory=list)
    why_this_order: str
    source_names: list[str] = Field(default_factory=list)
    verified: bool = False
    board_status: BoardStatus = "todo"


class ActionPlan(BaseModel):
    generated_at: datetime = Field(default_factory=utc_now)
    language: Literal["en", "hi"]
    days_since_death: int
    general_steps: list[str]
    tasks: list[PlanTask]
    disclaimer: str


class Letter(BaseModel):
    id: str = Field(default_factory=new_id)
    item_id: str
    institution: str
    kind: Literal["claim_intimation", "existence_enquiry", "reply_cover"]
    reply_id: str | None = Field(default=None, description="For reply_cover: the institution's reply it answers.")
    title: str
    body: str
    language: Literal["en", "hi"]
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    edited: bool = False


class Case(CaseFields):
    id: str = Field(default_factory=new_id)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    is_demo: bool = False
    owner_key_hash: str | None = None  # sha256 of the private key held by the creating browser; never sent out
    documents: list[Document] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    liabilities: list[Liability] = Field(default_factory=list)
    inference_runs: list[InferenceRun] = Field(default_factory=list)
    facts: CaseFacts = Field(default_factory=CaseFacts)
    questions: list[Question] = Field(default_factory=list)
    plan: ActionPlan | None = None
    letters: list[Letter] = Field(default_factory=list)
    memories: list[Memory] = Field(default_factory=list)
    name_check: NameCheck | None = None
    replies: list[InstitutionReply] = Field(default_factory=list)
    activity: list[ActivityEntry] = Field(default_factory=list)

    def get_question(self, question_id: str) -> Question | None:
        return next((q for q in self.questions if q.id == question_id), None)

    def get_letter(self, letter_id: str) -> Letter | None:
        return next((l for l in self.letters if l.id == letter_id), None)

    def get_document(self, document_id: str) -> Document | None:
        return next((d for d in self.documents if d.id == document_id), None)

    def get_item(self, item_id: str) -> Asset | Liability | None:
        return next((i for i in [*self.assets, *self.liabilities] if i.id == item_id), None)

    def get_reply(self, reply_id: str) -> "InstitutionReply | None":
        return next((r for r in self.replies if r.id == reply_id), None)

    def item_letter(self, item_id: str) -> Letter | None:
        """The claim or enquiry letter for an item (not a cover letter answering a reply)."""
        return next((l for l in self.letters if l.item_id == item_id and l.reply_id is None), None)
