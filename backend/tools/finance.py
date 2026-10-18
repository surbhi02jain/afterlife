"""Deterministic finance helpers. The model never does these: masking, identifier checks, totals, dates."""

import re
from calendar import monthrange
from datetime import date

from app.models import Asset, Case, IdentifierCheck, Liability

# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------

def normalize_identifier(identifier: str | None) -> str:
    """Uppercase alphanumerics only: 'SB/004417' -> 'SB004417', 'XXXX 7782' -> 'XXXX7782'."""
    return re.sub(r"[^A-Za-z0-9]", "", identifier or "").upper()


def mask_identifier(identifier: str | None) -> str | None:
    """Keep the last 4 characters only. Short or already-masked values are masked too."""
    clean = normalize_identifier(identifier)
    if not clean:
        return None
    visible = clean[-4:]
    if len(clean) <= 4 or set(visible) <= {"X"}:
        return "XXXX"
    return "XXXX" + visible


def identifier_digits(identifier: str | None) -> str:
    """Digits only, ignoring masking characters. Used to compare identifiers across documents."""
    return re.sub(r"\D", "", identifier or "")


def is_masked(identifier: str | None) -> bool:
    return bool(re.search(r"[X*]{2,}", (identifier or "").upper()))


# Format rules per type. Deliberately loose: they catch obvious misreads, not every institution's scheme.
_FORMATS: dict[str, list[str]] = {
    "savings_account": [r"^\d{9,18}$", r"^[A-Z]{1,4}\d{4,16}$"],      # bank a/c, or co-op style SB004417
    "fixed_deposit": [r"^\d{9,18}$", r"^[A-Z]{1,4}\d{4,16}$"],
    "life_insurance": [r"^\d{8,12}$", r"^[A-Z0-9]{6,20}$"],
    "mutual_fund": [r"^\d{5,12}$"],                                    # folio, after dropping the '/57' suffix
    "demat_account": [r"^\d{16}$", r"^IN\d{14}$"],                     # 16-digit or IN + 14
    "epf": [r"^\d{12}$", r"^[A-Z]{5}\d{17}$"],                         # UAN, or member id
    "ppf": [r"^\d{6,18}$"],
    "home_loan": [r"^[A-Z]{0,4}\d{6,18}$"],
    "personal_loan": [r"^[A-Z]{0,4}\d{6,18}$"],
    "vehicle_loan": [r"^[A-Z]{0,4}\d{6,18}$"],
    "credit_card": [r"^\d{16}$"],
    "other_loan": [r"^[A-Z0-9]{6,20}$"],
}


def check_identifier(item_type: str, identifier: str | None) -> IdentifierCheck:
    if not identifier or is_masked(identifier):
        return "unchecked"
    raw = identifier.strip().upper()
    if item_type == "mutual_fund":
        raw = raw.split("/")[0]
    clean = normalize_identifier(raw)
    patterns = _FORMATS.get(item_type)
    if not patterns:
        return "unchecked"
    return "valid" if any(re.match(p, clean) for p in patterns) else "invalid"


# ---------------------------------------------------------------------------
# Institutions
# ---------------------------------------------------------------------------

_GENERIC_WORDS = {
    "the", "of", "and", "ltd", "limited", "pvt", "private", "co", "company", "corp", "corporation", "india",
    "bank", "national", "cooperative", "co-operative", "operative", "gramin", "sahakari",
    "life", "insurance", "ins", "assurance", "general",
    "mutual", "fund", "mf", "amc", "asset", "management",
    "housing", "finance", "financial", "hfl", "services", "securities", "stockbroking", "broking",
    "nach", "ach", "dr", "cr", "upi", "neft", "imps", "emi", "prem", "premium", "sip",
}
# Words that can sit next to an acronym without changing which company it is ("LIC of India", "SBI Ltd").
# Sector words are NOT here: "SBI Life Insurance" and "LIC Housing Finance" are different companies.
_NAME_FILLER = {"the", "of", "and", "india", "ltd", "limited", "pvt", "private", "co", "company"}


def institution_tokens(name: str | None) -> set[str]:
    words = re.findall(r"[a-z]+", (name or "").lower())
    return {w for w in words if w not in _GENERIC_WORDS and len(w) > 1}


