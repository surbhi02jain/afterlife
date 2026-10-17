"""Fixed English/Hindi strings and formatting used by deterministic outputs (plan, letters, activity log)."""

from datetime import date

TYPE_LABEL = {
    "savings_account": ("savings account", "बचत खाता"),
    "fixed_deposit": ("fixed deposit", "फ़िक्स्ड डिपॉज़िट"),
    "life_insurance": ("life insurance policy", "जीवन बीमा पॉलिसी"),
    "mutual_fund": ("mutual fund folio", "म्यूचुअल फ़ंड फ़ोलियो"),
    "demat_account": ("demat account", "डीमैट खाता"),
    "epf": ("EPF account", "EPF खाता"),
    "ppf": ("PPF account", "PPF खाता"),
    "other_asset": ("asset", "संपत्ति"),
    "home_loan": ("home loan", "होम लोन"),
    "personal_loan": ("personal loan", "पर्सनल लोन"),
    "vehicle_loan": ("vehicle loan", "वाहन लोन"),
    "credit_card": ("credit card", "क्रेडिट कार्ड"),
    "other_loan": ("loan", "लोन"),
    "general": ("first steps", "पहले कदम"),
}

MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर",
             "दिसंबर"]


def label(item_type: str, language: str) -> str:
    en, hi = TYPE_LABEL.get(item_type, (item_type.replace("_", " "), item_type.replace("_", " ")))
    return hi if language == "hi" else en


def pick(language: str, en: str, hi: str) -> str:
    return hi if language == "hi" else en


def inr(value: float | None) -> str:
    """Indian digit grouping with a rupee sign: 232198.6 -> '₹2,32,198.60'."""
    if value is None:
        return "-"
    whole, frac = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        head, tail, groups = whole[:-3], whole[-3:], []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        whole = ",".join(([head] if head else []) + groups + [tail])
    return f"{'-' if value < 0 else ''}₹{whole}.{frac}"


def nice_date(d: date | str | None, language: str = "en") -> str:
    if d is None:
        return "-"
    if isinstance(d, str):
        d = date.fromisoformat(d)
    if language == "hi":
        return f"{d.day} {MONTHS_HI[d.month - 1]} {d.year}"
    return d.strftime("%-d %b %Y")
