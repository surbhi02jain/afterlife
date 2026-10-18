"""Schema validation against RECORDED Gemini responses (scripts/run_extraction.py --record). No network."""

import json
from pathlib import Path

import pytest

from app.demo import RECORDED_DIR, demo_documents
from app.models import DocumentType, ExtractedDocument
from tools.extraction import ExtractionError, parse_extraction

FIXTURES = RECORDED_DIR

EXPECTED_TYPE = {
    "01_bank_statement_p1": DocumentType.bank_statement,
    "02_bank_statement_p2": DocumentType.bank_statement,
    "03_coop_passbook": DocumentType.passbook,
    "04_fd_advice": DocumentType.other,
    "05_upi_history": DocumentType.upi_history,
    "06_premium_receipt": DocumentType.premium_receipt,
    "07_loan_emi_sms": DocumentType.loan_sms,
    "08_mf_statement": DocumentType.mutual_fund_statement,
    "09_epf_passbook": DocumentType.epf_passbook,
}


def recorded():
    return sorted(FIXTURES.glob("*.json"))


def load(path: Path) -> ExtractedDocument:
    return parse_extraction(json.loads(path.read_text())["raw_response"])


def test_every_demo_doc_has_a_recorded_fixture():
    missing = {p.stem for p in demo_documents()} - {p.stem for p in recorded()}
    assert not missing, f"record with: .venv/bin/python scripts/run_extraction.py --record  (missing {sorted(missing)})"


@pytest.mark.parametrize("path", recorded(), ids=lambda p: p.stem)
def test_recorded_response_validates(path):
    doc = load(path)
    if path.stem in EXPECTED_TYPE:
        assert doc.document_type == EXPECTED_TYPE[path.stem]
    for txn in doc.transactions:
        assert txn.amount >= 0


def test_statement_page1_reads_planted_evidence():
    path = FIXTURES / "01_bank_statement_p1.json"
    if not path.exists():
        pytest.skip("not recorded yet")
    doc = load(path)
    narrations = " | ".join(t.description.upper() for t in doc.transactions)
    assert "KAVACH" in narrations
    assert "DIVIDEND" in narrations
    kavach = [t for t in doc.transactions if "KAVACH" in t.description.upper()]
    assert all(t.direction == "debit" and t.amount == 3150 for t in kavach)
    assert len(kavach) == 2


# --- hand-written malformed replies: these must be rejected, never patched up --------------------

VALID = {
    "institution": "Sahyadri National Bank", "document_type": "bank_statement", "identifier": "30218847201931",
    "holder_name": "SURESH NARAYAN RAO", "nominee": None,
    "amounts": [{"label": "closing balance", "value": 199548.6, "currency": "INR"}],
    "dates": [{"label": "statement from", "date": "2026-06-01"}],
    "transactions": [{"date": "2026-06-07", "description": "NACH DR-KAVACH LIFE", "amount": 3150, "direction": "debit"}],
    "language_detected": "en", "confidence": "high",
}


def variant(**changes):
    data = json.loads(json.dumps(VALID))
    for key, value in changes.items():
        if value is ...:
            del data[key]
        else:
            data[key] = value
    return json.dumps(data)


def test_valid_hand_written_reply_parses():
    doc = parse_extraction(json.dumps(VALID))
    assert doc.transactions[0].direction == "debit"


@pytest.mark.parametrize(
    "raw",
    [
        variant(document_type="credit_card"),
        variant(confidence="very high"),
        variant(transactions=[{"date": "07/06/2026", "description": "x", "amount": 1, "direction": "debit"}]),
        variant(transactions=[{"date": "2026-02-30", "description": "x", "amount": 1, "direction": "debit"}]),
        variant(transactions=[{"date": None, "description": "x", "amount": 1, "direction": "out"}]),
        variant(dates=[{"label": "due", "date": "next month"}]),
        variant(transactions=...),
        variant(document_type=...),
        "this is not json",
        "",
    ],
    ids=["bad-enum", "bad-confidence", "non-iso-date", "impossible-date", "bad-direction",
         "bad-labeled-date", "missing-transactions", "missing-type", "not-json", "empty"],
)
def test_malformed_reply_is_rejected(raw):
    with pytest.raises(ExtractionError, match="did not match the extraction schema"):
        parse_extraction(raw)


def test_schema_sent_to_gemini_lists_every_document_type():
    schema = ExtractedDocument.model_json_schema()
    assert schema["$defs"]["DocumentType"]["enum"] == [t.value for t in DocumentType]
    assert set(schema["required"]) >= {"document_type", "transactions", "confidence", "language_detected"}
