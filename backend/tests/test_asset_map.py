from datetime import date

from app.models import InferenceResult
from tests.helpers import add_doc, extracted, loan_sms, new_case, premium_receipt, recorded
from tools.asset_map import sync_documents
from tools.inference import apply_proposals, build_prompt, collect_transactions

TODAY = date(2026, 10, 16)


def statement_case():
    """Both pages of the same savings account, as Gemini really extracted them."""
    case = new_case()
    p1 = add_doc(case, recorded("01_bank_statement_p1"), "01_bank_statement_p1.png")
    p2 = add_doc(case, recorded("02_bank_statement_p2"), "02_bank_statement_p2.png")
    return case, p1, p2


def test_same_account_in_two_documents_is_one_asset():
    case, p1, p2 = statement_case()
    sync_documents(case, TODAY)

    assert len(case.assets) == 1
    account = case.assets[0]
    assert account.type == "savings_account" and account.status == "confirmed"
    assert account.source_document_ids == [p1.id, p2.id]
    assert account.identifier_masked == "XXXX1931"
    assert account.identifier_check == "valid"
    assert len(account.evidence) == 2


def test_latest_document_sets_the_balance_regardless_of_order():
    case, p1, p2 = statement_case()
    case.documents.reverse()  # August page first
    sync_documents(case, TODAY)
    account = case.assets[0]
    assert account.amount_as_of == "2026-08-31"
    assert account.amount == p2.extraction.amounts[-1].value or "closing" in account.amount_label.lower()


def test_sync_is_idempotent():
    case, _, _ = statement_case()
    sync_documents(case, TODAY)
    snapshot = case.model_dump()
    sync_documents(case, TODAY)
    assert case.model_dump() == snapshot


def test_no_full_identifier_is_stored_on_items():
    case, _, _ = statement_case()
    add_doc(case, premium_receipt())
    sync_documents(case, TODAY)
    dumped = " ".join(i.model_dump_json() for i in [*case.assets, *case.liabilities])
    assert "30218847201931" not in dumped
    assert "784512093" not in dumped


def test_loan_sms_becomes_a_liability():
    case = new_case()
    add_doc(case, loan_sms())
    sync_documents(case, TODAY)
    assert case.assets == []
    loan = case.liabilities[0]
    assert loan.type == "home_loan" and loan.status == "confirmed"
    assert loan.amount == 1162904 and loan.identifier_masked == "XXXX7782"


def test_fd_advice_classified_as_other_becomes_fixed_deposit():
    case = new_case()
    add_doc(case, extracted(institution="SAHYADRI NATIONAL BANK", identifier="30219000456712",
                            amounts=[{"label": "Principal Amount", "value": 200000},
                                     {"label": "Maturity Value", "value": 214582.57}],
                            dates=[{"label": "Maturity Date", "date": "2027-03-15"}]))
    sync_documents(case, TODAY)
    fd = case.assets[0]
    assert fd.type == "fixed_deposit" and fd.amount == 214582.57


def test_upi_history_is_not_an_asset():
    case = new_case()
    add_doc(case, extracted(document_type="upi_history", institution="PayDost"))
    sync_documents(case, TODAY)
    assert case.assets == [] and case.liabilities == []


# --- inference merge rules -------------------------------------------------------------------------

def proposals(*items) -> InferenceResult:
    return InferenceResult.model_validate({"items": list(items)})


def kavach(ids, confidence="high"):
    return {"kind": "asset", "type": "life_insurance", "institution": "KAVACH LIFE INS", "identifier_hint": None,
            "reason": "Looks like a monthly premium.", "evidence_transaction_ids": ids, "confidence": confidence}


def txn_ids(refs, needle):
    return [r.id for r in refs if needle in r.description.upper()]


def test_inferred_asset_is_probable_with_real_evidence():
    case, _, _ = statement_case()
    sync_documents(case, TODAY)
    refs = collect_transactions(case)
    ids = txn_ids(refs, "KAVACH")
    assert len(ids) == 3  # Jun, Jul, Aug across both pages

    run = apply_proposals(case, proposals(kavach(ids)), refs, "test-model", today=TODAY)

    item = case.get_item(run.added[0])
    assert item.status == "probable" and item.origin == "inference"
    assert [e.amount for e in item.evidence] == [3150, 3150, 3150]
    assert {e.direction for e in item.evidence} == {"debit"}
    assert item.next_expected_debit == "2026-11-07"


def test_proposal_with_invented_evidence_is_discarded():
    case, _, _ = statement_case()
    refs = collect_transactions(case)
    run = apply_proposals(case, proposals(kavach(["T999", "T1000"])), refs, "m", today=TODAY)
    assert run.added == [] and len(run.discarded) == 1
    assert all(a.status != "probable" for a in case.assets)


