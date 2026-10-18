from datetime import date, timedelta

import pytest

from app import services
from tests.conftest import FakeClient
from tools import extraction
from tools.extraction import ExtractionError

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


def test_family_can_see_the_file_they_uploaded_but_no_one_else_can(api, storage):
    case = make_case(api)
    doc = upload(api, case["id"]).json()[0]
    url = f"/api/cases/{case['id']}/documents/{doc['id']}/file"
    response = api.get(url)
    assert response.status_code == 200 and response.content == PNG
    assert response.headers["content-type"] == "image/png" and "no-store" in response.headers["cache-control"]
    api.cookies.clear()  # another browser, without this case's key
    assert api.get(url).status_code == 404


def test_thumbnail_is_a_small_jpeg_and_files_without_one_say_so(api, storage):
    from io import BytesIO

    from PIL import Image

    case = make_case(api)
    photo = BytesIO()
    Image.new("RGB", (3000, 4000), "white").save(photo, "PNG")  # a phone-sized page
    doc = upload(api, case["id"], data=photo.getvalue()).json()[0]
    thumb = api.get(f"/api/cases/{case['id']}/documents/{doc['id']}/file?thumb=1")
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/jpeg"
    assert max(Image.open(BytesIO(thumb.content)).size) <= 320

    pdf = upload(api, case["id"], name="scan.pdf", data=b"%PDF-1.4", content_type="application/pdf").json()[0]
    assert api.get(f"/api/cases/{case['id']}/documents/{pdf['id']}/file?thumb=1").status_code == 415

    storage.delete_file(storage.get_case(case["id"]).documents[0].storage_key)  # e.g. the 24-hour rule
    gone = api.get(f"/api/cases/{case['id']}/documents/{doc['id']}/file")
    assert gone.status_code == 410 and gone.headers["content-type"].startswith("text/plain")


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


def test_document_in_someone_elses_name_is_flagged(api, monkeypatch, fake_client):
    # the fake statement belongs to SURESH NARAYAN RAO
    monkeypatch.setattr(extraction, "get_client", lambda: fake_client)
    for name, flagged in (("Demo Person", "SURESH NARAYAN RAO"), ("Suresh Rao", None)):
        case = api.post("/api/cases", json={**CASE, "deceased_name": name}).json()
        doc = upload(api, case["id"]).json()[0]
        api.post(f"/api/cases/{case['id']}/documents/{doc['id']}/extract")
        assert api.get(f"/api/cases/{case['id']}").json()["documents"][0]["other_holder"] == flagged


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


def test_timeout_marks_document_failed_not_stuck(api, monkeypatch):
    monkeypatch.setattr(extraction, "get_client", lambda: FakeClient(error=TimeoutError("read timed out")))
    case = make_case(api)
    doc = upload(api, case["id"]).json()[0]

    response = api.post(f"/api/cases/{case['id']}/documents/{doc['id']}/extract")
    assert response.status_code == 502
    stored = api.get(f"/api/cases/{case['id']}").json()["documents"][0]
    assert stored["status"] == "failed"
    assert "try again" in stored["error"]


def test_upload_rejects_too_many_files(api):
    case = make_case(api)
    files = [("files", (f"{n}.png", PNG, "image/png")) for n in range(21)]
    assert api.post(f"/api/cases/{case['id']}/documents", files=files).status_code == 413


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


def test_future_date_of_death_is_rejected_on_update_and_the_case_stays_readable(api):
    case = make_case(api)
    future = (date.today() + timedelta(days=30)).isoformat()
    assert api.patch(f"/api/cases/{case['id']}", json={"date_of_death": future}).status_code == 422
    assert api.get(f"/api/cases/{case['id']}").status_code == 200


def test_network_error_marks_the_document_failed_instead_of_stuck(api, storage, monkeypatch):
    import httpx

    monkeypatch.setattr(extraction, "get_client", lambda: FakeClient(error=httpx.ReadTimeout("slow")))
    case = make_case(api)
    upload(api, case["id"])
    response = api.post(f"/api/cases/{case['id']}/extract")
    assert response.status_code == 200
    [doc] = response.json()["documents"]
    assert doc["status"] == "failed" and "Couldn't reach Gemini (ReadTimeout)" in doc["error"]