def _is_acronym_of(short: str | None, full: str | None) -> bool:
    """'LIC' / 'LIC of India' for 'Life Insurance Corporation of India', 'SBI' for 'State Bank of India'."""
    core = [w for w in re.findall(r"[a-z]+", (short or "").lower()) if w not in _NAME_FILLER]
    if len(core) != 1 or not 3 <= len(core[0]) <= 6:
        return False
    full_words = [w for w in re.findall(r"[a-z]+", (full or "").lower()) if w not in _NAME_FILLER - {"india"}]
    initials = "".join(w[0] for w in full_words)
    return len(full_words) >= 3 and initials in (core[0], core[0] + "i")  # trailing "i" = "...of India"


def same_institution(a: str | None, b: str | None) -> bool:
    if _is_acronym_of(a, b) or _is_acronym_of(b, a):
        return True
    ta, tb = institution_tokens(a), institution_tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / min(len(ta), len(tb)) >= 0.5


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

_TITLES = {"mr", "mrs", "ms", "miss", "shri", "sri", "smt", "kumari", "km", "dr", "late", "lt", "md", "mohd"}


def _name_words(name: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]+", name.lower()) if w not in _TITLES]


def could_be_same_person(holder: str | None, deceased: str) -> bool:
    """Whether a document's holder can be the deceased. A flag for the family to check, never a block, so it is
    lenient: 'S. N. Rao', 'Mr. Suresh Narayan Rao' (family typed 'Suresh Rao'), 'N. Suresh' and joint holders pass.
    It catches a clearly different person: another given name ('Ramesh Rao') or another surname ('Suresh Kumar').
    Known limit: a relative whose name includes the deceased's ('Kamala Suresh Rao') passes."""
    target = _name_words(deceased)
    if not holder or not target:
        return True
    comparable = False
    for person in re.split(r"\s*(?:&|/|,|\band\b|\bjointly with\b)\s*", holder, flags=re.I):
        words = _name_words(person)
        if not words:
            continue  # e.g. a Devanagari name: nothing to compare
        comparable = True
        full = [w for w in words if len(w) > 1]
        given = target[0] in full or (len(words[0]) == 1 and target[0].startswith(words[0]))
        surname = not full or full[-1] in target or target[-1] in full
        if given and surname:
            return True
    return not comparable


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

def parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year, month = d.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(d.day, monthrange(year, month)[1]))


def recurring_cadence(dates: list[date]) -> int | None:
    """Return 1 (monthly) or 12 (yearly) if the dates repeat at that cadence, else None. Needs 2+ dates."""
    ds = sorted(set(dates))
    if len(ds) < 2:
        return None
    gaps = [(b - a).days for a, b in zip(ds, ds[1:])]
    if all(25 <= g <= 35 for g in gaps):
        return 1
    if all(350 <= g <= 380 for g in gaps):
        return 12
    return None


def next_expected(dates: list[date], today: date) -> date | None:
    """Next date a recurring debit will hit, strictly after today, from its past occurrences."""
    cadence = recurring_cadence(dates)
    if cadence is None:
        return None
    nxt = max(dates)
    while nxt <= today:
        nxt = add_months(nxt, cadence)
    return nxt


# ---------------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------------

def _sum(items: list[Asset] | list[Liability], status: str) -> tuple[float, int, int]:
    chosen = [i for i in items if i.status == status]
    known = [i.amount for i in chosen if i.amount is not None]
    return round(sum(known), 2), len(chosen), len(chosen) - len(known)


def totals(case: Case) -> dict:
    """Probable items are never added to the confirmed total; rejected items are ignored."""
    assets_total, assets_count, assets_unknown = _sum(case.assets, "confirmed")
    debts_total, debts_count, debts_unknown = _sum(case.liabilities, "confirmed")
    return {
        "confirmed_assets_total": assets_total,
        "confirmed_assets_count": assets_count,
        "confirmed_assets_without_amount": assets_unknown,
        "confirmed_liabilities_total": debts_total,
        "confirmed_liabilities_count": debts_count,
        "confirmed_liabilities_without_amount": debts_unknown,
        "probable_assets_count": sum(1 for a in case.assets if a.status == "probable"),
        "probable_liabilities_count": sum(1 for l in case.liabilities if l.status == "probable"),
        "net_confirmed": round(assets_total - debts_total, 2),
        "currency": "INR",
    }
