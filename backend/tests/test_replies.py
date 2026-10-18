"""Replies from institutions: Gemini's recorded readings of the sample letter and scam message, acted on by code."""

import json
from datetime import date

from app import services
from app.models import ReplyReading
from tests.helpers import demo_case, infer_kavach, recorded_raw
from tools.letters import draft_reply_letter
from tools.plan import build_plan
from tools.replies import apply_reply, parse_reply, respond_by

TODAY = date(2026, 10, 18)


def planned_case():
    case = demo_case()
    infer_kavach(case)
    case.plan = build_plan(case, TODAY)
    return case


def task_for(case, word):
    return next(t for t in case.plan.tasks if word.lower() in t.institution.lower())


def test_kavach_letter_confirms_the_inferred_policy_and_lists_what_to_send():
    case = planned_case()
    task = task_for(case, "kavach")
    policy = case.get_item(task.items[0].item_id)
    assert policy.status == "probable"

    reply = apply_reply(case, task.id, parse_reply(recorded_raw("replies", "reply_kavach_life")), "kavach.png", "t",
                        TODAY)

    assert reply.red_flags == [] and len(reply.requirements) == 5
    assert reply.respond_by == "2026-11-05"  # letter of 6 Oct + 30 days, worked out in code
    assert reply.confirmed_item_id == policy.id
    assert policy.status == "confirmed" and policy.confidence == "high"
    assert policy.identifier_masked == "XXXX0894" and policy.amount == 1500000
    assert any(e.document_id == f"reply:{reply.id}" for e in policy.evidence)
    assert task.board_status == "in_progress"
    assert "0048817" not in reply.reference_masked  # their reference is masked like any long number


def test_scam_message_changes_nothing_even_though_it_claims_to_confirm_an_account():
    case = planned_case()
    task = task_for(case, "sahyadri")
    reading = parse_reply(recorded_raw("replies", "message_fake_bank"))
    assert reading.confirms_account  # the scam says the money is "ready to release"
    before = case.model_dump_json(exclude={"replies"})

    reply = apply_reply(case, task.id, reading, "message.png", "t", TODAY)

    assert reply.red_flags and reply.requirements == [] and reply.respond_by is None
    assert reply.confirmed_item_id is None
    assert case.model_dump_json(exclude={"replies"}) == before  # no item, task or letter touched


def test_code_catches_a_fee_request_even_when_gemini_reports_no_red_flags():
    case = planned_case()
    task = task_for(case, "kavach")
    reading = ReplyReading.model_validate({
        "institution": "Kavach Life", "letter_date": "2026-10-06", "reference_number": None,
        "outcome": "asks_for_documents", "confirms_account": True, "item_type": "life_insurance",
        "identifier": None, "nominee": None, "amount": None,
        "requirements": [{"document": "Pay processing fee of Rs 999 to release the claim", "detail": None}],
        "respond_within_days": None, "red_flags": [], "summary": "They ask for a fee."})
    reply = apply_reply(case, task.id, reading, "x.png", "t", TODAY)
    assert reply.red_flags == ["asks for a fee or payment to release the money"]
    assert case.get_item(task.items[0].item_id).status == "probable"


def test_respond_by_is_date_arithmetic():
    assert respond_by("2026-10-06", 30, TODAY) == "2026-11-05"
    assert respond_by(None, 15, TODAY) == "2026-11-02"  # no date on the letter: from when it arrived
    assert respond_by("2026-10-06", None, TODAY) is None


def test_cover_letter_quotes_their_reference_and_lists_what_they_asked_for():
    case = planned_case()
    task = task_for(case, "kavach")
    reply = apply_reply(case, task.id, parse_reply(recorded_raw("replies", "reply_kavach_life")), "k.png", "t", TODAY)
    letter = draft_reply_letter(case, reply.id, TODAY)
    assert letter.kind == "reply_cover" and letter.reply_id == reply.id
    assert reply.reference_masked in letter.body and "6 Oct 2026" in letter.body
    assert "1. Claim form A" in letter.body and "5. Cancelled cheque" in letter.body


def test_reply_endpoint_updates_plan_letters_and_activity(api, storage, monkeypatch, fake_client):
    from tools import replies

    case = planned_case()
    case.is_demo = False
    storage.create_case(case)
    fake_client.models.text = recorded_raw("replies", "reply_kavach_life")
    monkeypatch.setattr(replies, "get_client", lambda: fake_client)
    task = task_for(case, "kavach")

    response = api.post(f"/api/cases/{case.id}/plan/tasks/{task.id}/replies",
                        files={"file": ("reply.png", b"\x89PNG fake", "image/png")})
    assert response.status_code == 201
    view = response.json()["case"]
    assert [l["kind"] for l in view["letters"]] == ["reply_cover"]
    kavach = next(t for t in view["plan"]["tasks"] if t["id"] == task.id)
    assert kavach["needs_confirmation"] is False and kavach["board_status"] == "in_progress"
    assert view["activity"][-1]["tool"] == "read_reply"

    reply = view["replies"][0]
    ticked = api.patch(f"/api/cases/{case.id}/replies/{reply['id']}/requirements/{reply['requirements'][0]['id']}",
                       json={"done": True}).json()
    assert ticked["replies"][0]["requirements"][0]["done"] is True


def test_reply_for_an_unknown_task_is_404(api):
    case = api.post("/api/cases", json={"deceased_name": "Asha Rao", "date_of_death": "2026-09-02",
                                        "relationship": "son"}).json()
    response = api.post(f"/api/cases/{case['id']}/plan/tasks/task-nope/replies",
                        files={"file": ("r.png", b"\x89PNG", "image/png")})
    assert response.status_code == 404


def test_demo_samples_are_served_and_matched_to_tasks(api):
    case = api.post("/api/demo").json()
    assert api.get("/api/demo/samples/reply_kavach_life.png").status_code == 200
    assert api.get("/api/demo/samples/../../.env").status_code == 404
    assert api.get("/api/demo/samples/README.md").status_code == 404
    assert case["samples"]["memory"] == "memory_hi.wav"


def test_a_red_flag_only_gemini_spotted_still_blocks_changes():
    case = planned_case()
    task = task_for(case, "kavach")
    reading = parse_reply(recorded_raw("replies", "reply_kavach_life")).model_copy(
        update={"red_flags": ["Call our agent on WhatsApp to speed up the claim"]})
    reply = apply_reply(case, task.id, reading, "x.png", "t", TODAY)
    assert reply.red_flags == ["asks for something a genuine bank or insurer would not"]
    assert reply.red_flag_quotes == ["Call our agent on WhatsApp to speed up the claim"]
    assert reply.confirmed_item_id is None and task.board_status == "todo"


def test_genuine_letter_with_the_usual_otp_warning_and_charges_still_confirms():
    # Real bank letters say "never share your OTP", ask for Aadhaar OTP e-KYC, and charge for duplicates.
    case = planned_case()
    task = task_for(case, "kavach")
    reading = parse_reply(recorded_raw("replies", "reply_kavach_life"))
    reading.summary += " They remind you never to share your OTP or PIN with anyone."
    reading.requirements[0].detail = "Complete Aadhaar OTP-based e-KYC of the nominee"
    reading.requirements[1].detail = "Pay charges of Rs 100 for a duplicate policy bond"

    reply = apply_reply(case, task.id, reading, "kavach.png", "t", TODAY)

    assert reply.red_flags == [] and reply.confirmed_item_id is not None
