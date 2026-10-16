from datetime import date

import pytest

from app.models import Asset, Liability
from tests.helpers import new_case
from tools.finance import (
    add_months,
    check_identifier,
    mask_identifier,
    next_expected,
    recurring_cadence,
    same_institution,
    totals,
)


@pytest.mark.parametrize("raw, masked", [
    ("30218847201931", "XXXX1931"),
    ("3021 8847 2019 31", "XXXX1931"),
    ("SB/004417", "XXXX4417"),
    ("XXXXXXX7782", "XXXX7782"),
    ("1048832/57", "XXXX3257"),
    ("1931", "XXXX"),          # too short to reveal anything
    ("XXXXXXXX", "XXXX"),
    ("", None),
    (None, None),
])
def test_mask_identifier_keeps_last_four_only(raw, masked):
    assert mask_identifier(raw) == masked


def test_masked_value_never_contains_more_than_four_original_characters():
    full = "30218847201931"
    masked = mask_identifier(full)
    assert masked.replace("X", "") == full[-4:]


@pytest.mark.parametrize("item_type, identifier, expected", [
    ("savings_account", "30218847201931", "valid"),
    ("savings_account", "SB/004417", "valid"),
    ("savings_account", "12AB", "invalid"),
    ("epf", "100987654321", "valid"),
    ("epf", "MHPUN00482130000001127", "valid"),
    ("epf", "10098765432", "invalid"),           # 11 digits: misread UAN
    ("mutual_fund", "1048832/57", "valid"),
    ("demat_account", "1208160000123456", "valid"),
    ("demat_account", "IN30012345678901", "valid"),
    ("demat_account", "12345", "invalid"),
    ("life_insurance", "784512093", "valid"),
    ("home_loan", "HL0098817782", "valid"),
    ("home_loan", "XXXXXXX7782", "unchecked"),   # masked on the SMS, can't validate
    ("other_asset", "anything", "unchecked"),
    ("savings_account", None, "unchecked"),
])
def test_check_identifier(item_type, identifier, expected):
    assert check_identifier(item_type, identifier) == expected


@pytest.mark.parametrize("a, b, same", [
    ("SAHYADRI NATIONAL BANK", "Sahyadri National Bank", True),
    ("Griha Setu HFL", "Griha Setu Housing Finance", True),
    ("JEEVAN RAKSHA LIC", "Jeevan Raksha Life Insurance Corporation", True),
    ("Kavach Life Insurance", "Jeevan Raksha Life Insurance Corporation", False),
    ("Sahyadri National Bank", "Deccan Gramin Co-operative Bank", False),
    ("Life Insurance", "Life Insurance Co", False),  # nothing distinctive to compare
])
def test_same_institution(a, b, same):
    assert same_institution(a, b) is same


def test_date_arithmetic():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 12, 5), 1) == date(2027, 1, 5)
    monthly = [date(2026, 6, 7), date(2026, 7, 7), date(2026, 8, 7)]
    assert recurring_cadence(monthly) == 1
    assert next_expected(monthly, today=date(2026, 10, 16)) == date(2026, 11, 7)
    assert recurring_cadence([date(2025, 7, 14), date(2026, 7, 14)]) == 12
    assert recurring_cadence([date(2026, 6, 7)]) is None
    assert recurring_cadence([date(2026, 6, 7), date(2026, 6, 20)]) is None


def test_totals_exclude_probable_and_rejected():
    case = new_case()
    case.assets = [
        Asset(type="savings_account", status="confirmed", amount=100000.5, confidence="high", origin="document"),
        Asset(type="mutual_fund", status="confirmed", amount=50000, confidence="high", origin="document"),
        Asset(type="fixed_deposit", status="confirmed", amount=None, confidence="high", origin="document"),
        Asset(type="demat_account", status="probable", amount=999999, confidence="high", origin="inference"),
        Asset(type="ppf", status="rejected", amount=777777, confidence="low", origin="inference"),
    ]
    case.liabilities = [
        Liability(type="home_loan", status="confirmed", amount=40000, confidence="high", origin="document"),
        Liability(type="personal_loan", status="probable", amount=5000, confidence="low", origin="inference"),
    ]
    t = totals(case)
    assert t["confirmed_assets_total"] == 150000.5
    assert t["confirmed_assets_count"] == 3
    assert t["confirmed_assets_without_amount"] == 1
    assert t["probable_assets_count"] == 1
    assert t["confirmed_liabilities_total"] == 40000
    assert t["probable_liabilities_count"] == 1
    assert t["net_confirmed"] == 110000.5
