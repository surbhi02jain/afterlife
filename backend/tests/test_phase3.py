"""Knowledge base, action plan, follow-up questions and letters. No network."""

from datetime import date

import pytest

import kb
from app.models import InferenceResult
from tests.helpers import add_doc, loan_sms, new_case, premium_receipt, recorded
from tools.asset_map import sync_documents
from tools.inference import apply_proposals, collect_transactions
from tools.letters import draft_letter, letter_pdf
from tools.plan import build_plan
from tools.questions import QuestionDraft, add_questions, apply_answer, find_gaps

TODAY = date(2026, 10, 16)


def full_case(language="en"):
    """The demo family as Gemini really extracted it, plus both planted assets inferred."""
    case = new_case(language=language)
    for stem in ["01_bank_statement_p1", "02_bank_statement_p2", "04_fd_advice", "06_premium_receipt",
                 "07_loan_emi_sms", "08_mf_statement", "09_epf_passbook"]:
        add_doc(case, recorded(stem), f"{stem}.png")
    sync_documents(case, TODAY)
    refs = collect_transactions(case)

    def ids(needle):
        return [r.id for r in refs if needle in r.description.upper()]

    apply_proposals(case, InferenceResult.model_validate({"items": [
        {"kind": "asset", "type": "life_insurance", "institution": "KAVACH LIFE INS", "identifier_hint": None,
         "reason": "Monthly premiums.", "evidence_transaction_ids": ids("KAVACH"), "confidence": "high"},
        {"kind": "asset", "type": "demat_account", "institution": "ANAND STOCKBROKING", "identifier_hint": None,
         "reason": "Dividends.", "evidence_transaction_ids": ids("DIV") + ids("ANAND"), "confidence": "high"},
        {"kind": "liability", "type": "home_loan", "institution": "GRIHA SETU HFL", "identifier_hint": None,
         "reason": "EMIs.", "evidence_transaction_ids": ids("EMI DR"), "confidence": "high"},
    ]}), refs, "test", today=TODAY)
    return case


def item(case, type_, word=""):
    return next(i for i in [*case.assets, *case.liabilities] if i.type == type_ and word in (i.institution or "").lower())


# --- knowledge base --------------------------------------------------------------------------------

REQUIRED_KB = {"general", "bank_savings_account", "fixed_deposit", "life_insurance", "mutual_funds", "demat_shares",
               "epf", "ppf", "loan"}


def test_kb_has_every_required_entry_marked_unverified():
    entries = kb.entries()
    assert REQUIRED_KB <= set(entries)
    for key, e in entries.items():
        assert e["verified"] is False, key
        assert e["source_name"]
        for field in ("steps", "documents_required", "typical_timeline", "title"):
            assert e[field]["en"] and e[field]["hi"], (key, field)


def test_lookup_maps_item_types_and_reports_missing():
    assert kb.lookup("savings_account")["key"] == "bank_savings_account"
    assert kb.lookup("home_loan", "hi")["steps"][0].startswith("लेंडर")
    missing = kb.lookup("other_asset")
    assert missing["found"] is False and "confirm with the institution" in missing["message"]


# --- action plan -----------------------------------------------------------------------------------

def test_plan_order_grouping_and_flags():
    case = full_case()
    plan = build_plan(case, TODAY)
    order = [t.institution for t in plan.tasks]

    # EMI (5 Nov) and Kavach premium (7 Nov) auto-debits are within 45 days, so they come first
    assert order[0] == "Griha Setu Housing Finance" and plan.tasks[0].time_sensitive
    assert "5 Nov 2026" in plan.tasks[0].time_sensitive[0]
    assert order[1] == "KAVACH LIFE INS"
    # savings account + FD at the same bank are one task
    sahyadri = next(t for t in plan.tasks if "SAHYADRI" in t.institution)
    assert {i.type for i in sahyadri.items} == {"savings_account", "fixed_deposit"}
    assert [t.order for t in plan.tasks] == list(range(1, len(plan.tasks) + 1))
    assert plan.days_since_death == 44 and "not legal advice" in plan.disclaimer


def test_probable_task_starts_by_asking_and_cites_kb():
    plan = build_plan(full_case(), TODAY)
    kavach = next(t for t in plan.tasks if t.institution == "KAVACH LIFE INS")
    assert kavach.needs_confirmation
    assert kavach.first_step.startswith("Ask KAVACH LIFE INS to confirm whether")
    assert kavach.steps[1:] == kb.lookup("life_insurance")["steps"]
    assert kavach.source_names == [kb.lookup("life_insurance")["source_name"]] and kavach.verified is False


def test_board_status_survives_rebuild_and_rejected_items_drop_out():
    case = full_case()
    case.plan = build_plan(case, TODAY)
    case.plan.tasks[2].board_status = "in_progress"
    kept = case.plan.tasks[2].id
    item(case, "demat_account").status = "rejected"
    case.plan = build_plan(case, TODAY)
    assert next(t for t in case.plan.tasks if t.id == kept).board_status == "in_progress"
    assert not any("ANAND" in t.institution for t in case.plan.tasks)


