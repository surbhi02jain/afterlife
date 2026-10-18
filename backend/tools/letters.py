"""Claim letters, pre-filled from case data. Deterministic templates in English or Hindi; editable; PDF export.

- Confirmed item  -> claim intimation letter (full number taken from the family's own document).
- Probable item   -> existence enquiry: asks the institution to CONFIRM whether anything exists, quoting the
                     payments we noticed. It never asserts that the account or policy exists.
"""

from datetime import date
from pathlib import Path

import kb
from app.models import Case, Letter
from fpdf import FPDF
from tools.i18n import inr, label, nice_date, pick

FONTS = Path(__file__).resolve().parents[1] / "fonts"


def full_identifier(case: Case, item) -> str | None:
    for doc_id in item.source_document_ids:
        doc = case.get_document(doc_id)
        if doc and doc.extraction and doc.extraction.identifier:
            return doc.extraction.identifier
    return None


def _signature(case: Case, lang: str) -> str:
    name = case.facts.claimant_name or pick(lang, "[Your full name]", "[आपका पूरा नाम]")
    address = case.facts.claimant_address or pick(lang, "[Your address]", "[आपका पता]")
    phone = pick(lang, "Phone: [your phone number]", "फ़ोन: [आपका फ़ोन नंबर]")
    return f"{name}\n{address}\n{phone}"


def _numbered(lines: list[str]) -> str:
    return "\n".join(f"{n}. {line}" for n, line in enumerate(lines, start=1))


