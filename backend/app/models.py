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

class CaseCreate(BaseModel):
    deceased_name: str = Field(min_length=1, max_length=120)
    date_of_death: date
    relationship: str = Field(min_length=1, max_length=60, description="How the user is related to the deceased.")
    language: Literal["en", "hi"] = "en"

    @field_validator("date_of_death")
    @classmethod
    def not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("date of death cannot be in the future")
        return value


class CaseUpdate(BaseModel):
    deceased_name: str | None = Field(default=None, min_length=1, max_length=120)
    date_of_death: date | None = None
    relationship: str | None = Field(default=None, min_length=1, max_length=60)
    language: Literal["en", "hi"] | None = None


DocumentStatus = Literal["uploaded", "extracting", "extracted", "failed"]


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


class Evidence(BaseModel):
    document_id: str
    document_name: str
    date: str | None = None
    description: str
    amount: float | None = None
    direction: Literal["credit", "debit"] | None = None

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
    origin: Literal["document", "inference"]
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


class Case(CaseCreate):
    id: str = Field(default_factory=new_id)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    is_demo: bool = False
    documents: list[Document] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    liabilities: list[Liability] = Field(default_factory=list)
    inference_runs: list[InferenceRun] = Field(default_factory=list)

    def get_document(self, document_id: str) -> Document | None:
        return next((d for d in self.documents if d.id == document_id), None)

    def get_item(self, item_id: str) -> Asset | Liability | None:
        return next((i for i in [*self.assets, *self.liabilities] if i.id == item_id), None)
