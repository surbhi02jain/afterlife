"""Builders for cases with extracted documents, so asset-map tests need no storage or network."""

import json
from datetime import date
from pathlib import Path

from app.demo import RECORDED_DIR
from app.models import Case, Document, ExtractedDocument
from tools.extraction import parse_extraction

FIXTURES = RECORDED_DIR


def recorded(stem: str) -> ExtractedDocument:
    """A real Gemini reply recorded by scripts/run_extraction.py --record."""
    return parse_extraction(json.loads((FIXTURES / f"{stem}.json").read_text())["raw_response"])


def extracted(**fields) -> ExtractedDocument:
    base = {"institution": None, "document_type": "other", "identifier": None, "holder_name": None, "nominee": None,
            "amounts": [], "dates": [], "transactions": [], "language_detected": "en", "confidence": "high"}
    return ExtractedDocument.model_validate({**base, **fields})


def new_case(**fields) -> Case:
    return Case(deceased_name="Demo Person", date_of_death=date(2026, 9, 2), relationship="son", **fields)


def add_doc(case: Case, extraction: ExtractedDocument, filename: str = "doc.png") -> Document:
    doc = Document(filename=filename, content_type="image/png", size_bytes=1, storage_key="k",
                   status="extracted", extraction=extraction)
    case.documents.append(doc)
    return doc


def loan_sms() -> ExtractedDocument:
    return extracted(
        institution="Griha Setu Housing Finance", document_type="loan_sms", identifier="XXXXXXX7782",
        amounts=[{"label": "EMI", "value": 18450}, {"label": "Principal outstanding", "value": 1162904}],
        dates=[{"label": "EMI due", "date": "2026-09-05"}],
        transactions=[{"date": "2026-08-05", "description": "EMI received for Home Loan A/c XXXXXXX7782",
                       "amount": 18450, "direction": "debit"}],
    )


def premium_receipt() -> ExtractedDocument:
    return extracted(
        institution="JEEVAN RAKSHA LIFE INSURANCE CORPORATION", document_type="premium_receipt",
        identifier="784512093", nominee="Kamala Suresh Rao (Wife)",
        amounts=[{"label": "Sum Assured", "value": 500000}, {"label": "Premium Amount Paid", "value": 24380}],
        dates=[{"label": "Receipt Date", "date": "2026-07-14"}],
    )
