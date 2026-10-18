# Virasat demo family (100% synthetic)

**Deceased:** Mr. Suresh Narayan Rao (fictional), date of death 2026-09-02. Family: Kamala Suresh Rao (wife), Arjun Suresh Rao (son).
Every institution name is fictional and every image is watermarked "SYNTHETIC DEMO DOCUMENT".

The mutual fund statement is locked like a real one: the family types its password (`SURE1503`: first 4
letters of the name + day and month of birth, 15 March) on the Documents screen before it can be read.

Regenerate with `.venv/bin/python scripts/make_demo_docs.py`.

## Uploaded documents (`docs/`)

| File | What it is | Asset it confirms |
|---|---|---|
| 01_bank_statement_p1.png | Sahyadri National Bank savings statement, Jun-Jul 2026 | Savings a/c ...1931 |
| 02_bank_statement_p2.png | Same account, Aug 2026 | (same account, dedup test) |
| 03_coop_passbook.png | Deccan Gramin Co-op Bank passbook photo | Savings a/c SB/004417 |
| 04_fd_advice.png | Fixed deposit advice | FD ...6712, Rs 2,00,000 |
| 05_upi_history.png | PayDost UPI app screenshot, Aug 2026 | (same txns as statement, dedup test) |
| 06_premium_receipt.png | Jeevan Raksha life policy premium receipt | Policy ...2093, SA Rs 5,00,000 |
| 07_loan_emi_sms.png | Griha Setu home loan EMI SMS | LIABILITY: home loan ...7782 |
| 08_mf_statement.pdf | Navodaya Mutual Fund statement, **password-protected PDF** (password `SURE1503`) | Folio 1048832/57 |
| 09_epf_passbook.png | EPF member passbook | UAN ...4321 (no nominee shown, a gap) |

## PLANTED: names written differently (for the name check)
- `09_epf_passbook.png` gives the member's name as **"S N RAO"**; every other paper says Suresh Narayan Rao.
- `03_coop_passbook.png` gives the nominee as **"Smt. Kamla Rao"**; the other papers say Kamala Suresh Rao.

## Samples for the demo buttons (`samples/`)
| File | What it is | What should happen |
|---|---|---|
| memory_hi.wav | Kamala's voice memo in Hindi (macOS synthetic voice): monthly Kavach Life premiums, and a PPF account at the post office | Kavach backed by 3 statement debits (high); PPF added as probable, *not very sure*, no transactions |
| reply_kavach_life.png | Kavach Life confirms policy KL...0894 (sum assured Rs 15,00,000) and asks for 5 documents within 30 days | The probable Kavach policy becomes confirmed; checklist; respond by 5 Nov 2026; covering letter |
| message_fake_bank.png | A fake "Sahyadri National Bank Claims Cell" message asking for a Rs 2,950 fee to a UPI id and an OTP | Flagged as a scam; nothing in the case changes |

## PLANTED: assets with NO document, inferable only from transactions

### 1. Demat / broking account at "Anand Stockbroking"
Dividends can only arrive if shares are held in a demat account; a DP AMC charge names the depository participant.

| Date | Narration | Amount |
|---|---|---|
| 18-06-2026 | `ACH CR-NAVBHARAT POWER LTD-FINAL DIVIDEND FY26` | Cr 1,840.00 |
| 22-07-2026 | `ACH CR-SURYODAY CEMENTS LTD-INTERIM DIVIDEND` | Cr 612.00 |
| 12-08-2026 | `ANAND STOCKBROKING-DP AMC CHGS FY27` | Dr 590.00 |
| 14-08-2026 | `UPI/ANAND STOCKBROKING/add funds` | Dr 10,000.00 |
| 26-08-2026 | `ACH CR-MALABAR SPICES LTD-INTERIM DIV` | Cr 350.00 |

Also in `05_upi_history.png`: "Paid to Anand Stockbroking Rs 10,000.00" on 14 Aug 2026 (same txn as the statement).

### 2. Second life insurance policy with "Kavach Life Insurance"
A fixed monthly NACH premium debit to an insurer with no matching policy document.

| Date | Narration | Amount |
|---|---|---|
| 07-06-2026 | `NACH DR-KAVACH LIFE INS-PREM-UMRN SNB70002315` | Dr 3,150.00 |
| 07-07-2026 | `NACH DR-KAVACH LIFE INS-PREM-UMRN SNB70002315` | Dr 3,150.00 |
| 07-08-2026 | `NACH DR-KAVACH LIFE INS-PREM-UMRN SNB70002315` | Dr 3,150.00 |

## Inferable but ALSO uploaded (should be deduplicated, not reported as new)
- EMI debits `EMI DR-GRIHA SETU HFL-HL0098817782` -> home loan, already in `07_loan_emi_sms.png`
- SIP debits `ACH DR-NAVODAYA MF-SIP-1048832` -> mutual fund, already in `08_mf_statement.pdf`
- `JEEVAN RAKSHA LIC-PREM-POL 784512093` -> policy already in `06_premium_receipt.png`
- Salary credits from Kalpataru Engg Works -> EPF, already in `09_epf_passbook.png`

## Expected outcome
The asset map should show both planted items as **Probable** (never Confirmed), each citing the rows above
as evidence, and should NOT create duplicate probable entries for the loan, mutual fund, Jeevan Raksha policy or EPF.
