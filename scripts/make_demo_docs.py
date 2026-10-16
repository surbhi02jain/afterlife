"""Generate clearly fake, realistic-looking demo documents for the Saath demo family.

Everything here is synthetic: fictional person, fictional institutions, made-up numbers, and every image
carries a "SYNTHETIC DEMO DOCUMENT" watermark.

Two assets are PLANTED: they have no document of their own, but they can be inferred from transactions:
  1. A demat account at "Anand Stockbroking" (dividend credits + DP AMC charge + UPI 'add funds').
  2. A second life policy with "Kavach Life Insurance" (monthly NACH premium debit).

Usage:  .venv/bin/python scripts/make_demo_docs.py   -> writes demo/docs/*.png and demo/README.md
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "demo" / "docs"

# ---------------------------------------------------------------------------
# The synthetic family
# ---------------------------------------------------------------------------
PERSON = "SURESH NARAYAN RAO"
PERSON_TITLE = "Mr. Suresh Narayan Rao"
WIFE = "Kamala Suresh Rao"
SON = "Arjun Suresh Rao"
ADDRESS = ["Flat 7, Shanti Kunj Society", "Kothrud, Pune 411038 (SAMPLE ADDRESS)"]
DATE_OF_DEATH = "2026-09-02"

BANK = "Sahyadri National Bank"
SAVINGS_AC = "30218847201931"

# ---------------------------------------------------------------------------
# Fonts and drawing helpers
# ---------------------------------------------------------------------------
FONT_CANDIDATES = {
    "regular": ["/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "bold": ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "mono": ["/System/Library/Fonts/Supplemental/Courier New.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"],
    "serif": ["/System/Library/Fonts/Supplemental/Georgia.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"],
}
_font_cache: dict = {}


def font(kind: str, size: int):
    key = (kind, size)
    if key not in _font_cache:
        for path in FONT_CANDIDATES[kind]:
            if Path(path).exists():
                _font_cache[key] = ImageFont.truetype(path, size)
                break
        else:
            _font_cache[key] = ImageFont.load_default(size=size)
    return _font_cache[key]


def inr(value: float) -> str:
    """Indian digit grouping: 1234567.5 -> 12,34,567.50"""
    whole, frac = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return ("-" if value < 0 else "") + whole + "." + frac


def text(draw, xy, s, size=20, kind="regular", fill="#1f2328", anchor="la"):
    draw.text(xy, s, font=font(kind, size), fill=fill, anchor=anchor)


def watermark(img: Image.Image) -> Image.Image:
    """Diagonal 'SAMPLE' plus a top banner so nobody can mistake these for real documents."""
    img = img.convert("RGBA")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w, h = img.size
    size = max(40, w // 11)
    label = "SYNTHETIC SAMPLE"
    stamp_w = int(font("bold", size).getlength(label)) + 40
    stamp = Image.new("RGBA", (stamp_w, size + 30), (0, 0, 0, 0))
    ImageDraw.Draw(stamp).text((stamp_w // 2, 10), label, font=font("bold", size), fill=(200, 30, 30, 38), anchor="ma")
    stamp = stamp.rotate(28, expand=True)
    layer.paste(stamp, ((w - stamp.width) // 2, (h - stamp.height) // 2), stamp)
    d.rectangle([0, 0, w, 30], fill=(200, 30, 30, 230))
    d.text((w // 2, 15), "SYNTHETIC DEMO DOCUMENT - NOT REAL - fictional person and institution (Saath hackathon demo)",
           font=font("bold", 16), fill="white", anchor="mm")
    return Image.alpha_composite(img, layer).convert("RGB")


def table(draw, top, columns, rows, row_h=34, size=19, header_fill="#e8eef5", zebra="#f7f9fb", left=60, right=None):
    """columns: list of (title, x, width, align). rows: list of lists of strings. Returns y after table."""
    right = right or max(x + w for _, x, w, _ in columns)
    draw.rectangle([left, top, right, top + row_h], fill=header_fill)
    for title, x, w, align in columns:
        tx = x + w - 8 if align == "r" else x + 8
        text(draw, (tx, top + row_h // 2), title, size=size - 1, kind="bold", anchor="rm" if align == "r" else "lm")
    y = top + row_h
    for i, row in enumerate(rows):
        if i % 2:
            draw.rectangle([left, y, right, y + row_h], fill=zebra)
        for (title, x, w, align), cell in zip(columns, row):
            tx = x + w - 8 if align == "r" else x + 8
            text(draw, (tx, y + row_h // 2), cell, size=size, anchor="rm" if align == "r" else "lm")
        y += row_h
    draw.rectangle([left, top, right, y], outline="#9aa7b4", width=1)
    return y


def logo(draw, xy, initials, color, r=34):
    x, y = xy
    draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
    text(draw, (x, y), initials, size=int(r * 0.8), kind="bold", fill="white", anchor="mm")


def save(img: Image.Image, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    watermark(img).save(OUT_DIR / name, optimize=True)
    print("wrote", (OUT_DIR / name).relative_to(ROOT))


# ---------------------------------------------------------------------------
# Bank statement (2 pages). Planted evidence lives here.
# ---------------------------------------------------------------------------
# (date dd-mm-yyyy, narration, ref, debit, credit)
STATEMENT_ROWS = [
    ("01-06-2026", "NEFT CR-KALPATARU ENGG WORKS-SALARY JUN26", "N152601887", 0, 78400.00),
    ("02-06-2026", "UPI/SHARMA GENERAL STORE/groceries", "615338210442", 2315.00, 0),
    ("05-06-2026", "EMI DR-GRIHA SETU HFL-HL0098817782", "EMI0605", 18450.00, 0),
    ("07-06-2026", "NACH DR-KAVACH LIFE INS-PREM-UMRN SNB70002315", "NACH0706", 3150.00, 0),
    ("10-06-2026", "ACH DR-NAVODAYA MF-SIP-1048832", "ACH1006", 5000.00, 0),
    ("12-06-2026", "ATM WDL-SNB ATM KOTHRUD PUNE", "ATM44120", 10000.00, 0),
    ("15-06-2026", "UPI/PUNE POWER DISTRIBUTION/electricity", "616620930118", 2140.00, 0),
    ("18-06-2026", "ACH CR-NAVBHARAT POWER LTD-FINAL DIVIDEND FY26", "DIV1806", 0, 1840.00),
    ("21-06-2026", "UPI/SANJEEVANI MEDICALS/medicines", "617245501926", 1280.00, 0),
    ("26-06-2026", "UPI/CR/ARJUN S RAO", "617789043310", 0, 5000.00),
    ("30-06-2026", "SB INTEREST CREDIT", "INT3006", 0, 1126.00),
    ("01-07-2026", "NEFT CR-KALPATARU ENGG WORKS-SALARY JUL26", "N182601554", 0, 78400.00),
    ("03-07-2026", "UPI/SHARMA GENERAL STORE/groceries", "618401177263", 2870.00, 0),
    ("05-07-2026", "EMI DR-GRIHA SETU HFL-HL0098817782", "EMI0507", 18450.00, 0),
    ("07-07-2026", "NACH DR-KAVACH LIFE INS-PREM-UMRN SNB70002315", "NACH0707", 3150.00, 0),
    ("10-07-2026", "ACH DR-NAVODAYA MF-SIP-1048832", "ACH1007", 5000.00, 0),
    ("14-07-2026", "JEEVAN RAKSHA LIC-PREM-POL 784512093", "JR140726", 24380.00, 0),
    ("16-07-2026", "UPI/PUNE POWER DISTRIBUTION/electricity", "619712045581", 2460.00, 0),
    ("19-07-2026", "ATM WDL-SNB ATM KOTHRUD PUNE", "ATM45981", 8000.00, 0),
    ("22-07-2026", "ACH CR-SURYODAY CEMENTS LTD-INTERIM DIVIDEND", "DIV2207", 0, 612.00),
    ("28-07-2026", "UPI/DR MEHTA CLINIC/consultation", "620919336702", 1500.00, 0),
    # ---- page 2 (August) ----
    ("01-08-2026", "NEFT CR-KALPATARU ENGG WORKS-SALARY AUG26", "N213601202", 0, 78400.00),
    ("04-08-2026", "UPI/SHARMA GENERAL STORE/groceries", "621604418827", 2140.00, 0),
    ("05-08-2026", "EMI DR-GRIHA SETU HFL-HL0098817782", "EMI0508", 18450.00, 0),
    ("07-08-2026", "NACH DR-KAVACH LIFE INS-PREM-UMRN SNB70002315", "NACH0708", 3150.00, 0),
    ("10-08-2026", "ACH DR-NAVODAYA MF-SIP-1048832", "ACH1008", 5000.00, 0),
    ("12-08-2026", "ANAND STOCKBROKING-DP AMC CHGS FY27", "DPAMC1208", 590.00, 0),
    ("14-08-2026", "UPI/ANAND STOCKBROKING/add funds", "622680117734", 10000.00, 0),
    ("17-08-2026", "UPI/PUNE POWER DISTRIBUTION/electricity", "622913850046", 2310.00, 0),
    ("20-08-2026", "UPI/SANJEEVANI MEDICALS/medicines", "623207761195", 3460.00, 0),
    ("23-08-2026", "UPI/CR/ARJUN S RAO", "623589902471", 0, 5000.00),
    ("26-08-2026", "ACH CR-MALABAR SPICES LTD-INTERIM DIV", "DIV2608", 0, 350.00),
    ("29-08-2026", "ATM WDL-SNB ATM KOTHRUD PUNE", "ATM47702", 6000.00, 0),
]
OPENING_BALANCE = 142315.60
PAGE_SPLIT = 21  # rows on page 1


def statement_with_balances():
    balance, rows = OPENING_BALANCE, []
    for date, narration, ref, dr, cr in STATEMENT_ROWS:
        balance = round(balance - dr + cr, 2)
        rows.append((date, narration, ref, dr, cr, balance))
    return rows


def bank_statement_page(page: int) -> Image.Image:
    img = Image.new("RGB", (1240, 1754), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 30, 1240, 150], fill="#0b4f6c")
    logo(d, (110, 90), "SNB", "#f2a541", r=40)
    text(d, (170, 62), BANK.upper(), size=34, kind="bold", fill="white")
    text(d, (170, 106), "Kothrud Branch, Pune  |  IFSC SNBX0000412 (fictional)", size=18, fill="#dbe9f0")

    rows = statement_with_balances()
    if page == 1:
        chunk, opening, period = rows[:PAGE_SPLIT], OPENING_BALANCE, ("01-06-2026", "31-07-2026")
    else:
        chunk, opening, period = rows[PAGE_SPLIT:], rows[PAGE_SPLIT - 1][5], ("01-08-2026", "31-08-2026")

    text(d, (60, 185), "STATEMENT OF ACCOUNT", size=28, kind="bold", fill="#0b4f6c")
    text(d, (1180, 190), f"Page {page} of 2", size=18, fill="#555", anchor="ra")
    y = 240
    left_info = [("Account Holder", PERSON), ("Address", ADDRESS[0]), ("", ADDRESS[1]), ("Nominee", f"Registered ({WIFE})")]
    right_info = [("Account No", SAVINGS_AC), ("Account Type", "Savings - Regular"),
                  ("Statement Period", f"{period[0]} to {period[1]}"), ("Currency", "INR")]
    for i, ((lk, lv), (rk, rv)) in enumerate(zip(left_info, right_info)):
        text(d, (60, y + i * 32), lk, size=19, kind="bold")
        text(d, (250, y + i * 32), lv, size=19)
        text(d, (680, y + i * 32), rk, size=19, kind="bold")
        text(d, (880, y + i * 32), rv, size=19)
    y += 4 * 32 + 30
    text(d, (60, y), f"Opening Balance as on {period[0]}:  Rs. {inr(opening)}", size=20, kind="bold")
    y += 44

    cols = [("Date", 60, 125, "l"), ("Narration", 185, 520, "l"), ("Ref No", 705, 145, "l"),
            ("Withdrawal", 850, 115, "r"), ("Deposit", 965, 105, "r"), ("Balance", 1070, 120, "r")]
    body = [[dt, nar, ref, inr(dr) if dr else "", inr(cr) if cr else "", inr(bal)] for dt, nar, ref, dr, cr, bal in chunk]
    y = table(d, y, cols, body, size=16, row_h=36, right=1190)

    total_dr = sum(r[3] for r in chunk)
    total_cr = sum(r[4] for r in chunk)
    y += 24
    text(d, (60, y), f"Total Withdrawals: Rs. {inr(total_dr)}    Total Deposits: Rs. {inr(total_cr)}", size=19)
    text(d, (60, y + 34), f"Closing Balance as on {period[1]}:  Rs. {inr(chunk[-1][5])}", size=20, kind="bold")
    text(d, (60, 1690), "This is a computer generated statement and does not require a signature.  "
         "Sahyadri National Bank is a FICTIONAL bank.", size=15, fill="#666")
    return img


# ---------------------------------------------------------------------------
# Co-operative bank passbook (photo of a passbook page)
# ---------------------------------------------------------------------------
def passbook() -> Image.Image:
    img = Image.new("RGB", (1600, 1100), "#f3ead2")
    d = ImageDraw.Draw(img)
    d.rectangle([40, 50, 1560, 1060], outline="#8a7a55", width=3)
    text(d, (800, 95), "DECCAN GRAMIN CO-OPERATIVE BANK LTD.", size=36, kind="serif", fill="#5a2d0c", anchor="ma")
    text(d, (800, 145), "Paud Road Branch, Pune  -  SAVINGS BANK PASS BOOK (fictional bank)", size=22, kind="serif", fill="#5a2d0c", anchor="ma")
    info = [("A/c No.", "SB/004417"), ("Name", PERSON_TITLE), ("Nominee", WIFE), ("Joint holder", "-")]
    for i, (k, v) in enumerate(info):
        text(d, (90 + (i % 2) * 740, 200 + (i // 2) * 40), f"{k}: {v}", size=24, kind="mono", fill="#222")
    rows = [
        ("02-01-2026", "B/F", "", "", "", "31,240.00"),
        ("18-01-2026", "BY CASH", "", "", "5,000.00", "36,240.00"),
        ("31-03-2026", "BY INT", "", "", "271.00", "36,511.00"),
        ("11-05-2026", "TO CASH SELF", "", "3,000.00", "", "33,511.00"),
        ("30-06-2026", "BY INT", "", "", "254.00", "33,765.00"),
        ("14-07-2026", "BY CASH", "", "", "5,000.00", "38,765.00"),
    ]
    cols = [("Date", 70, 190, "l"), ("Particulars", 260, 400, "l"), ("Chq No", 660, 160, "l"),
            ("Withdrawals", 820, 230, "r"), ("Deposits", 1050, 230, "r"), ("Balance", 1280, 250, "r")]
    for title, x, w, align in cols:
        d.line([x, 290, x, 1000], fill="#b8a77d", width=1)
    table(d, 300, cols, [list(r) for r in rows], row_h=56, size=24, header_fill="#e6d8b0", zebra="#f3ead2", left=70, right=1530)
    for y in range(300 + 56 * 7, 1000, 56):
        d.line([70, y, 1530, y], fill="#d6c79f")
    return img.rotate(-1.2, expand=False, fillcolor="#c9c2b0")


# ---------------------------------------------------------------------------
# Fixed deposit advice
# ---------------------------------------------------------------------------
def fd_advice() -> Image.Image:
    img = Image.new("RGB", (1240, 900), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 30, 1240, 130], fill="#0b4f6c")
    logo(d, (100, 80), "SNB", "#f2a541", r=34)
    text(d, (150, 58), BANK.upper(), size=30, kind="bold", fill="white")
    text(d, (150, 96), "Kothrud Branch, Pune", size=18, fill="#dbe9f0")
    text(d, (620, 175), "FIXED DEPOSIT ADVICE", size=30, kind="bold", fill="#0b4f6c", anchor="ma")
    principal, rate = 200000.00, 7.10
    maturity_value = round(principal * (1 + rate / 400) ** 4, 2)
    fields = [
        ("Depositor", PERSON), ("FD Account No", "30219000456712"), ("Linked SB Account", SAVINGS_AC),
        ("Principal Amount", f"Rs. {inr(principal)}"), ("Rate of Interest", f"{rate:.2f}% p.a. (compounded quarterly)"),
        ("Date of Deposit", "15-03-2026"), ("Period", "12 months"), ("Maturity Date", "15-03-2027"),
        ("Maturity Value", f"Rs. {inr(maturity_value)}"), ("Nominee", f"{WIFE} (Wife)"),
        ("Instructions on Maturity", "Credit principal + interest to SB account"),
    ]
    y = 240
    for k, v in fields:
        text(d, (120, y), k, size=22, kind="bold")
        text(d, (470, y), v, size=22)
        d.line([120, y + 36, 1120, y + 36], fill="#e3e8ee")
        y += 50
    text(d, (120, 840), "Authorised Signatory (sample)    -    Sahyadri National Bank is a FICTIONAL bank.", size=16, fill="#666")
    return img


# ---------------------------------------------------------------------------
# Phone screenshots (UPI history, loan SMS)
# ---------------------------------------------------------------------------
def phone_frame(title: str, color: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (1080, 2100), "#ffffff")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 30, 1080, 110], fill="#f4f4f4")
    text(d, (50, 70), "9:41", size=34, kind="bold", anchor="lm")
    text(d, (1030, 70), "4G  87%", size=30, anchor="rm")
    d.rectangle([0, 110, 1080, 260], fill=color)
    text(d, (60, 185), "<", size=56, kind="bold", fill="white", anchor="lm")
    text(d, (130, 185), title, size=46, kind="bold", fill="white", anchor="lm")
    return img, d


def upi_history() -> Image.Image:
    img, d = phone_frame("PayDost  -  History", "#3b2a8c")
    text(d, (60, 310), f"Linked account: {BANK} XX{SAVINGS_AC[-4:]}", size=30, fill="#444")
    text(d, (60, 360), "UPI ID: sureshrao.sample@paydost (demo)", size=30, fill="#444")
    text(d, (60, 440), "AUGUST 2026", size=30, kind="bold", fill="#3b2a8c")
    entries = [
        ("Received from", "Arjun S Rao", "23 Aug 2026, 7:12 PM", 5000.00, True),
        ("Paid to", "Sanjeevani Medicals", "20 Aug 2026, 11:05 AM", 3460.00, False),
        ("Paid to", "Pune Power Distribution", "17 Aug 2026, 9:40 AM", 2310.00, False),
        ("Paid to", "Anand Stockbroking", "14 Aug 2026, 10:02 AM", 10000.00, False),
        ("Paid to", "Sharma General Store", "04 Aug 2026, 6:48 PM", 2140.00, False),
    ]
    y = 500
    for verb, who, when, amount, incoming in entries:
        d.rounded_rectangle([40, y, 1040, y + 230], radius=28, fill="#f5f3fb")
        d.ellipse([75, y + 55, 185, y + 165], fill="#d9d2f5")
        text(d, (130, y + 110), who[0], size=48, kind="bold", fill="#3b2a8c", anchor="mm")
        text(d, (220, y + 50), verb, size=28, fill="#666")
        text(d, (220, y + 92), who, size=36, kind="bold")
        text(d, (220, y + 150), when, size=28, fill="#666")
        sign = "+ " if incoming else "- "
        text(d, (1000, y + 92), f"{sign}Rs {inr(amount)}", size=36, kind="bold",
             fill="#1a7f37" if incoming else "#1f2328", anchor="ra")
        text(d, (1000, y + 150), "Completed", size=26, fill="#1a7f37", anchor="ra")
        y += 260
    text(d, (540, 1880), "PayDost is a FICTIONAL payments app", size=26, fill="#888", anchor="ma")
    return img


def loan_sms() -> Image.Image:
    img, d = phone_frame("GS-GRIHSF", "#2e7d32")
    text(d, (540, 300), "Text Message", size=28, fill="#777", anchor="ma")
    messages = [
        ("05 Aug 2026, 9:14 AM",
         "Dear Customer, EMI of Rs.18,450.00 for your Home Loan A/c XXXXXXX7782 has been received "
         "on 05-08-2026. Principal outstanding: Rs.11,62,904.00. Remaining tenure: 94 months. "
         "-Griha Setu Housing Finance"),
        ("01 Sep 2026, 10:30 AM",
         "Reminder: EMI of Rs.18,450 for Home Loan A/c XXXXXXX7782 is due on 05-09-2026. Please keep "
         "sufficient balance in A/c XX1931. -Griha Setu Housing Finance"),
        ("05 Sep 2026, 9:16 AM",
         "Dear Customer, EMI of Rs.18,450.00 for Home Loan A/c XXXXXXX7782 due on 05-09-2026 is "
         "received. For loan insurance or closure queries call 1800-000-0000 (demo). -Griha Setu HFL"),
    ]
    y = 370
    for when, body in messages:
        lines = wrap(body, font("regular", 34), 820)
        h = 60 + len(lines) * 46
        text(d, (540, y), when, size=26, fill="#777", anchor="ma")
        y += 50
        d.rounded_rectangle([50, y, 930, y + h], radius=34, fill="#e9eef0")
        for i, line in enumerate(lines):
            text(d, (90, y + 30 + i * 46), line, size=34)
        y += h + 50
    text(d, (540, 1880), "Griha Setu Housing Finance is FICTIONAL", size=26, fill="#888", anchor="ma")
    return img


def wrap(s: str, f, max_width: int) -> list[str]:
    words, lines, line = s.split(), [], ""
    for w in words:
        candidate = f"{line} {w}".strip()
        if f.getlength(candidate) <= max_width:
            line = candidate
        else:
            lines.append(line)
            line = w
    return lines + [line]


# ---------------------------------------------------------------------------
# Insurance premium receipt (the policy that IS uploaded)
# ---------------------------------------------------------------------------
def premium_receipt() -> Image.Image:
    img = Image.new("RGB", (1240, 1100), "#fffdf6")
    d = ImageDraw.Draw(img)
    d.rectangle([30, 50, 1210, 1070], outline="#1d3f8f", width=4)
    logo(d, (120, 140), "JR", "#1d3f8f", r=46)
    text(d, (190, 105), "JEEVAN RAKSHA LIFE INSURANCE CORPORATION", size=32, kind="bold", fill="#1d3f8f")
    text(d, (190, 152), "Branch Office: Deccan Gymkhana, Pune  (fictional insurer)", size=20, fill="#333")
    text(d, (620, 225), "PREMIUM RECEIPT", size=32, kind="bold", fill="#1d3f8f", anchor="ma")
    fields = [
        ("Receipt No", "JR/PNE/2026/0718842"), ("Receipt Date", "14/07/2026"),
        ("Policy No", "784512093"), ("Name of Life Assured", PERSON_TITLE),
        ("Plan / Term", "Jeevan Suraksha Endowment / 25 yrs"), ("Date of Commencement", "15/07/2014"),
        ("Sum Assured", f"Rs. {inr(500000)}"), ("Mode of Payment", "Yearly"),
        ("Premium Due Date", "15/07/2026"), ("Premium Amount Paid", f"Rs. {inr(24380)}"),
        ("Paid Through", f"Auto-debit, {BANK} A/c XX{SAVINGS_AC[-4:]}"),
        ("Next Due Date", "15/07/2027"), ("Nominee", f"{WIFE} (Wife)"),
    ]
    y = 300
    for k, v in fields:
        text(d, (90, y), k, size=22, kind="bold")
        text(d, (480, y), ": " + v, size=22)
        y += 52
    text(d, (90, 1010), "This receipt is valid subject to realisation. Jeevan Raksha is a FICTIONAL insurer.", size=17, fill="#666")
    return img


# ---------------------------------------------------------------------------
# Mutual fund statement
# ---------------------------------------------------------------------------
def mf_statement() -> Image.Image:
    img = Image.new("RGB", (1240, 1754), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 30, 1240, 150], fill="#7b2d26")
    logo(d, (105, 90), "NMF", "#f6c344", r=40)
    text(d, (165, 60), "NAVODAYA MUTUAL FUND", size=34, kind="bold", fill="white")
    text(d, (165, 106), "Account Statement  |  fictional asset management company", size=18, fill="#f3dcd9")
    text(d, (60, 190), "ACCOUNT STATEMENT: 01-Jun-2026 to 31-Aug-2026", size=24, kind="bold", fill="#7b2d26")
    info = [("Folio No", "1048832/57"), ("Investor", PERSON), ("PAN", "AXXXX9876R (masked)"),
            ("Mode of Holding", "Single"), ("Nominee", f"{WIFE} - 100%"), ("Bank Mandate", f"{BANK} XX{SAVINGS_AC[-4:]}")]
    for i, (k, v) in enumerate(info):
        x, y = 60 + (i % 2) * 600, 240 + (i // 2) * 36
        text(d, (x, y), k, size=19, kind="bold")
        text(d, (x + 190, y), v, size=19)

    cols = [("Date", 60, 150, "l"), ("Transaction", 210, 420, "l"), ("Amount (Rs)", 630, 170, "r"),
            ("NAV", 800, 120, "r"), ("Units", 920, 130, "r"), ("Unit Balance", 1050, 140, "r")]

    y = 380
    text(d, (60, y), "Navodaya Flexi Cap Fund - Direct Plan - Growth   (SIP Rs 5,000 on 10th of every month)", size=20, kind="bold")
    units = 1213.004
    rows = [["01-06-2026", "Opening Unit Balance", "", "", "", f"{units:,.3f}"]]
    for date, nav in [("10-06-2026", 69.12), ("10-07-2026", 70.48), ("10-08-2026", 67.95)]:
        bought = round(5000 / nav, 3)
        units = round(units + bought, 3)
        rows.append([date, "SIP Purchase - Instalment", inr(5000), f"{nav:.2f}", f"{bought:.3f}", f"{units:,.3f}"])
    y = table(d, y + 40, cols, rows, size=17, right=1190)
    flexi_value = round(units * 68.42, 2)
    text(d, (60, y + 20), f"Closing units {units:,.3f}  x  NAV 68.42 (31-Aug-2026)  =  Market value Rs. {inr(flexi_value)}", size=19)

    y += 100
    text(d, (60, y), "Navodaya ELSS Tax Saver Fund - Direct Plan - Growth", size=20, kind="bold")
    elss_units = 410.330
    y = table(d, y + 40, cols, [["01-06-2026", "Opening Unit Balance", "", "", "", f"{elss_units:,.3f}"],
                                ["31-08-2026", "No transactions during the period", "", "", "", f"{elss_units:,.3f}"]],
              size=17, right=1190)
    elss_value = round(elss_units * 102.15, 2)
    text(d, (60, y + 20), f"Closing units {elss_units:,.3f}  x  NAV 102.15 (31-Aug-2026)  =  Market value Rs. {inr(elss_value)}", size=19)

    y += 110
    d.rectangle([60, y, 1190, y + 70], fill="#fbeeed")
    text(d, (80, y + 35), f"TOTAL PORTFOLIO VALUE as on 31-Aug-2026:  Rs. {inr(flexi_value + elss_value)}", size=22, kind="bold", anchor="lm")
    text(d, (60, 1690), "Navodaya Mutual Fund is FICTIONAL. Mutual fund investments are subject to market risks.", size=15, fill="#666")
    return img


# ---------------------------------------------------------------------------
# EPF passbook
# ---------------------------------------------------------------------------
def epf_passbook() -> Image.Image:
    img = Image.new("RGB", (1240, 1400), "white")
    d = ImageDraw.Draw(img)
    text(d, (620, 70), "MEMBER PASSBOOK - EMPLOYEES' PROVIDENT FUND", size=30, kind="bold", fill="#183a6b", anchor="ma")
    text(d, (620, 115), "(SYNTHETIC SAMPLE - layout for demo only)", size=20, fill="#b42318", anchor="ma")
    info = [("Establishment ID / Name", "MHPUN0048213000 / KALPATARU ENGINEERING WORKS PVT LTD (fictional)"),
            ("Member ID / Name", f"MHPUN00482130000001127 / {PERSON}"),
            ("UAN", "100987654321"), ("Date of Birth", "12-03-1968")]
    y = 170
    for k, v in info:
        text(d, (60, y), k, size=19, kind="bold")
        text(d, (340, y), v, size=19)
        y += 36
    text(d, (60, y + 20), "Financial Year 2026-2027", size=22, kind="bold", fill="#183a6b")
    y += 70

    emp_open, er_open, pen_open = 984210, 312450, 164300
    cols = [("Wage Month", 60, 140, "l"), ("Credit Date", 200, 150, "l"), ("Particulars", 350, 300, "l"),
            ("EPF Wages", 650, 130, "r"), ("Employee", 780, 130, "r"), ("Employer", 910, 130, "r"), ("Pension", 1040, 140, "r")]
    rows = [["", "", "OB Int. Updated upto 31/03/2026", "", inr(emp_open), inr(er_open), inr(pen_open)]]
    months = [("Apr-2026", "15-05-2026"), ("May-2026", "15-06-2026"), ("Jun-2026", "15-07-2026"),
              ("Jul-2026", "14-08-2026"), ("Aug-2026", "15-09-2026")]
    for wm, cd in months:
        rows.append([wm, cd, f"Cont. For Due-Month {wm[:3].upper()}26", inr(39200), inr(4704), inr(3454), inr(1250)])
    n = len(months)
    rows.append(["", "", "Total Contributions", "", inr(4704 * n), inr(3454 * n), inr(1250 * n)])
    rows.append(["", "", "Closing Balance", "", inr(emp_open + 4704 * n), inr(er_open + 3454 * n), inr(pen_open + 1250 * n)])
    y = table(d, y, cols, rows, size=16, row_h=40, right=1180)
    total = emp_open + 4704 * n + er_open + 3454 * n
    text(d, (60, y + 30), f"Total EPF balance (Employee + Employer share): Rs. {inr(total)}", size=21, kind="bold")
    text(d, (60, y + 70), "Pension (EPS) contributions are not withdrawable as a lump sum; shown for information.", size=17, fill="#555")
    text(d, (60, 1340), "This passbook is a synthetic sample. Kalpataru Engineering Works is a FICTIONAL employer.", size=15, fill="#666")
    return img


# ---------------------------------------------------------------------------
# README of what is planted (generated from the same data, so it can't drift)
# ---------------------------------------------------------------------------
def readme() -> str:
    def rows_matching(*needles):
        return [r for r in STATEMENT_ROWS if any(n in r[1] for n in needles)]

    def fmt(rows):
        return "\n".join(f"| {dt} | `{nar}` | {'Dr ' + inr(dr) if dr else 'Cr ' + inr(cr)} |" for dt, nar, _, dr, cr in rows)

    return f"""# Saath demo family (100% synthetic)

