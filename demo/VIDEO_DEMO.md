# Recording the Virasat demo

Everything here is synthetic: a fictional family, fictional banks, watermarked documents. Documents are uploaded
like a real family's and **read live by Gemini** (only cases created with the hidden `POST /api/demo` replay saved
readings).

Part A is a full walkthrough that touches every feature; record it in pieces. Part B cuts it to the 3-minute video
the hackathon asks for. Part C maps every feature to the step that shows it.

---

## 0. Before you record

1. **Billed settings in `afterlife/.env`:** `REASONING_MODEL=gemini-4-argon`, `GEMINI_RPM=0`, `GEMINI_DAILY_LIMIT=300`,
   and your key. One full run costs roughly ₹50–60 in Gemini calls.
2. **Fresh build and server** (VS Code terminal, in `afterlife/`):
   ```bash
   (cd frontend && npm run build)
   .venv/bin/uvicorn app.main:app --app-dir backend --port 8000
   ```
3. **Do one complete dry run of Part A first.** It is the first full live run of the agent on `gemini-4-argon`; watch the
   terminal for errors and note how long "Find what might be missing" takes. Then **Privacy → Delete my data** and
   start clean for the real recording.
4. **Browser:** a fresh Chrome profile or window, 1440×900 or larger, zoom 100%, bookmarks bar and extensions hidden.
   Allow the microphone for `localhost` when asked (step 6). Keep a second **incognito** window ready for step 17.
