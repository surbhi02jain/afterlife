"""Two extra synthetic documents for recording the demo video, in the same style as the demo family's.

  10_bank_statement_sep.png     September for the same Sahyadri account: money keeps leaving after the death on
                                2 Sep (EMI, premium, SIP, an ATM withdrawal at another branch, a wallet top-up),
                                which drives the money-after-death alert.
  11_passbook_other_person.png  A passbook in someone else's name (Ramesh Kumar Sharma), which drives the
                                "this document is in someone else's name" flag and the Remove button.

They live in demo/video/, not demo/docs/: they have no recorded Gemini reading and are read live when uploaded.
Usage:  .venv/bin/python scripts/make_video_docs.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

from make_demo_docs import (ADDRESS, BANK, PERSON, ROOT, SAVINGS_AC, WIFE, inr, logo, statement_with_balances, table,
                            text, watermark)

OUT_DIR = ROOT / "demo" / "video"

# (date, narration, ref, debit, credit). The death is on 02-09-2026: everything debited after it is flagged.
SEPTEMBER_ROWS = [
    ("01-09-2026", "NEFT CR-KALPATARU ENGG WORKS-SALARY SEP26", "N244601390", 0, 78400.00),
    ("02-09-2026", "UPI/SANJEEVANI MEDICALS/medicines", "624502238871", 4120.00, 0),
    ("05-09-2026", "EMI DR-GRIHA SETU HFL-HL0098817782", "EMI0509", 18450.00, 0),
    ("07-09-2026", "NACH DR-KAVACH LIFE INS-PREM-UMRN SNB70002315", "NACH0709", 3150.00, 0),
    ("09-09-2026", "ATM WDL-SNB ATM HADAPSAR PUNE", "ATM48815", 20000.00, 0),
    ("10-09-2026", "ACH DR-NAVODAYA MF-SIP-1048832", "ACH1009", 5000.00, 0),
    ("11-09-2026", "UPI/QUICKPAY WALLET/load money", "625411907326", 15000.00, 0),
    ("15-09-2026", "SB INTEREST CREDIT", "INT1509", 0, 412.00),
]


def september_statement() -> Image.Image:
    img = Image.new("RGB", (1240, 1300), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 30, 1240, 150], fill="#0b4f6c")
    logo(d, (110, 90), "SNB", "#f2a541", r=40)
    text(d, (170, 62), BANK.upper(), size=34, kind="bold", fill="white")
    text(d, (170, 106), "Kothrud Branch, Pune  |  IFSC SNBX0000412 (fictional)", size=18, fill="#dbe9f0")
    text(d, (60, 185), "STATEMENT OF ACCOUNT", size=28, kind="bold", fill="#0b4f6c")
    text(d, (1180, 190), "Page 1 of 1", size=18, fill="#555", anchor="ra")

    opening = statement_with_balances()[-1][5]  # carries on from the August page
    period = ("01-09-2026", "15-09-2026")
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

    balance, body = opening, []
    for dt, nar, ref, dr, cr in SEPTEMBER_ROWS:
        balance = round(balance - dr + cr, 2)
        body.append([dt, nar, ref, inr(dr) if dr else "", inr(cr) if cr else "", inr(balance)])
    cols = [("Date", 60, 125, "l"), ("Narration", 185, 520, "l"), ("Ref No", 705, 145, "l"),
            ("Withdrawal", 850, 115, "r"), ("Deposit", 965, 105, "r"), ("Balance", 1070, 120, "r")]
    y = table(d, y, cols, body, size=16, row_h=36, right=1190)
    y += 24
    text(d, (60, y), f"Total Withdrawals: Rs. {inr(sum(r[3] for r in SEPTEMBER_ROWS))}    "
                     f"Total Deposits: Rs. {inr(sum(r[4] for r in SEPTEMBER_ROWS))}", size=19)
    text(d, (60, y + 34), f"Closing Balance as on {period[1]}:  Rs. {inr(balance)}", size=20, kind="bold")
    text(d, (60, 1240), "This is a computer generated statement and does not require a signature.  "
         "Sahyadri National Bank is a FICTIONAL bank.", size=15, fill="#666")
    return img


def other_person_passbook() -> Image.Image:
    img = Image.new("RGB", (1600, 1000), "#efe6cc")
    d = ImageDraw.Draw(img)
    d.rectangle([40, 50, 1560, 960], outline="#8a7a55", width=3)
    text(d, (800, 95), "DECCAN GRAMIN CO-OPERATIVE BANK LTD.", size=36, kind="serif", fill="#5a2d0c", anchor="ma")
    text(d, (800, 145), "Hadapsar Branch, Pune  -  SAVINGS BANK PASS BOOK (fictional bank)", size=22, kind="serif",
         fill="#5a2d0c", anchor="ma")
    info = [("A/c No.", "SB/006213"), ("Name", "Mr. Ramesh Kumar Sharma"), ("Nominee", "Smt. Sunita Sharma"),
            ("Joint holder", "-")]
    for i, (k, v) in enumerate(info):
        text(d, (90 + (i % 2) * 740, 200 + (i // 2) * 40), f"{k}: {v}", size=24, kind="mono", fill="#222")
    rows = [
        ("04-01-2026", "B/F", "", "", "", "12,880.00"),
        ("20-02-2026", "BY CASH", "", "", "3,000.00", "15,880.00"),
        ("31-03-2026", "BY INT", "", "", "108.00", "15,988.00"),
        ("06-06-2026", "TO CASH SELF", "", "2,500.00", "", "13,488.00"),
        ("30-06-2026", "BY INT", "", "", "94.00", "13,582.00"),
    ]
    cols = [("Date", 70, 190, "l"), ("Particulars", 260, 400, "l"), ("Chq No", 660, 160, "l"),
            ("Withdrawals", 820, 230, "r"), ("Deposits", 1050, 230, "r"), ("Balance", 1280, 250, "r")]
    for _, x, _, _ in cols:
        d.line([x, 290, x, 900], fill="#b8a77d", width=1)
    table(d, 300, cols, [list(r) for r in rows], row_h=56, size=24, header_fill="#e6d8b0", zebra="#efe6cc",
          left=70, right=1530)
    return img.rotate(0.8, expand=False, fillcolor="#c9c2b0")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, img in (("10_bank_statement_sep.png", september_statement()),
                      ("11_passbook_other_person.png", other_person_passbook())):
        watermark(img).save(OUT_DIR / name, optimize=True)
        print("wrote", (OUT_DIR / name).relative_to(ROOT))


if __name__ == "__main__":
    main()
