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


def demo_case() -> Case:
    """The sample family with all 9 documents read (recorded Gemini readings), in upload order, as the app has it."""
    from app import demo
    from tools.asset_map import sync_documents

    case = demo.new_demo_case()
    for path in demo.demo_documents():
        add_doc(case, recorded(path.stem), path.name)
    sync_documents(case, date(2026, 10, 16))
    return case


def recorded_raw(kind: str, stem: str) -> str:
    """A real Gemini reply recorded by scripts/record_samples.py --record."""
    return json.loads((RECORDED_DIR.parent / kind / f"{stem}.json").read_text())["raw_response"]


def infer_kavach(case: Case) -> None:
    """Apply the inference result Gemini gives for the planted Kavach premiums (all three NACH debits cited)."""
    from app.models import InferenceResult
    from tools.inference import apply_proposals, collect_transactions

    refs = collect_transactions(case)
    ids = [r.id for r in refs if "KAVACH" in r.description]
    result = InferenceResult.model_validate({"items": [{
        "kind": "asset", "type": "life_insurance", "institution": "KAVACH LIFE INS", "identifier_hint": None,
        "reason": "Monthly premiums to Kavach Life point to a policy.", "evidence_transaction_ids": ids,
        "confidence": "high"}]})
    apply_proposals(case, result, refs, "test", today=date(2026, 10, 16))