def test_expired_upload_asks_the_family_to_upload_again(api, storage):
    import shutil

    case = make_case(api)
    doc = upload(api, case["id"]).json()[0]
    shutil.rmtree(storage.uploads_dir / case["id"])  # what the 24h bucket lifecycle rule does in production
    response = api.post(f"/api/cases/{case['id']}/documents/{doc['id']}/extract")
    assert response.status_code == 502 and "upload it again" in response.json()["detail"]
    assert storage.get_case(case["id"]).documents[0].status == "failed"


def test_unexpected_error_still_surfaces_but_never_leaves_the_document_stuck(storage):
    from tests.helpers import new_case

    case = storage.create_case(new_case())
    doc = services.add_document(storage, case.id, "a.png", "image/png", PNG)
    with pytest.raises(ExtractionError, match="ZeroDivisionError") as raised:
        services.extract_case_document(storage, case.id, doc.id, client=FakeClient(error=ZeroDivisionError()))
    assert isinstance(raised.value.__cause__, ZeroDivisionError)
    assert storage.get_case(case.id).documents[0].status == "failed"


def test_switching_language_redrafts_plan_and_unedited_letters_only(api, monkeypatch, fake_client):
    case = extracted_case(api, monkeypatch, fake_client)
    item_id = api.get(f"/api/cases/{case['id']}/asset-map").json()["assets"]["confirmed"][0]["id"]
    api.post(f"/api/cases/{case['id']}/plan")
    first = api.post(f"/api/cases/{case['id']}/letters", json={"item_id": item_id}).json()

    body = api.patch(f"/api/cases/{case['id']}", json={"language": "hi"}).json()
    assert body["plan"]["language"] == "hi"
    [letter] = body["letters"]
    assert letter["language"] == "hi" and letter["id"] == first["id"] and "सेवा में" in letter["body"]

    api.put(f"/api/cases/{case['id']}/letters/{letter['id']}", json={"body": "मेरे अपने शब्द।"})
    body = api.patch(f"/api/cases/{case['id']}", json={"language": "en"}).json()
    assert body["plan"]["language"] == "en"
    assert body["letters"][0]["body"] == "मेरे अपने शब्द।"  # the family's edit is never overwritten