**Deceased:** {PERSON_TITLE} (fictional), date of death {DATE_OF_DEATH}. Family: {WIFE} (wife), {SON} (son).
Every institution name is fictional and every image is watermarked "SYNTHETIC DEMO DOCUMENT".

Regenerate with `.venv/bin/python scripts/make_demo_docs.py`.

## Uploaded documents (`docs/`)

| File | What it is | Asset it confirms |
|---|---|---|
| 01_bank_statement_p1.png | {BANK} savings statement, Jun-Jul 2026 | Savings a/c ...{SAVINGS_AC[-4:]} |
| 02_bank_statement_p2.png | Same account, Aug 2026 | (same account, dedup test) |
| 03_coop_passbook.png | Deccan Gramin Co-op Bank passbook photo | Savings a/c SB/004417 |
| 04_fd_advice.png | Fixed deposit advice | FD ...6712, Rs 2,00,000 |
| 05_upi_history.png | PayDost UPI app screenshot, Aug 2026 | (same txns as statement, dedup test) |
| 06_premium_receipt.png | Jeevan Raksha life policy premium receipt | Policy ...2093, SA Rs 5,00,000 |
| 07_loan_emi_sms.png | Griha Setu home loan EMI SMS | LIABILITY: home loan ...7782 |
| 08_mf_statement.png | Navodaya Mutual Fund statement | Folio 1048832/57 |
| 09_epf_passbook.png | EPF member passbook | UAN ...4321 (no nominee shown, a gap) |

