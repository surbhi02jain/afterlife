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
    assert storage.read_file(doc["storage_key"]) == PNG
    assert len(api.get(f"/api/cases/{case['id']}/documents").json()) == 1


def test_upload_guesses_type_from_extension(api):
    case = make_case(api)
    response = upload(api, case["id"], name="scan.pdf", data=b"%PDF-1.4", content_type="application/octet-stream")
    assert response.status_code == 201
    assert response.json()[0]["content_type"] == "application/pdf"


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
    assert body["extraction"]["document_type"] == "bank_statement"
    assert len(body["extraction"]["transactions"]) == 2


def test_extract_failure_is_recorded_not_hidden(api, monkeypatch):
    monkeypatch.setattr(extraction, "get_client", lambda: FakeClient(text="not json"))
    case = make_case(api)
    doc = upload(api, case["id"]).json()[0]

    response = api.post(f"/api/cases/{case['id']}/documents/{doc['id']}/extract")
    assert response.status_code == 502
    stored = api.get(f"/api/cases/{case['id']}").json()["documents"][0]
    assert stored["status"] == "failed"
    assert "did not match" in stored["error"]
    assert stored["extraction"] is None


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
    doc = upload(api, case["id"]).json()[0]
    api.delete(f"/api/cases/{case['id']}")
    with pytest.raises(FileNotFoundError):
        storage.read_file(doc["storage_key"])