def test_single_transaction_cannot_be_high_confidence():
    case, _, _ = statement_case()
    refs = collect_transactions(case)
    run = apply_proposals(case, proposals(kavach(txn_ids(refs, "KAVACH")[:1], "high")), refs, "m", today=TODAY)
    assert case.get_item(run.added[0]).confidence == "medium"


def test_inferred_loan_merges_into_documented_loan():
    case, _, _ = statement_case()
    add_doc(case, loan_sms())
    sync_documents(case, TODAY)
    refs = collect_transactions(case)
    emi_ids = txn_ids(refs, "EMI DR-GRIHA SETU")
    run = apply_proposals(case, proposals({
        "kind": "liability", "type": "home_loan", "institution": "GRIHA SETU HFL", "identifier_hint": "HL0098817782",
        "reason": "EMI debits.", "evidence_transaction_ids": emi_ids, "confidence": "high"}), refs, "m", today=TODAY)

    assert run.added == [] and len(run.merged) == 1
    assert len(case.liabilities) == 1
    loan = case.liabilities[0]
    assert loan.status == "confirmed"
    assert loan.next_expected_debit == "2026-11-05"


def test_same_hidden_asset_proposed_twice_is_one_item():
    case, _, _ = statement_case()
    refs = collect_transactions(case)
    ids = txn_ids(refs, "KAVACH")
    apply_proposals(case, proposals(kavach(ids[:2]), kavach(ids[2:])), refs, "m", today=TODAY)
    apply_proposals(case, proposals(kavach(ids)), refs, "m", today=TODAY)  # second run
    kavach_items = [a for a in case.assets if a.type == "life_insurance"]
    assert len(kavach_items) == 1 and len(kavach_items[0].evidence) == 3


def test_document_upload_promotes_probable_to_confirmed():
    case, _, _ = statement_case()
    refs = collect_transactions(case)
    apply_proposals(case, proposals(kavach(txn_ids(refs, "KAVACH"))), refs, "m", today=TODAY)
    add_doc(case, extracted(institution="Kavach Life Insurance Co. Ltd", document_type="insurance_policy",
                            identifier="55K91027", amounts=[{"label": "Sum Assured", "value": 1000000}]))
    sync_documents(case, TODAY)
    policy = next(a for a in case.assets if a.type == "life_insurance")
    assert policy.status == "confirmed" and policy.amount == 1000000
    assert len(policy.source_document_ids) == 1 and len(policy.evidence) == 4


def test_user_rejection_survives_rebuild_and_reinference():
    case, _, _ = statement_case()
    refs = collect_transactions(case)
    run = apply_proposals(case, proposals(kavach(txn_ids(refs, "KAVACH"))), refs, "m", today=TODAY)
    item = case.get_item(run.added[0])
    item.status, item.decided_by_user = "rejected", True

    sync_documents(case, TODAY)
    apply_proposals(case, proposals(kavach(txn_ids(refs, "KAVACH"))), refs, "m", today=TODAY)
    assert case.get_item(item.id).status == "rejected"
    assert len([a for a in case.assets if a.type == "life_insurance"]) == 1


def test_prompt_lists_known_items_masked():
    case, _, _ = statement_case()
    add_doc(case, premium_receipt())
    sync_documents(case, TODAY)
    prompt = build_prompt(case, collect_transactions(case))
    assert "XXXX1931" in prompt and "life_insurance" in prompt
    assert "T1 | 2026-06-01 | credit | 78400.00" in prompt


def test_epf_amount_is_employee_plus_employer_never_pension():
    case = new_case()
    add_doc(case, recorded("09_epf_passbook"))
    sync_documents(case, TODAY)
    assert case.assets[0].amount == 1337450.0

    case = new_case()
    add_doc(case, extracted(document_type="epf_passbook", identifier="100987654321", amounts=[
        {"label": "Employee Closing Balance", "value": 1007730}, {"label": "Employer Closing Balance", "value": 329720},
        {"label": "Pension Closing Balance", "value": 170550}]))
    sync_documents(case, TODAY)
    assert case.assets[0].amount == 1337450.0


def test_mandate_reference_is_not_kept_as_policy_number():
    case, _, _ = statement_case()
    refs = collect_transactions(case)
    proposal = {**kavach(txn_ids(refs, "KAVACH")), "identifier_hint": "SNB70002315"}
    run = apply_proposals(case, proposals(proposal), refs, "m", today=TODAY)
    item = case.get_item(run.added[0])
    assert item.identifier_masked is None and item.identifier_check == "unchecked"