def draft_letter(case: Case, item_id: str, today: date | None = None) -> Letter:
    item = case.get_item(item_id)
    if item is None:
        raise KeyError(item_id)
    lang, today = case.language, today or date.today()
    name, dod = case.deceased_name, nice_date(case.date_of_death, lang)
    institution = item.institution or pick(lang, "the institution", "संस्था")
    kind_label = label(item.type, lang)
    header = pick(lang, f"To,\nThe Branch Manager / Claims Department\n{institution}\n\nDate: {nice_date(today)}",
                  f"सेवा में,\nशाखा प्रबंधक / क्लेम विभाग\n{institution}\n\nदिनांक: {nice_date(today, 'hi')}")
    # Every letter asks the institution to verify the sender: a copy sent by an impersonator works against them.
    verify = pick(lang, "For the family's safety, please share details only after verifying me against your nominee and "
                        "legal-heir records, and reply only to the address you hold on record.",
                  "परिवार की सुरक्षा के लिए, कृपया अपने नॉमिनी और कानूनी वारिस के रिकॉर्ड से मेरी पुष्टि करने के बाद ही "
                  "जानकारी दें, और उत्तर केवल अपने रिकॉर्ड में दर्ज पते पर भेजें।")
    closing = pick(lang, "Thank you for your help at this difficult time.\n\nYours faithfully,",
                   "इस कठिन समय में आपकी सहायता के लिए धन्यवाद।\n\nभवदीय,")

    if item.status == "probable":
        clues = "\n".join(f"- {nice_date(e.date, lang)}: {inr(e.amount)} ({e.description})"
                          for e in item.evidence if e.date)
        subject = pick(lang, f"Request to confirm any {kind_label} held by the late {name}",
                       f"स्वर्गीय {name} के नाम पर किसी {kind_label} की पुष्टि हेतु अनुरोध")
        # payments are quoted when we have them; a family memory alone is mentioned, never quoted to the institution
        why = (pick(lang, "While going through their bank records, our family noticed these entries that appear to be "
                          f"linked to {institution}:\n\n{clues}\n\n",
                    f"उनके बैंक रिकॉर्ड देखते समय हमारे परिवार ने ये प्रविष्टियाँ देखीं जो {institution} से जुड़ी लगती "
                    f"हैं:\n\n{clues}\n\n") if clues else
               pick(lang, f"Our family remembers that {name} may have dealt with {institution}. ",
                    f"हमारे परिवार को याद है कि {name} का {institution} से संबंध रहा हो सकता है। "))
        body = pick(
            lang,
            f"Dear Sir or Madam,\n\n{name} passed away on {dod}. I am the {case.relationship} of the deceased. "
            f"{why}We think {name} may have held a {kind_label} with you, but we have not "
            f"found the papers. Could you please confirm whether any {kind_label} exists in their name and, if so, "
            "share its number, the nominee recorded, and the claim process.\n\nI am enclosing a copy of the death "
            "certificate and can provide any further identification you need.",
            f"महोदय/महोदया,\n\n{name} का निधन {dod} को हुआ। दिवंगत से मेरा संबंध: {case.relationship}। {why}हमें लगता "
            f"है कि आपके यहाँ {name} के नाम पर {kind_label} होने की संभावना है, लेकिन हमें इसके कागज़ नहीं मिले। कृपया पुष्टि करें कि "
            f"क्या उनके नाम पर कोई {kind_label} है, और यदि है, तो उसका नंबर, दर्ज नॉमिनी और क्लेम की प्रक्रिया बताएँ।\n\n"
            "मैं मृत्यु प्रमाण पत्र की प्रति संलग्न कर रहा/रही हूँ और आवश्यक कोई भी पहचान पत्र दे सकता/सकती हूँ।",
        )
        kind = "existence_enquiry"
        title = pick(lang, f"Enquiry to {institution}", f"{institution} को पूछताछ पत्र")
    else:
        number = full_identifier(case, item) or item.identifier_masked or pick(lang, "[number]", "[नंबर]")
        nominee = (pick(lang, f" Your records should show {item.nominee} as the nominee.",
                        f" आपके रिकॉर्ड में नॉमिनी {item.nominee} दर्ज होने चाहिए।") if item.nominee else "")
        procedure = kb.lookup(item.type, lang)
        documents = procedure["documents_required"] if procedure["found"] else [pick(lang, "Death certificate",
                                                                                     "मृत्यु प्रमाण पत्र")]
        subject = pick(lang, f"Intimation of the death of {name} and request to begin the claim - {kind_label} "
                             f"no. {number}",
                       f"{name} के निधन की सूचना एवं क्लेम प्रारंभ करने हेतु अनुरोध - {kind_label} संख्या {number}")
        requests = pick(lang, [
            f"Record the death and stop any further debits or online access on this {kind_label}.",
            f"Share the claim form and the list of documents needed to settle this {kind_label}.",
            "Tell me the expected timeline and a contact person for this claim.",
        ], [
            f"मृत्यु को रिकॉर्ड करें और इस {kind_label} पर आगे के डेबिट या ऑनलाइन उपयोग रोकें।",
            f"इस {kind_label} के निपटान के लिए क्लेम फ़ॉर्म और आवश्यक दस्तावेज़ों की सूची दें।",
            "इस दावे की अनुमानित समय-सीमा और संपर्क व्यक्ति बताएँ।",
        ])
        body = pick(
            lang,
            f"Dear Sir or Madam,\n\nI am writing to inform you that {name}, the holder of {kind_label} no. {number} "
            f"with you, passed away on {dod}. I am the {case.relationship} of the deceased.{nominee}\n\n"
            f"I request you to:\n{_numbered(requests)}\n\nI am enclosing:\n{_numbered(documents)}",
            f"महोदय/महोदया,\n\nमैं आपको सूचित करना चाहता/चाहती हूँ कि आपके यहाँ {kind_label} संख्या {number} के धारक {name} "
            f"का निधन {dod} को हो गया। दिवंगत से मेरा संबंध: {case.relationship}।{nominee}\n\nमेरा अनुरोध है कि आप:\n"
            f"{_numbered(requests)}\n\nसंलग्न दस्तावेज़:\n{_numbered(documents)}",
        )
        kind = "claim_intimation"
        title = pick(lang, f"Claim letter to {institution}", f"{institution} को क्लेम पत्र")

    subject_label = pick(lang, "Subject", "विषय")
    text = f"{header}\n\n{subject_label}: {subject}\n\n{body}\n\n{verify}\n\n{closing}\n\n{_signature(case, lang)}"
    return Letter(item_id=item.id, institution=institution, kind=kind, title=title, body=text, language=lang)