def test_plan_in_hindi():
    plan = build_plan(full_case("hi"), TODAY)
    assert "कानूनी सलाह नहीं" in plan.disclaimer
    assert "नवंबर" in plan.tasks[0].time_sensitive[0]
    assert plan.general_steps == kb.lookup("general", "hi")["steps"]


# --- questions -------------------------------------------------------------------------------------

def test_gaps_cover_probable_items_missing_nominee_and_claimant():
    case = full_case()
    gaps = {g.target: g for g in reversed(find_gaps(case))}
    assert gaps["confirm_item"].options == ["Yes", "No", "Not sure"]
    assert {g.item_id for g in find_gaps(case) if g.target == "confirm_item"} == {
        item(case, "life_insurance", "kavach").id, item(case, "demat_account").id}
    assert {"death_certificate", "claimant_name", "claimant_address"} <= {g.target for g in find_gaps(case)}


def test_questions_only_for_real_gaps_and_capped():
    case = full_case()
    gaps = find_gaps(case)
    drafts = [QuestionDraft(gap_id="made-up", text="?", why="?")] + [
        QuestionDraft(gap_id=g.id, text=f"Question {n}", why="w") for n, g in enumerate(gaps)]
    created = add_questions(case, gaps, drafts)
    assert len(created) == 4
    assert all(q.target in {g.target for g in gaps} for q in created)
    # asked gaps are not offered again
    assert {g.id for g in find_gaps(case)}.isdisjoint({g.id for g in gaps[:4]})


@pytest.mark.parametrize("answer, status", [("Yes", "confirmed"), ("No", "rejected"), ("Not sure", "probable"),
                                            ("हाँ", "confirmed")])
def test_answering_a_confirm_question_updates_the_item(answer, status):
    case = full_case()
    gap = next(g for g in find_gaps(case) if g.target == "confirm_item")
    [q] = add_questions(case, [gap], [QuestionDraft(gap_id=gap.id, text="Did they?", why="w")])
    apply_answer(case, q.id, answer)
    assert case.get_item(gap.item_id).status == status
    assert q.status == "answered" and q.answer == answer


def test_answers_fill_nominee_and_claimant_details():
    case = full_case()
    gaps = find_gaps(case)
    by_target = {g.target: g for g in gaps}
    qs = add_questions(case, gaps, [QuestionDraft(gap_id=by_target[t].id, text=t, why="w")
                                     for t in ("item_nominee", "claimant_name", "death_certificate")])
    apply_answer(case, qs[0].id, "Kamala Suresh Rao")
    apply_answer(case, qs[1].id, "Arjun Suresh Rao")
    apply_answer(case, qs[2].id, "Applied for it")
    assert item(case, "epf").nominee == "Kamala Suresh Rao"
    assert case.facts.claimant_name == "Arjun Suresh Rao" and case.facts.death_certificate == "applied"


# --- letters ---------------------------------------------------------------------------------------

def test_claim_letter_uses_full_number_and_kb_documents():
    case = full_case()
    case.facts.claimant_name = "Arjun Suresh Rao"
    letter = draft_letter(case, item(case, "life_insurance", "jeevan").id, TODAY)
    assert letter.kind == "claim_intimation"
    assert "policy no. 784512093" in letter.body and "passed away on 2 Sep 2026" in letter.body
    for doc in kb.lookup("life_insurance")["documents_required"]:
        assert doc in letter.body
    assert "Arjun Suresh Rao" in letter.body and "[Your address]" in letter.body


def test_enquiry_letter_for_probable_item_never_claims_it_exists():
    case = full_case()
    letter = draft_letter(case, item(case, "life_insurance", "kavach").id, TODAY)
    assert letter.kind == "existence_enquiry"
    assert "confirm whether any life insurance policy exists" in letter.body
    assert letter.body.count("Rs 3,150.00") == 3
    assert "policy no." not in letter.body


def test_hindi_letter_and_pdf():
    case = full_case("hi")
    letter = draft_letter(case, item(case, "demat_account").id, TODAY)
    assert "विषय:" in letter.body and "पुष्टि" in letter.body
    pdf = letter_pdf(letter)
    assert pdf.startswith(b"%PDF") and len(pdf) > 5000


def test_statement_debits_are_linked_to_documented_loan_and_fund():
    case = full_case()
    loan = item(case, "home_loan")
    assert [e.date for e in loan.evidence if e.direction == "debit"] == ["2026-06-05", "2026-07-05", "2026-08-05"]
    assert loan.next_expected_debit == "2026-11-05"
    fund = item(case, "mutual_fund")
    assert fund.next_expected_debit == "2026-11-10"
    # an account's own statement rows are not "evidence" of itself
    savings = item(case, "savings_account", "sahyadri")
    assert all(e.direction is None for e in savings.evidence)


def test_plan_puts_the_soonest_auto_debit_first():
    plan = build_plan(full_case(), TODAY)
    assert [t.institution for t in plan.tasks[:3]] == ["Griha Setu Housing Finance", "KAVACH LIFE INS",
                                                       "NAVODAYA MUTUAL FUND"]
