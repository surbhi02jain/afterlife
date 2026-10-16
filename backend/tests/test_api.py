from datetime import date, timedelta

import pytest

from app import services
from tests.conftest import FakeClient
from tools import extraction

CASE = {"deceased_name": "Demo Person", "date_of_death": "2026-09-02", "relationship": "son", "language": "en"}
PNG = b"\x89PNG\r\n\x1a\nfake"


def make_case(api):
    response = api.post("/api/cases", json=CASE)
    assert response.status_code == 201
    return response.json()


def upload(api, case_id, name="statement.png", data=PNG, content_type="image/png"):
    return api.post(f"/api/cases/{case_id}/documents", files=[("files", (name, data, content_type))])


def test_health(api):
    body = api.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["extraction_model"]


def test_case_crud(api):
    case = make_case(api)
    assert case["deceased_name"] == "Demo Person"
    assert api.get(f"/api/cases/{case['id']}").json()["relationship"] == "son"

    patched = api.patch(f"/api/cases/{case['id']}", json={"language": "hi"}).json()
    assert patched["language"] == "hi"
    assert patched["deceased_name"] == "Demo Person"

    assert api.delete(f"/api/cases/{case['id']}").status_code == 204
    assert api.get(f"/api/cases/{case['id']}").status_code == 404


@pytest.mark.parametrize("bad", [
    {"date_of_death": (date.today() + timedelta(days=1)).isoformat()},
    {"language": "fr"},
    {"deceased_name": ""},
])
def test_case_validation(api, bad):
    assert api.post("/api/cases", json={**CASE, **bad}).status_code == 422


def test_unknown_case_is_404(api):
    assert api.get("/api/cases/doesnotexist").status_code == 404
    assert api.get("/api/cases/..%2F..%2Fetc").status_code == 404


def test_upload_and_list(api, storage):
    case = make_case(api)
    response = upload(api, case["id"])
    assert response.status_code == 201
    doc = response.json()[0]
    assert doc["status"] == "uploaded" and doc["size_bytes"] == len(PNG)
    assert "storage_key" not in doc  # internals stay server-side
    stored = storage.get_case(case["id"]).documents[0]
    assert storage.read_file(stored.storage_key) == PNG
    assert len(api.get(f"/api/cases/{case['id']}/documents").json()) == 1


def test_upload_guesses_type_from_extension(api, storage):
    case = make_case(api)
    response = upload(api, case["id"], name="scan.pdf", data=b"%PDF-1.4", content_type="application/octet-stream")
    assert response.status_code == 201
    assert storage.get_case(case["id"]).documents[0].content_type == "application/pdf"


def test_upload_rejects_unsupported_type(api):
    case = make_case(api)
    assert upload(api, case["id"], name="notes.txt", data=b"hi", content_type="text/plain").status_code == 415


def test_extract_success(api, monkeypatch, fake_client):
    monkeypatch.setattr(extraction, "get_client", lambda: fake_client)
    case = make_case(api)
    doc = upload(api, case["id"]).json()[0]

    response = api.post(f"/api/cases/{case['id']}/documents/{doc['id']}/extract")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "extracted"
    assert body["document_type"] == "bank_statement" and body["transactions"] == 2
    assert "extraction" not in body


def test_extract_failure_is_recorded_not_hidden(api, monkeypatch):
    monkeypatch.setattr(extraction, "get_client", lambda: FakeClient(text="not json"))
    case = make_case(api)
    doc = upload(api, case["id"]).json()[0]

    response = api.post(f"/api/cases/{case['id']}/documents/{doc['id']}/extract")
    assert response.status_code == 502
    stored = api.get(f"/api/cases/{case['id']}").json()["documents"][0]
    assert stored["status"] == "failed"
    assert "did not match" in stored["error"]
    assert stored["document_type"] is None


def test_extract_without_api_key_fails_clearly(api):
    case = make_case(api)
    doc = upload(api, case["id"]).json()[0]
    response = api.post(f"/api/cases/{case['id']}/documents/{doc['id']}/extract")
    assert response.status_code == 502
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_extract_all_runs_every_pending_document(api, storage, fake_client):
    case = make_case(api)
    for name in ["a.png", "b.png", "c.png"]:
        upload(api, case["id"], name=name)
    result = services.extract_pending(storage, case["id"], client=fake_client)
    assert [d.status for d in result.documents] == ["extracted"] * 3
    assert len(fake_client.models.calls) == 3


def test_delete_case_removes_uploads(api, storage):
    case = make_case(api)
    upload(api, case["id"])
    key = storage.get_case(case["id"]).documents[0].storage_key
    api.delete(f"/api/cases/{case['id']}")
    with pytest.raises(FileNotFoundError):
        storage.read_file(key)


# --- asset map endpoints ---------------------------------------------------------------------------

