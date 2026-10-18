"""Family memories: Gemini's reading of the sample Hindi recording (recorded), matched to transactions by code."""

import json

from app.models import MemoryReading
from tests.helpers import demo_case, infer_kavach, recorded_raw
from tools.finance import totals
from tools.memories import apply_memory, matching_transactions, parse_memory
from tools.inference import collect_transactions


def sample_memory() -> MemoryReading:
    return parse_memory(recorded_raw("memory", "memory_hi"))


def reading(*clues, transcript="...") -> MemoryReading:
    base = {"institution": None, "months": [], "amount_hint": None}
    return MemoryReading.model_validate({"transcript": transcript, "language_detected": "en",
                                         "clues": [{**base, **c} for c in clues]})


def by_type(case, item_type):
    return [i for i in [*case.assets, *case.liabilities] if i.type == item_type and i.status == "probable"]


def test_recorded_memory_backs_the_premiums_and_adds_the_ppf_with_low_confidence():
    case = demo_case()
    before = totals(case)
    memory = apply_memory(case, sample_memory(), "test", "voice")

    kavach = by_type(case, "life_insurance")
    assert len(kavach) == 1 and kavach[0].confidence == "high"  # three monthly premiums back what she remembers
    assert sum(1 for e in kavach[0].evidence if e.direction == "debit") == 3
    assert any(e.document_id.startswith("memory:") for e in kavach[0].evidence)

    ppf = by_type(case, "ppf")
    assert len(ppf) == 1 and ppf[0].confidence == "low"  # no paper shows it: a memory alone is a lead, not a fact
    assert [e.document_id for e in ppf[0].evidence] == [f"memory:{memory.id}"]

    assert totals(case)["confirmed_assets_total"] == before["confirmed_assets_total"]  # probable is never counted
    assert [r.matched_transactions for r in memory.results] == [3, 0]


def test_memory_that_agrees_with_inference_merges_and_raises_confidence():
    case = demo_case()
    infer_kavach(case)
    inferred = by_type(case, "life_insurance")[0]
    inferred.confidence = "medium"
    memory = apply_memory(case, sample_memory(), "test", "voice")

    assert by_type(case, "life_insurance") == [inferred]  # merged, not a second policy
    assert not memory.results[0].created
    assert inferred.confidence == "high"
    assert "remembers" in inferred.reason


def test_unnamed_institution_needs_a_month_or_amount_to_match():
    case = demo_case()
    refs = collect_transactions(case)
    vague = reading({"type": "life_insurance", "what_they_said": "some insurance"}).clues[0]
    assert matching_transactions(vague, refs) == []
    june = reading({"type": "life_insurance", "what_they_said": "insurance in June", "months": [6]}).clues[0]
    found = matching_transactions(june, refs)
    assert [r.date for r in found] == ["2026-06-07"] and "KAVACH" in found[0].description


def test_same_payment_in_statement_and_upi_screenshot_counts_once():
    case = demo_case()
    clue = reading({"type": "demat_account", "institution": "Anand Stockbroking", "what_they_said": "shares"}).clues[0]
    found = matching_transactions(clue, collect_transactions(case))
    assert len(found) == len({(r.date, r.amount) for r in found}) == 2  # DP charge + one Rs 10,000 payment


def test_secrets_and_long_numbers_never_reach_the_case():
    case = demo_case()
    memory = apply_memory(case, reading(
        {"type": "savings_account", "institution": "Sahyadri National Bank",
         "what_they_said": "his ATM PIN is 4412, account 30218847201931"},
        transcript="His ATM PIN is 4 4 1 2 and the account is 30218847201931."), "test", "typed")
    # full numbers stay only in the document extraction, never in what the family said or on items
    stored = " ".join(x.model_dump_json() for x in [*case.memories, *case.assets, *case.liabilities])
    assert "4412" not in stored and "4 4 1 2" not in stored and "30218847201931" not in stored
    assert "[removed]" in memory.transcript and "XXXX1931" in memory.transcript


def test_memory_endpoint_reads_typed_text(api, monkeypatch, fake_client):
    from tools import memories

    fake_client.models.text = json.dumps({"transcript": "He had a PPF at the post office", "language_detected": "en",
                                          "clues": [{"type": "ppf", "institution": "India Post", "months": [],
                                                     "amount_hint": None, "what_they_said": "a PPF at the post office"}]})
    monkeypatch.setattr(memories, "get_client", lambda: fake_client)
    case = api.post("/api/cases", json={"deceased_name": "Asha Rao", "date_of_death": "2026-09-02",
                                        "relationship": "son"}).json()
    response = api.post(f"/api/cases/{case['id']}/memories", data={"text": "He had a PPF at the post office"})
    assert response.status_code == 201
    probable = response.json()["case"]["asset_map"]["assets"]["probable"]
    assert [(i["type"], i["confidence"], i["origin"]) for i in probable] == [("ppf", "low", "family")]
    assert "WHAT THE FAMILY TYPED" in fake_client.models.calls[0]["contents"][0]


def test_memory_needs_exactly_one_of_voice_or_text(api):
    case = api.post("/api/cases", json={"deceased_name": "Asha Rao", "date_of_death": "2026-09-02",
                                        "relationship": "son"}).json()
    assert api.post(f"/api/cases/{case['id']}/memories", data={"text": "  "}).status_code == 400
    both = api.post(f"/api/cases/{case['id']}/memories", data={"text": "hi"},
                    files={"audio": ("m.wav", b"RIFF", "audio/wav")})
    assert both.status_code == 400
    wrong = api.post(f"/api/cases/{case['id']}/memories", files={"audio": ("m.txt", b"x", "text/plain")})
    assert wrong.status_code == 415


def test_a_reply_that_does_not_validate_is_an_error_not_data(api, monkeypatch, fake_client):
    from tools import memories

    fake_client.models.text = '{"transcript": "x"}'
    monkeypatch.setattr(memories, "get_client", lambda: fake_client)
    case = api.post("/api/cases", json={"deceased_name": "Asha Rao", "date_of_death": "2026-09-02",
                                        "relationship": "son"}).json()
    response = api.post(f"/api/cases/{case['id']}/memories", data={"text": "He had a PPF"})
    assert response.status_code == 502 and "schema" in response.json()["detail"]
    after = api.get(f"/api/cases/{case['id']}").json()
    assert after["memories"] == [] and not after["activity"][-1]["ok"]


def test_demo_case_replays_the_recorded_sample_memory(api):
    from app import demo

    case = api.post("/api/demo").json()
    wav = demo.SAMPLE_MEMORY.read_bytes()
    response = api.post(f"/api/cases/{case['id']}/memories", files={"audio": ("memory.wav", wav, "audio/wav")})
    assert response.status_code == 201  # no Gemini key in tests: this only works because the reply is recorded
    assert response.json()["memory"]["model"].endswith("(recorded)")