def test_removing_a_wrong_upload_takes_its_item_letter_and_questions_with_it(api, storage, monkeypatch, fake_client):
    from tools.questions import QuestionDraft, find_gaps

    case = extracted_case(api, monkeypatch, fake_client)
    doc_id = storage.get_case(case["id"]).documents[0].id
    item_id = api.get(f"/api/cases/{case['id']}/asset-map").json()["assets"]["confirmed"][0]["id"]
    api.post(f"/api/cases/{case['id']}/plan")
    api.post(f"/api/cases/{case['id']}/letters", json={"item_id": item_id})
    storage.update_case(case["id"], lambda c: setattr(c.get_item(item_id), "nominee", None))  # so we ask about it
    gap = next(g for g in find_gaps(storage.get_case(case["id"])) if g.item_id == item_id)
    services.ask_questions(storage, case["id"], [QuestionDraft(gap_id=gap.id, text="Nominee?", why="claims")])

    response = api.delete(f"/api/cases/{case['id']}/documents/{doc_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["documents"] == [] and body["asset_map"]["assets"]["confirmed"] == []
    assert body["letters"] == [] and body["questions"] == [] and body["plan"]["tasks"] == []
    assert body["activity"][-1]["summary_en"] == "Removed statement.png and 1 item it showed"
    assert list((storage.uploads_dir / case["id"]).iterdir()) == []  # the file itself is gone
    assert api.delete(f"/api/cases/{case['id']}/documents/{doc_id}").status_code == 404


def test_edited_letters_survive_removing_their_document(api, storage, monkeypatch, fake_client):
    case = extracted_case(api, monkeypatch, fake_client)
    doc_id = storage.get_case(case["id"]).documents[0].id
    item_id = api.get(f"/api/cases/{case['id']}/asset-map").json()["assets"]["confirmed"][0]["id"]
    letter = api.post(f"/api/cases/{case['id']}/letters", json={"item_id": item_id}).json()
    api.put(f"/api/cases/{case['id']}/letters/{letter['id']}", json={"body": "My own words."})
    body = api.delete(f"/api/cases/{case['id']}/documents/{doc_id}").json()
    assert [l["body"] for l in body["letters"]] == ["My own words."]


def test_document_removed_while_being_read_is_a_clear_error(storage):
    from tests.helpers import new_case

    case = storage.create_case(new_case())
    doc = services.add_document(storage, case.id, "a.png", "image/png", PNG)

    class RemovesItself(FakeClient):
        def __init__(self):
            super().__init__(text="{}")
            outer = self

            class Models:
                calls = []

                def generate_content(self, **kwargs):
                    services.remove_document(storage, case.id, doc.id)
                    raise RuntimeError("never reached by the family")

            outer.models = Models()

    with pytest.raises(extraction.ExtractionError, match="removed"):
        services.extract_case_document(storage, case.id, doc.id, client=RemovesItself())
    assert storage.get_case(case.id).documents == []


def test_case_opens_only_in_the_browser_that_created_it(api):
    from fastapi.testclient import TestClient

    from app.main import app

    created = api.post("/api/cases", json=CASE)
    case_id = created.json()["id"]
    cookie = created.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and f"Path=/api/cases/{case_id}" in cookie
    assert "owner_key_hash" not in created.json()

    stranger = TestClient(app)  # someone who only has the link
    forger = TestClient(app, cookies={f"afterlife_case_{case_id}": "guessed-key"})
    for client in (stranger, forger):
        for method, path, body in (("get", "", None), ("patch", "", {"language": "hi"}), ("get", "/documents", None),
                                   ("post", "/plan", None), ("delete", "", None)):
            response = client.request(method, f"/api/cases/{case_id}{path}", json=body)
            assert response.status_code == 404, (method, path)

    assert api.get(f"/api/cases/{case_id}").status_code == 200  # nothing was deleted, and the owner still gets in


def test_cases_from_before_keys_still_open(api, storage):
    from tests.helpers import new_case

    case = storage.create_case(new_case())
    assert api.get(f"/api/cases/{case.id}").status_code == 200


def test_daily_gemini_limit_stops_spending_and_says_so(api, monkeypatch, fake_client):
    from datetime import date, timedelta

    from app import gemini

    budget = gemini.DailyBudget(1)
    monkeypatch.setattr(gemini, "get_daily_budget", lambda: budget)
    monkeypatch.setattr(extraction, "get_client", lambda: fake_client)
    case = make_case(api)
    first, second = upload(api, case["id"], name="a.png").json()[0], upload(api, case["id"], name="b.png").json()[0]

    assert api.post(f"/api/cases/{case['id']}/documents/{first['id']}/extract").status_code == 200
    response = api.post(f"/api/cases/{case['id']}/documents/{second['id']}/extract")
    assert response.status_code == 502 and "today's limit" in response.json()["detail"]
    assert len(fake_client.models.calls) == 1  # the second request never reached Gemini

    budget._day = date.today() - timedelta(days=1)  # a new day: allowed again
    assert api.post(f"/api/cases/{case['id']}/documents/{second['id']}/extract").status_code == 200


def test_agent_stops_cleanly_at_the_daily_limit(storage, monkeypatch):
    import pytest as _pytest

    from agent.loop import AgentError, run_agent
    from app import gemini
    from tests.test_agent import ScriptedLlm, uploaded_case

    budget = gemini.DailyBudget(1)
    monkeypatch.setattr(gemini, "get_daily_budget", lambda: budget)
    case, _ = uploaded_case(storage)
    with _pytest.raises(AgentError, match="today's limit"):
        run_agent(storage, case.id, model=ScriptedLlm())  # keeps calling tools, so a second model call is needed
    assert storage.get_case(case.id).activity[-1].tool == "agent_error"


def test_leaving_a_case_on_a_shared_computer_locks_this_browser_out(api):
    case = api.post("/api/cases", json=CASE).json()
    assert api.post(f"/api/cases/{case['id']}/leave").status_code == 204
    assert api.get(f"/api/cases/{case['id']}").status_code == 404  # the next person at this computer sees nothing