INFERENCE_REPLY = {"items": [
    {"kind": "asset", "type": "life_insurance", "institution": "KAVACH LIFE INS", "identifier_hint": None,
     "reason": "Looks like a monthly premium.", "evidence_transaction_ids": ["T1"], "confidence": "medium"},
    {"kind": "asset", "type": "demat_account", "institution": "Anand Stockbroking", "identifier_hint": None,
     "reason": "Made up.", "evidence_transaction_ids": ["T42"], "confidence": "high"},
]}


def extracted_case(api, monkeypatch, fake_client):
    monkeypatch.setattr(extraction, "get_client", lambda: fake_client)
    case = make_case(api)
    doc = upload(api, case["id"]).json()[0]
    api.post(f"/api/cases/{case['id']}/documents/{doc['id']}/extract")
    return case


def test_extraction_fills_asset_map(api, monkeypatch, fake_client):
    case = extracted_case(api, monkeypatch, fake_client)
    body = api.get(f"/api/cases/{case['id']}/asset-map").json()
    [account] = body["assets"]["confirmed"]
    assert account["type"] == "savings_account" and account["identifier_masked"] == "XXXX1931"
    assert body["assets"]["probable"] == []
    assert body["totals"]["confirmed_assets_total"] == 199548.6


def test_infer_endpoint_adds_only_evidenced_probable_items(api, monkeypatch, fake_client):
    import json

    from tools import inference

    case = extracted_case(api, monkeypatch, fake_client)
    monkeypatch.setattr(inference, "get_client", lambda: FakeClient(text=json.dumps(INFERENCE_REPLY)))

    body = api.post(f"/api/cases/{case['id']}/infer").json()
    assert len(body["run"]["added"]) == 1
    assert "no valid transaction evidence" in body["run"]["discarded"][0]
    [probable] = body["asset_map"]["assets"]["probable"]
    assert probable["institution"] == "KAVACH LIFE INS"
    assert probable["evidence"][0]["description"].startswith("NACH DR-KAVACH")
    assert body["asset_map"]["totals"]["confirmed_assets_count"] == 1  # probable never counted


def test_mark_item_confirmed_or_not_applicable(api, monkeypatch, fake_client):
    import json

    from tools import inference

    case = extracted_case(api, monkeypatch, fake_client)
    monkeypatch.setattr(inference, "get_client", lambda: FakeClient(text=json.dumps(INFERENCE_REPLY)))
    item_id = api.post(f"/api/cases/{case['id']}/infer").json()["run"]["added"][0]

    body = api.post(f"/api/cases/{case['id']}/items/{item_id}/status", json={"status": "rejected"}).json()
    assert body["assets"]["rejected"][0]["id"] == item_id
    body = api.post(f"/api/cases/{case['id']}/items/{item_id}/status", json={"status": "confirmed"}).json()
    assert {a["id"] for a in body["assets"]["confirmed"]} >= {item_id}
    assert body["assets"]["confirmed"][-1]["decided_by_user"] is True

    assert api.post(f"/api/cases/{case['id']}/items/nope/status", json={"status": "confirmed"}).status_code == 404
    assert api.post(f"/api/cases/{case['id']}/items/{item_id}/status", json={"status": "maybe"}).status_code == 422


def test_infer_with_no_transactions_is_a_clear_error(api):
    case = make_case(api)
    response = api.post(f"/api/cases/{case['id']}/infer")
    assert response.status_code == 502 and "no transactions" in response.json()["detail"]


def test_answers_flow_into_unedited_letters_but_never_overwrite_edits(api, storage, monkeypatch, fake_client):
    from tools.questions import QuestionDraft, find_gaps

    case = extracted_case(api, monkeypatch, fake_client)
    item_id = api.get(f"/api/cases/{case['id']}/asset-map").json()["assets"]["confirmed"][0]["id"]
    letter = api.post(f"/api/cases/{case['id']}/letters", json={"item_id": item_id}).json()
    assert "[Your full name]" in letter["body"]

    gap = next(g for g in find_gaps(storage.get_case(case["id"])) if g.target == "claimant_name")
    services.ask_questions(storage, case["id"], [QuestionDraft(gap_id=gap.id, text="Your name?", why="letters")])
    question = storage.get_case(case["id"]).questions[0]
    body = api.post(f"/api/cases/{case['id']}/questions/{question.id}/answer", json={"answer": "Arjun Rao"}).json()
    assert "Arjun Rao" in body["letters"][0]["body"]

    api.put(f"/api/cases/{case['id']}/letters/{letter['id']}", json={"body": "My own words."})
    api.post(f"/api/cases/{case['id']}/items/{item_id}/status", json={"status": "confirmed"})
    assert api.get(f"/api/cases/{case['id']}").json()["letters"][0]["body"] == "My own words."