## PLANTED: assets with NO document, inferable only from transactions

### 1. Demat / broking account at "Anand Stockbroking"
Dividends can only arrive if shares are held in a demat account; a DP AMC charge names the depository participant.

| Date | Narration | Amount |
|---|---|---|
{fmt(rows_matching("DIVIDEND", "INTERIM DIV", "ANAND STOCKBROKING"))}

Also in `05_upi_history.png`: "Paid to Anand Stockbroking Rs 10,000.00" on 14 Aug 2026 (same txn as the statement).

### 2. Second life insurance policy with "Kavach Life Insurance"
A fixed monthly NACH premium debit to an insurer with no matching policy document.

| Date | Narration | Amount |
|---|---|---|
{fmt(rows_matching("KAVACH"))}

## Inferable but ALSO uploaded (should be deduplicated, not reported as new)
- EMI debits `EMI DR-GRIHA SETU HFL-HL0098817782` -> home loan, already in `07_loan_emi_sms.png`
- SIP debits `ACH DR-NAVODAYA MF-SIP-1048832` -> mutual fund, already in `08_mf_statement.png`
- `JEEVAN RAKSHA LIC-PREM-POL 784512093` -> policy already in `06_premium_receipt.png`
- Salary credits from Kalpataru Engg Works -> EPF, already in `09_epf_passbook.png`

## Expected outcome
The asset map should show both planted items as **Probable** (never Confirmed), each citing the rows above
as evidence, and should NOT create duplicate probable entries for the loan, mutual fund, Jeevan Raksha policy or EPF.
"""


def main():
    save(bank_statement_page(1), "01_bank_statement_p1.png")
    save(bank_statement_page(2), "02_bank_statement_p2.png")
    save(passbook(), "03_coop_passbook.png")
    save(fd_advice(), "04_fd_advice.png")
    save(upi_history(), "05_upi_history.png")
    save(premium_receipt(), "06_premium_receipt.png")
    save(loan_sms(), "07_loan_emi_sms.png")
    save(mf_statement(), "08_mf_statement.png")
    save(epf_passbook(), "09_epf_passbook.png")
    (ROOT / "demo" / "README.md").write_text(readme())
    print("wrote demo/README.md")


if __name__ == "__main__":
    main()