5. **Files**, in two folders:
   - `afterlife/demo/docs/`: the family's 9 documents (01 to 09).
   - `afterlife/demo/video/`: `10_bank_statement_sep.png` (money keeps leaving after the death) and
     `11_passbook_other_person.png` (someone else's passbook).
   - `afterlife/demo/samples/`: `reply_kavach_life.png` (a genuine reply) and `message_fake_bank.png` (a scam).
6. **Password for the locked PDF** (`08_mf_statement.pdf`): `SURE1503`.
7. Make regenerating the two video documents possible any time: `.venv/bin/python scripts/make_video_docs.py`.

### The family (keep this in front of you)

| | |
|---|---|
| Deceased | **Suresh Narayan Rao**, died **2 September 2026**, Pune |
| You | **Arjun**, his son |
| Nominee | Kamala Suresh Rao, his wife |
| Hidden on purpose | a **Kavach Life** policy (only monthly premium debits) and a **demat account at Anand Stockbroking** (dividends, DP charges); no document for either |
| Planted name differences | EPF passbook says **"S N RAO"**; co-op passbook nominee says **"Smt. Kamla Rao"** |
| After the death | 5 payments, **₹61,600**, left his Sahyadri account in September (EMI, premium, SIP, an ATM withdrawal at another branch, a wallet top-up) |

---

## Part A: full walkthrough (every feature)

Times are rough; "Find what might be missing" depends on Gemini.

### 1. Start a case (start screen)
- Show the start screen: the lotus logo, **"Virasat: Find and claim what your loved one left behind"**, the dawn
  backdrop, "We are sorry for your loss."
- Fill the form:
  - **Their name:** `Suresh Narayan Rao`
  - **Date they passed away:** `02/09/2026`
  - **You are their:** `Son`
  - **Language for letters and steps:** `English`
- Click **Begin**.
- *Say:* "A family starts with nothing more than a name and a date. No login, no bank access."

### 2. Documents: what to upload
- On **Documents**, the guide **"What can I upload, and where do I find it?"** is open. Scroll through it.
- *Say:* "Families rarely have neat paperwork. Virasat tells them what helps and where it usually is, and never to
  log in with the deceased's passwords."

### 3. Upload everything at once
- Click **Choose photos or PDFs**, select **all 9 files in `demo/docs/`** and **both files in `demo/video/`** (11 files).
- Each file appears at once with a thumbnail and **Uploading…**; click any thumbnail to open it full size.
- Each file uploads separately and Gemini reads two at a time: **Reading…** then **Read: bank statement, Sahyadri
  National Bank**, and so on (about 40–60 seconds).
- Watch for three things:
  - `08_mf_statement.pdf` shows **Locked with a password**.
  - `11_passbook_other_person.png` shows, in red: **"This document is in the name of Mr. Ramesh Kumar Sharma, not
    Suresh Narayan Rao. Please check it is the right document, or remove it."**
  - Every other file shows **Read: …** with its type and bank.
- *Say:* "Gemini is reading phone photos, a passbook, SMS and UPI screenshots into a strict structure that code
  checks."

### 4. A paper in someone else's name → Remove
- On `11_passbook_other_person.png`, click **Remove** → **Yes, remove**.
- *Say:* "If a paper isn't his (a mix-up, or someone trying it on), Virasat flags it, and the family removes it."

### 5. Unlock the password-protected statement
- On `08_mf_statement.pdf`, type **`SURE1503`** and click **Open file**. It is read like the others.
- *Say:* "Statements arrive locked. The family types the password once; Virasat opens the file and never stores the
  password."

### 6. Tell us what you remember (voice memory + secret redaction)
Still on **Documents**, below the list, the card **"Tell us what you remember"**. It comes *before* the search on
purpose: the agent uses what the family remembers as hints while it reads the transactions.
- Click **Record a memory**, allow the microphone, and say (Hindi, or the English after it):
  > "मुझे याद है, वो हर महीने कवच लाइफ़ इंश्योरेंस का प्रीमियम भरते थे। और जब अर्जुन पैदा हुआ था, तब उन्होंने पोस्ट
  > ऑफ़िस में एक पीपीएफ़ खाता खुलवाया था। उनका ATM पिन 4412 था।"
  >
  > *(English: "He paid a Kavach Life insurance premium every month. When Arjun was born he opened a PPF account at the
  > post office. His ATM PIN was 4412.")*
- Click **Stop and send**. Under **What we heard**:
  - **Kavach Life**: *backed by 3 payments in the statements*.
  - **PPF at the Post Office**: *no payment found in the papers yet, so it is marked "not very sure"*.
  - **What you said** shows the PIN as **[removed]**.
- *Say:* "A grieving mother can just talk, in Hindi. Code matches what she remembers against the statements, the agent
  will use it as a hint, and the PIN she mentioned is never stored."
- (Fallback if the mic fails: type the English text under **Or type it** and click **Add this memory**.)

### 7. Find what might be missing (the ADK agent)
- Click **Find what might be missing**. The panel **"Virasat is looking through everything…"** fills in live:
  read documents, look for hidden assets, check names, look up procedures, prepare questions, build the plan, draft
  letters.
- Optional: open **✦ What Virasat did** (top right) to show the full activity log, in English and Hindi.
- *Say:* "This is a Gemini agent on Google's Agent Development Kit. It decides the order of work; every step it takes
  is logged, and code checks everything it proposes."

### 8. What we found (the key moment)
The app moves to **What we found**. Show, top to bottom:
1. **Red alert: "Money left an account after Suresh Narayan Rao passed away":** **5 payments, ₹61,600 in total**:
   EMI on 5 Sep, Kavach premium on 7 Sep, **₹20,000 ATM withdrawal at Hadapsar on 9 Sep**, SIP on 10 Sep, **₹15,000
   wallet top-up on 11 Sep**. "It is first in your plan."
   *Say:* "He died on the 2nd. Someone withdrew twenty thousand rupees a week later. That goes straight to the top."
2. **Confirmed so far**: the total, the coloured bar and the legend (savings, FD, life insurance, mutual fund, EPF).
3. **"We may have found 3 more things"**: marigold cards: **Kavach Life** (life insurance), **Anand Stockbroking**
   (demat) and the **PPF** from the memory. Open Kavach: its ledger rows are the three premium debits (click a file
   name to open that statement), and its reason
   ends "Your family remembers it too." The PPF has only the family's words, so it is "not very sure".
   *Say:* "Nobody had papers for these. Gemini spotted the pattern, using what the family remembered as a hint; code
   checked that every transaction it cited is real. They stay 'probable' until confirmed, and never count in the
   total."
4. **Confirmed** cards with pastel icons; **Loans and dues** (the home loan, next EMI date).

### 9. Confirm or reject a probable item
- On **Anand Stockbroking**, click **Yes, this is right**. It moves to Confirmed and the total updates.
- (Leave **Kavach Life** probable; step 12 confirms it from the insurer's letter.)
- Later, **Remember something else? Tell us** (below the cards) adds another memory; it is checked at once.

### 10. Questions
- Click **Next: a few questions**. The agent picks 2 to 4 real gaps, so the set can vary; answer whichever appear:
  - Does the family know about the **Kavach Life** policy? → **Not sure** (keep it probable for step 12)
  - Any other "did he have…" question → **Yes** or **Not sure**
  - Death certificate → **Applied for it**
  - **Nominee for the EPF account** (not on the document) → type `Kamala Suresh Rao` → **Save**
  - Your name for letters → `Arjun Suresh Rao` → **Save**
  - Postal address → `Flat 7, Shanti Kunj Society, Kothrud, Pune 411038` → **Save**
- *Say:* "Only real gaps become questions, and every answer flows into the letters."

### 11. Plan
Click **See your plan**. Show:
- **"Stay safe from scams"** notice at the top.
- **0 of N steps done** progress bar.
- **Step 1: Sahyadri National Bank**: *Time-sensitive*: "₹61,600 left this account in 5 payments after Suresh Narayan
  Rao passed away…", and why it comes first.
- **Griha Setu Housing Finance**: next EMI date, *Time-sensitive*.
- A probable institution (Kavach Life): *Needs checking*, first step "Ask Kavach Life to confirm…".
- Open **All steps and documents** on one step: steps and documents come from the knowledge base, with the source.
- **Check names across the papers** (lower on the page): **Names are written differently on some papers**:
  *Their name*: "Suresh Narayan Rao" vs **"S N RAO"** on the EPF passbook; *The nominee's name*: "Kamala Suresh Rao"
  vs **"Smt. Kamla Rao"** on the co-op passbook, with **What you can do** from the knowledge base.
  (If it shows **Check the names**, click it.)
- *Say:* "The plan is ordered by urgency, written in plain steps, and it warns them about name mismatches before a
  bank does."

### 12. A genuine reply from the insurer, and the letter rewritten from it
- **Before:** click **Letters** and open the **Kavach Life** letter. It is an **enquiry**: "Request to confirm any life
  insurance policy…", quoting the three premium debits and asking for the policy number and nominee. (If there is no
  Kavach letter, use **Make a letter for…** → Kavach Life.) Don't edit it: edited letters are never rewritten.
- Back on **Plan**, on the **Kavach Life** step, click **Got a reply from them? Upload it** and choose
  `demo/samples/reply_kavach_life.png`.
- You'll see: **Reply from Kavach Life…**: **"They confirmed it exists. It is now in your confirmed list."**, **Please
  respond by** a date (worked out in code), **What they ask for (0 of 5 ready)** with ticks, and **Your covering letter
  is ready**. Tick one requirement.
- **After:** click **Letters** again. The same Kavach letter is now a **claim letter**: "Intimation of the death… policy
  no. XXXX0894", nominee **Kamala S. Rao**, and the documents to enclose, all taken from their reply. Next to it is the
  new **Reply to KAVACH LIFE INSURANCE CO. LTD.** quoting their reference (masked) and listing the 5 things they asked for.
- *Say:* "The hidden policy we found from three debits is now confirmed in writing by the insurer. The enquiry we sent
  has become a claim with their policy number and nominee, and the reply lists exactly what they asked for."

### 13. A scam message
- On the **Sahyadri National Bank** step, upload `demo/samples/message_fake_bank.png`.
- You'll see: **"This looks like a scam. Please don't reply to it."** with the reasons (a fee to release the money,
  an OTP, a personal UPI id) and **Their words**. Nothing in the case changes.
- *Say:* "Fraudsters target grieving families with 'release fees'. Virasat checks every reply for that, in code, and
  refuses to act on it."

### 14. Letters
- Click **Letters** (or **See letters**). Show:
  - a **Claim letter** (full account number from the family's own document, the nominee, the documents to enclose),
  - the **Enquiry** letter for a probable item, such as the PPF from the memory ("please confirm whether any … exists"),
  - the line asking the institution to **verify the sender against its nominee records**,
  - **Make a letter for…** → choose another item to draft one.
- Edit a word, **Save changes**, then **Download PDF** and open it.

### 15. Hindi
- Click **हिन्दी** (top right). Every screen switches; the plan and unedited letters are redrafted in Hindi.
- Open **Letters → Download PDF** again: a Hindi PDF with correct Devanagari.
- Click **Read aloud** (सुनें) on any screen for a few seconds. Switch back with **English**.

### 16. Family board
- Click **Family board**: steps in To do / In progress (Kavach Life moved there after its reply) / Done.
- Click **Start** on one step and **Mark done** on another; go back to **Plan** to show the progress bar move.

### 17. Privacy and security
- In the **incognito** window, paste the case address (`http://localhost:8000/#/case/…`). It lands on the start screen:
  **"That case can't be opened here. For privacy, a case opens only on the device where it was started."**
  *Say:* "A forwarded link opens nothing. Each case is locked to the browser that started it."
- Back in the main window, click **Privacy** (footer): what happens to documents, **Using a shared computer? → Leave
  this case**, and **Delete my data**. Show **Delete my data → Yes, delete everything** only at the very end.

---

## Part B: the 3-minute video

Record Part A in pieces (pre-run steps 3–7 so you are not filming waits), then edit to this. Speak over it, or add
captions.

| Time | Show | Say (about 25 words per 10 seconds) |
|---|---|---|
| 0:00–0:15 | Start screen, then the form being filled | "When someone dies in India, families often don't know what accounts or policies existed. Close to ₹1 lakh crore sits unclaimed. Virasat helps them find it." |
| 0:15–0:40 | Step 3 sped up: 11 files uploading, **Read …** appearing; the **someone else's name** flag; **Remove**; the **locked PDF** opened with the password | "A family uploads whatever they have: photos, passbooks, SMS. Gemini reads them live. A paper in someone else's name is flagged; a locked statement is opened, the password never stored." |
| 0:40–1:00 | Step 6: recording the Hindi memory on **Documents**; **What we heard**, PIN shown as **[removed]** | "His wife can simply speak, in Hindi. What she remembers is matched against the statements and handed to the agent as a hint, and the PIN she mentioned is never stored." |
| 1:00–1:15 | Step 7: **Find what might be missing**, the live activity panel (sped up) | "Then a Gemini agent, built on Google's Agent Development Kit, works through the case: every step logged, everything it proposes checked by code." |
| 1:15–1:45 | Step 8: the **red after-death alert**, the total and bar, the **marigold "probably" cards** with their ledger rows (Kavach: "Your family remembers it too.") | "Money is still leaving his account after he died, including a twenty-thousand rupee ATM withdrawal. And things nobody had papers for: a life policy and a demat account, found in the transactions, with her memory as a hint. Never presented as fact." |
| 1:45–2:10 | Step 11: the plan (step 1 Sahyadri with ₹61,600, the scam notice), the **name check** | "The plan is ordered by urgency and warns about name mismatches (S N Rao on one paper, Suresh Narayan Rao on another) before a bank delays the claim." |
| 2:10–2:35 | Steps 12–13: the **Kavach reply** confirming the policy and the checklist; the enquiry letter **rewritten as a claim**; the **scam message** warning | "When the insurer replies, the policy is confirmed and the enquiry becomes a claim letter with their policy number and nominee. When a fraudster asks for a release fee, Virasat refuses to act." |
| 2:35–2:50 | Step 14–15: a letter, **Download PDF**, switch to **हिन्दी** and the Hindi PDF | "Letters are drafted, editable, and in English or Hindi." |
| 2:50–3:00 | Step 17: the incognito "can't be opened here", then the logo | "Each case is locked to the family's device. Virasat: find and claim what your loved one left behind." |

Tips: zoom in (or crop) on the alert, the ledger rows, the **[removed]** PIN and the scam warning: those are the
moments judges remember. Keep the cursor still while talking.

---

## Part C: feature coverage

| Feature | Where it shows |
|---|---|
| Bilingual start, form, lotus branding | Step 1 |
| Upload guide (what to upload, where to find it, no passwords) | Step 2 |
| One-file-per-request upload, live Gemini extraction (photos, passbook, SMS, UPI, PDF) | Step 3 |
| File previews: thumbnails while uploading and in the list, replies on the plan, source documents on What we found | Steps 3, 8, 12–13 |
| Name flag on a document in someone else's name; Remove a document | Steps 3–4 |
| Password-protected PDF unlock (password never stored) | Step 5 |
| ADK agent, live activity log in English and Hindi | Step 7 |
| Money-after-death alert | Step 8 |
| Asset mix total, bar and legend; confirmed and loan cards | Step 8 |
| Hidden-asset inference with cited transaction evidence; probable never counted | Step 8 |
| Confirm / not applicable | Step 9 |
| Voice memory in Hindi before the search: hints for the agent, matched to statements, re-checked at each analysis; secret redaction | Step 6 |
| Gap-driven questions; answers flow into letters | Step 10 |
| Urgency-ordered plan, knowledge-base steps with sources, progress bar, scam notice | Step 11 |
| Name check across papers (Gemini + verified in code) with guidance | Step 11 |
| Institution reply: confirmation, requirements checklist, respond-by date, covering letter | Step 12 |
| Letter rewritten from the institution's reply (enquiry → claim with their policy no. and nominee; edited letters kept) | Step 12 |
| Scam message detection: nothing changes | Step 13 |
| Claim, enquiry and covering letters; verify-the-sender line; edit; PDF | Step 14 |
| Hindi throughout, Hindi PDF, read aloud | Step 15 |
| Family board | Step 16 |
| Case opens only on its own device; leave on a shared computer; delete my data | Step 17 |

## If something goes wrong

- **A file shows "Couldn't read this":** click **Try again**. Persistent? Check the terminal for the Gemini error.
- **"Find what might be missing" stays greyed out:** a file is still reading or still locked (step 5).
- **"today's limit":** the daily ceiling was reached; raise `GEMINI_DAILY_LIMIT` in `.env` and restart the server.
- **Microphone blocked:** allow it in Chrome's address bar for `localhost`, or type the memory instead.
- **Results differ slightly from this script:** documents are read live, so wording can vary. The planted facts
  (two hidden assets, ₹61,600 after the death, the two name differences) come from the documents themselves.