def test_inferred_identifier_is_never_marked_valid():
    case, _, _ = statement_case()
    refs = collect_transactions(case)
    proposal = {**kavach(txn_ids(refs, "KAVACH")), "identifier_hint": "784512000"}
    run = apply_proposals(case, proposals(proposal), refs, "m", today=TODAY)
    assert case.get_item(run.added[0]).identifier_check == "unchecked"


def test_demat_proposal_always_carries_the_dividend_credits():
    case, _, _ = statement_case()
    refs = collect_transactions(case)
    only_dp_charge = txn_ids(refs, "DP AMC")
    run = apply_proposals(case, proposals({
        "kind": "asset", "type": "demat_account", "institution": "ANAND STOCKBROKING", "identifier_hint": None,
        "reason": "DP charges.", "evidence_transaction_ids": only_dp_charge, "confidence": "medium"}), refs, "m",
        today=TODAY)
    demat = case.get_item(run.added[0])
    assert sorted(e.amount for e in demat.evidence if e.direction == "credit") == [350, 612, 1840]


def test_as_of_ignores_future_dates():
    from tools.asset_map import as_of_date
    case = new_case()
    doc = add_doc(case, recorded("04_fd_advice"))
    assert as_of_date(doc, TODAY) == "2026-03-15"  # deposit date, not the 2027 maturity date


def test_accounts_at_different_banks_sharing_last_four_digits_stay_separate():
    case = new_case()
    add_doc(case, extracted(institution="Sahyadri National Bank", document_type="bank_statement",
                            identifier="30218847201931"))
    add_doc(case, extracted(institution="Konkan Gramin Bank", document_type="passbook", identifier="99887766551931"))
    sync_documents(case)
    assert sorted(a.institution for a in case.assets) == ["Konkan Gramin Bank", "Sahyadri National Bank"]


def test_masked_page_two_still_merges_with_page_one_of_the_same_bank():
    case = new_case()
    add_doc(case, extracted(institution="Sahyadri National Bank", document_type="bank_statement",
                            identifier="30218847201931"))
    add_doc(case, extracted(institution="SAHYADRI NATIONAL BANK", document_type="bank_statement",
                            identifier="XXXXXXXXXX1931"))
    sync_documents(case)
    assert len(case.assets) == 1


def test_lic_policy_and_lic_premium_clue_are_one_item():
    case = new_case()
    add_doc(case, extracted(institution="Life Insurance Corporation of India", document_type="premium_receipt"))
    sync_documents(case)
    from tools.asset_map import Candidate, upsert

    item, created = upsert(case, Candidate(type="life_insurance", institution="LIC", identifier=None,
                                           confidence="medium", origin="inference"))
    assert not created and len(case.assets) == 1


def test_forgetting_one_page_keeps_the_account_the_other_page_proves():
    from tools.asset_map import forget_document

    case, p1, p2 = statement_case()
    sync_documents(case, TODAY)
    assert forget_document(case, p2.id, TODAY) == []
    [account] = case.assets
    assert account.source_document_ids == [p1.id]
    assert all(e.document_id != p2.id for e in account.evidence)
    assert account.amount is not None and account.amount_as_of <= TODAY.isoformat()  # re-read from page 1


def test_forgetting_the_only_document_removes_its_item_and_unbacked_inferences():
    from tools.asset_map import forget_document

    case = new_case()
    statement = add_doc(case, extracted(
        institution="Sahyadri National Bank", document_type="bank_statement", identifier="30218847201931",
        transactions=[{"date": "2026-08-07", "description": "NACH DR-KAVACH LIFE INS-PREM", "amount": 3150,
                       "direction": "debit"}]))
    sync_documents(case, TODAY)
    refs = collect_transactions(case)
    run = apply_proposals(case, InferenceResult.model_validate({"items": [
        {"kind": "asset", "type": "life_insurance", "institution": "Kavach Life", "identifier_hint": None,
         "reason": "Monthly premiums.", "evidence_transaction_ids": ["T1"], "confidence": "medium"}]}),
        refs, "test", TODAY)
    account_id, [policy_id] = case.assets[0].id, run.added

    assert sorted(forget_document(case, statement.id, TODAY)) == sorted([account_id, policy_id])
    assert case.assets == [] and case.documents == []


def test_family_decisions_survive_forgetting_a_document():
    from tools.asset_map import forget_document

    case, p1, p2 = statement_case()
    sync_documents(case, TODAY)
    case.assets[0].decided_by_user = True
    forget_document(case, p1.id, TODAY)
    forget_document(case, p2.id, TODAY)
    assert len(case.assets) == 1
