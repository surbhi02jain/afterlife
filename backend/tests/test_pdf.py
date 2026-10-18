"""Password-protected PDFs: locked on upload, opened with the family's password, never stored. No network."""

import io

import pytest
from fpdf import FPDF
from pypdf import PdfReader, PdfWriter

from app import services
from tests.test_api import make_case, upload
from tools import extraction, pdf
from tools.extraction import ExtractionError

PASSWORD = "SURE0512"


def make_pdf(user_password=None, owner_password="bank-owner"):
    doc = FPDF()
    doc.add_page()
    doc.set_font("helvetica", size=12)
    doc.cell(0, 10, "Closing balance 1,99,548.60")
    data = bytes(doc.output())
    if user_password is None:
        return data
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    writer.encrypt(user_password=user_password, owner_password=owner_password, algorithm="AES-256")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def text_of(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    assert not reader.is_encrypted
    return reader.pages[0].extract_text()


def test_prepare_leaves_plain_pdfs_and_non_pdfs_alone():
    plain = make_pdf()
    assert pdf.prepare(plain) == (plain, False)
    assert pdf.prepare(b"%PDF-1.4") == (b"%PDF-1.4", False)  # unparseable: Gemini decides


def test_prepare_opens_owner_only_pdfs_right_away():
    data, locked = pdf.prepare(make_pdf(user_password=""))
    assert not locked and "1,99,548.60" in text_of(data)


def test_unlock_with_right_and_wrong_password():
    locked = make_pdf(PASSWORD)
    assert pdf.prepare(locked) == (locked, True)
    with pytest.raises(pdf.WrongPassword):
        pdf.unlock(locked, "wrong")
    assert "1,99,548.60" in text_of(pdf.unlock(locked, PASSWORD))


def test_locked_upload_waits_for_password_then_reads(api, storage, monkeypatch, fake_client):
    monkeypatch.setattr(extraction, "get_client", lambda: fake_client)
    case = make_case(api)
    doc = upload(api, case["id"], name="statement.pdf", data=make_pdf(PASSWORD),
                 content_type="application/pdf").json()[0]
    assert doc["status"] == "locked"

    # Locked files are skipped by "read all" and refused (not failed) by a direct read.
    services.extract_pending(storage, case["id"])
    assert storage.get_case(case["id"]).documents[0].status == "locked"
    assert api.post(f"/api/cases/{case['id']}/documents/{doc['id']}/extract").status_code == 502
    assert storage.get_case(case["id"]).documents[0].status == "locked"
    assert fake_client.models.calls == []

    url = f"/api/cases/{case['id']}/documents/{doc['id']}/unlock"
    wrong = api.post(url, json={"password": "wrong"})
    assert wrong.status_code == 400 and "didn't open" in wrong.json()["detail"]

    assert api.post(url, json={"password": PASSWORD}).json()["status"] == "uploaded"
    stored = storage.get_case(case["id"])
    assert "1,99,548.60" in text_of(storage.read_file(stored.documents[0].storage_key))
    assert PASSWORD not in stored.model_dump_json()  # never stored, not even in the activity log
    assert stored.activity[-1].tool == "unlock_document"

    assert api.post(f"/api/cases/{case['id']}/documents/{doc['id']}/extract").json()["status"] == "extracted"


def test_unlock_unknown_document_and_empty_password(api):
    case = make_case(api)
    assert api.post(f"/api/cases/{case['id']}/documents/nope/unlock", json={"password": "x"}).status_code == 404
    doc = upload(api, case["id"], name="s.pdf", data=make_pdf(PASSWORD), content_type="application/pdf").json()[0]
    assert api.post(f"/api/cases/{case['id']}/documents/{doc['id']}/unlock", json={"password": ""}).status_code == 422


def test_demo_case_has_a_locked_statement_that_replays_once_opened(storage, monkeypatch):
    from app import demo

    case = services.create_demo_case(storage)
    [locked] = [d for d in case.documents if d.status == "locked"]
    assert locked.filename == "08_mf_statement.pdf" and len(case.documents) == 9

    services.unlock_document(storage, case.id, locked.id, demo.DEMO_PDF_PASSWORD)
    monkeypatch.setattr(extraction, "get_client", lambda: pytest.fail("demo replay must not call Gemini"))
    doc = services.extract_case_document(storage, case.id, locked.id)
    assert doc.extracted_with_model.endswith("(recorded)")  # the unlocked bytes match the recorded reading
    assert doc.extraction.identifier == "1048832/57"