def draft_reply_letter(case: Case, reply_id: str, today: date | None = None) -> Letter:
    """Cover letter answering an institution's reply: quotes their reference and lists what they asked for."""
    reply = case.get_reply(reply_id)
    if reply is None:
        raise KeyError(reply_id)
    lang, today = case.language, today or date.today()
    name = case.deceased_name
    task = next((t for t in (case.plan.tasks if case.plan else []) if t.id == reply.task_id), None)
    item_id = task.items[0].item_id if task and task.items else ""
    their = (pick(lang, f"your letter dated {nice_date(reply.letter_date)}", f"आपके दिनांक {nice_date(reply.letter_date, 'hi')} के पत्र")
             if reply.letter_date else pick(lang, "your recent letter", "आपके हाल के पत्र"))
    ref = (pick(lang, f" (your reference {reply.reference_masked})", f" (आपका संदर्भ {reply.reference_masked})")
           if reply.reference_masked else "")
    enclosed = [r.document + (f", {r.detail}" if r.detail else "") for r in reply.requirements]
    header = pick(lang, f"To,\nThe Claims Department\n{reply.institution}\n\nDate: {nice_date(today)}",
                  f"सेवा में,\nक्लेम विभाग\n{reply.institution}\n\nदिनांक: {nice_date(today, 'hi')}")
    subject = pick(lang, f"Documents for the claim of the late {name}{ref}",
                   f"स्वर्गीय {name} के दावे हेतु दस्तावेज़{ref}")
    body = pick(
        lang,
        f"Dear Sir or Madam,\n\nThank you for {their}{ref} about the late {name}. As you asked, I am enclosing:\n"
        f"{_numbered(enclosed) if enclosed else '[list the documents you are sending]'}\n\n"
        "Please let me know if anything else is needed, and confirm once you have received these.",
        f"महोदय/महोदया,\n\nस्वर्गीय {name} के संबंध में {their}{ref} के लिए धन्यवाद। आपके कहे अनुसार मैं ये संलग्न कर रहा/रही हूँ:\n"
        f"{_numbered(enclosed) if enclosed else '[भेजे जा रहे दस्तावेज़ों की सूची लिखें]'}\n\n"
        "कृपया बताएँ यदि कुछ और चाहिए, और इन्हें प्राप्त होने पर पुष्टि करें।",
    )
    closing = pick(lang, "Yours faithfully,", "भवदीय,")
    text = f"{header}\n\n{pick(lang, 'Subject', 'विषय')}: {subject}\n\n{body}\n\n{closing}\n\n{_signature(case, lang)}"
    return Letter(item_id=item_id, reply_id=reply.id, institution=reply.institution, kind="reply_cover",
                  title=pick(lang, f"Reply to {reply.institution}", f"{reply.institution} को उत्तर"), body=text,
                  language=lang)


def redraft(case: Case, letter: Letter) -> Letter:
    """A fresh draft of the same letter, keeping its id."""
    fresh = draft_reply_letter(case, letter.reply_id) if letter.reply_id else draft_letter(case, letter.item_id)
    fresh.id, fresh.created_at = letter.id, letter.created_at
    return fresh


def letter_pdf(letter: Letter) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_margins(22, 22, 22)
    pdf.add_page()
    pdf.add_font("NotoSans", "", str(FONTS / "NotoSans-Regular.ttf"))
    pdf.add_font("NotoSans", "B", str(FONTS / "NotoSans-Bold.ttf"))
    pdf.add_font("NotoDeva", "", str(FONTS / "NotoSansDevanagari-Regular.ttf"))
    pdf.add_font("NotoDeva", "B", str(FONTS / "NotoSansDevanagari-Bold.ttf"))
    pdf.set_text_shaping(True)
    main, fallback = ("NotoDeva", "NotoSans") if letter.language == "hi" else ("NotoSans", "NotoDeva")
    pdf.set_fallback_fonts([fallback])
    pdf.set_font(main, size=11.5)
    for paragraph in letter.body.split("\n"):
        if paragraph.strip():
            pdf.multi_cell(0, 6.4, paragraph, new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.ln(3.5)
    return bytes(pdf.output())
