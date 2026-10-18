"""Name check: Gemini's recorded comparison of the sample family's names, verified by code."""

import json

import pytest

from app import services
from app.models import NameCheckResult
from tests.helpers import add_doc, demo_case, extracted, new_case, recorded_raw
from tools.names import build_prompt, name_list, needs_check, normalize, parse_result, verify


def finding(kind, *mentions, explanation="They differ."):
    return NameCheckResult.model_validate({"findings": [{
        "kind": kind, "explanation": explanation,
        "mentions": [{"ref": ref, "role": role, "name": name} for ref, role, name in mentions]}]})


def test_recorded_check_finds_both_planted_differences():
    case = demo_case()
    listed = name_list(case)
    check = verify(listed, parse_result(recorded_raw("names", "demo_case")), "test")

    assert check.discarded == []
    issues = {i.kind: i for i in check.issues}
    assert set(issues) == {"deceased_name_differs", "nominee_name_differs"}
    deceased = {row["name"]: row["where"] for row in issues["deceased_name_differs"].names}
    assert deceased["S N RAO"] == ["09_epf_passbook.png"]
    nominee = {row["name"]: row["where"] for row in issues["nominee_name_differs"].names}
    assert nominee["Smt. Kamla Rao"] == ["03_coop_passbook.png"]
    # only one row per way of writing it: case and titles don't count as a difference
    assert len(issues["deceased_name_differs"].names) == 2
    assert "D9" not in issues["deceased_name_differs"].explanation  # our refs are replaced by the file the family knows


def test_recorded_reply_matches_the_prompt_the_app_sends():
    from app import demo

    prompt = build_prompt(name_list(demo_case()))
    assert demo.recorded("names", prompt.encode()) is not None  # so the demo replays it instead of calling Gemini


def test_misquoted_names_are_discarded():
    listed = name_list(demo_case())
    check = verify(listed, finding("deceased_name_differs", ("FAMILY", "deceased", "Suresh Narayan Rao"),
                                   ("D9", "holder", "S. N. Rao")), "test")  # the passbook says "S N RAO"
    assert check.issues == [] and "not found" in check.discarded[0]


def test_findings_that_do_not_really_differ_are_discarded():
    listed = name_list(demo_case())
    check = verify(listed, finding("deceased_name_differs", ("FAMILY", "deceased", "Suresh Narayan Rao"),
                                   ("D1", "holder", "SURESH NARAYAN RAO")), "test")
    assert check.issues == [] and "don't actually differ" in check.discarded[0]


@pytest.mark.parametrize("a, b", [("SURESH NARAYAN RAO", "Mr. Suresh Narayan Rao"),
                                  ("Kamala Suresh Rao (Wife)", "Smt. KAMALA SURESH RAO")])
def test_titles_case_and_brackets_are_not_differences(a, b):
    assert normalize(a) == normalize(b)


def test_matching_names_need_no_gemini_call(storage, fake_client):
    case = new_case()
    add_doc(case, extracted(holder_name="DEMO PERSON", nominee="Kamala Rao"))
    add_doc(case, extracted(holder_name="Mr. Demo Person", nominee="Kamala Rao (Wife)"))
    storage.create_case(case)
    assert not needs_check(name_list(case))
    check = services.check_names(storage, case.id, client=fake_client)
    assert check.issues == [] and fake_client.models.calls == []
    assert storage.get_case(case.id).name_check.model.startswith("none needed")


def test_a_different_name_is_sent_to_gemini_and_verified(storage, fake_client):
    case = new_case()
    add_doc(case, extracted(holder_name="D. Person"))
    storage.create_case(case)
    fake_client.models.text = json.dumps({"findings": [{
        "kind": "deceased_name_differs", "explanation": "D1 uses initials.",
        "mentions": [{"ref": "FAMILY", "role": "deceased", "name": "Demo Person"},
                     {"ref": "D1", "role": "holder", "name": "D. Person"}]}]})
    check = services.check_names(storage, case.id, client=fake_client)
    assert len(fake_client.models.calls) == 1 and "D1 | holder | D. Person" in fake_client.models.calls[0]["contents"]
    assert check.issues[0].explanation == "doc.png uses initials."


def test_name_check_endpoint_shows_kb_guidance_for_differences(api):
    case = api.post("/api/demo").json()
    # read every sample document (recorded readings) so the names are there to compare
    pdf = next(d for d in case["documents"] if d["status"] == "locked")
    from app import demo
    api.post(f"/api/cases/{case['id']}/documents/{pdf['id']}/unlock", json={"password": demo.DEMO_PDF_PASSWORD})
    api.post(f"/api/cases/{case['id']}/extract")
    view = api.post(f"/api/cases/{case['id']}/name-check").json()
    assert len(view["name_check"]["issues"]) == 2
    assert view["name_guidance"]["found"] and view["name_guidance"]["verified"] is False
    assert view["name_guidance"]["source_name"]


def test_agent_tool_returns_the_differences(storage):
    from agent.tools import ToolContext, dispatch

    case = demo_case()
    storage.create_case(case)
    output = dispatch(ToolContext(storage, case.id, "run1"), "check_names", {})  # demo case: the recorded reply
    assert output["names_compared"] == 14
    assert {d["kind"] for d in output["differences"]} == {"deceased_name_differs", "nominee_name_differs"}
    assert storage.get_case(case.id).activity[-1].run_id == "run1"
