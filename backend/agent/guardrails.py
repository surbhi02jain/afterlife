"""Code-level guardrails that run regardless of what the model does."""

import re

# Python's \b treats Devanagari vowel signs (e.g. the ी in ओटीपी) as non-word characters, so a word ending in one
# never matches `\b...\b`. These boundaries count every Devanagari character as part of the word.
_START = r"(?<![\wऀ-ॿ])"
_END = r"(?![\wऀ-ॿ])"


def _words(*alternatives: str) -> str:
    return _START + "(?:" + "|".join(alternatives) + ")" + _END


def _stems(*alternatives: str) -> str:
    """Hindi verb stems: निकाल matches निकालना / निकालने."""
    return _START + "(?:" + "|".join(alternatives) + ")"


# Secrets: asking to know them is as bad as asking to use them. "PIN code" is the postal code on letters, not a PIN.
SECRET_TERMS = re.compile(_words(
    r"pins?(?!\s*-?code)", r"m-?pin", r"otps?", r"cvv", r"passwords?", r"passcodes?", r"passwd",
    "पिन", "पासवर्ड", "ओटीपी"), re.I)
# Access routes: only a problem with a "use" verb. "Pay off his credit card" is a normal question about a debt.
ACCESS_TERMS = re.compile(_words(
    r"(?:debit|credit|atm)\s+cards?", r"cards?", r"card\s+number", r"net\s*banking", r"online\s+banking",
    r"mobile\s+banking", r"internet\s+banking", r"log\s*in", r"login", r"user\s*id",
    "कार्ड", "नेट बैंकिंग"), re.I)  # a UPI PIN is caught by SECRET_TERMS; "stop his UPI transfers" is fine
USE_TERMS = re.compile("|".join([
    # not "used": "he used his card" describes the past, not a request
    _words(r"use", r"using", r"withdraw\w*", r"transfer\w*", r"swipe\w*", r"unlock\w*", r"access\w*",
           r"log\s*in", r"login", r"sign\s*in", r"get\s+into", r"break\s+into", r"pay\s+(?:with|using|by|from)",
           r"take\s+out", r"move\s+(?:the\s+)?money"),
    _stems("इस्तेमाल", "उपयोग", "निकाल", "ट्रांसफर", "खोल", "लॉग"),
]), re.I)
ASK_TERMS = re.compile("|".join([
    _words(r"what(?:'s|\s+is|\s+was)", r"tell", r"know", r"find", r"get", r"give", r"share", r"recover\w*",
           r"reset\w*", r"remember", r"guess\w*", r"crack\w*", r"bypass\w*", r"enter", r"type", r"need"),
    _stems("बता", "चाहिए", "पता", "डाल"),
]), re.I)

# Shutting an account down is exactly what the family should do: "how do we stop someone using his net banking?"
PROTECT_TERMS = re.compile("|".join([
    _words(r"close\w*", r"block\w*", r"cancel\w*", r"stop\w*", r"freez\w*", r"report\w*", r"deactivat\w*",
           r"disabl\w*", r"surrender\w*", r"misus\w*", r"fraud\w*"),
    _stems("बंद", "ब्लॉक", "रोक", "रद्द"),
]), re.I)

LEGAL_TERMS = re.compile("|".join([
    # "will" only as the document, never the future tense ("the bank will send a form")
    _words(r"(?:a|the|his|her|their|my|any|no|written|make|made|making|without)\s+will", r"wills",
           r"will\s+(?:and|or)\s+testament", r"will\s+(?:deed|document|paper)s?"),
    _words(r"succession", r"legal\s+heirs?", r"probate", r"court", r"inherit\w*", r"lawyers?", r"advocates?",
           r"property\s+dispute", r"disputes?", r"affidavit"),
    _stems("वसीयत", "उत्तराधिकार", "कानूनी", "अदालत", "वारिस"),
]), re.I)

REFUSAL = {
    "en": ("I'm sorry, I can't help with using {name}'s cards, PINs, passwords, OTPs or online banking. Using them "
           "after a death isn't allowed and can cause trouble for the family later. The safe way is to inform the "
           "bank, which protects the money for the nominee. I can prepare that letter for you."),
    "hi": ("माफ़ कीजिए, मैं {name} के कार्ड, PIN, पासवर्ड, OTP या नेट बैंकिंग के उपयोग में मदद नहीं कर सकता। मृत्यु के बाद "
           "इनका उपयोग करना अनुमत नहीं है और बाद में परिवार के लिए परेशानी हो सकती है। सुरक्षित तरीका है बैंक को सूचित "
           "करना, जिससे पैसा नॉमिनी के लिए सुरक्षित रहता है। मैं आपके लिए वह पत्र तैयार कर सकता हूँ।"),
}

LEGAL_NOTE = {
    "en": "This is guidance, not legal advice.",
    "hi": "यह मार्गदर्शन है, कानूनी सलाह नहीं।",
}


def asks_to_use_credentials(message: str) -> bool:
    if SECRET_TERMS.search(message) and (ASK_TERMS.search(message) or USE_TERMS.search(message)):
        return True
    # Secrets above are refused whatever the wording; cards and banking only when it isn't about shutting them down.
    return bool(ACCESS_TERMS.search(message) and USE_TERMS.search(message) and not PROTECT_TERMS.search(message))


def touches_legal_topic(*texts: str) -> bool:
    return any(LEGAL_TERMS.search(t or "") for t in texts)


def with_legal_note(reply: str, language: str) -> str:
    note = LEGAL_NOTE[language]
    return reply if note in reply else f"{reply.rstrip()}\n\n{note}"


# A secret said or written next to digits: "his PIN is 4 4 1 2", "पासवर्ड 1503 है". Never kept, whatever the model wrote.
_SECRET_WITH_DIGITS = re.compile("(" + SECRET_TERMS.pattern + r"[^\d\n]{0,25})\d(?:[\s-]?\d){2,}", re.I)
# Card numbers: 15 or 16 digits, possibly in groups. (Bank account numbers, often 9 to 14 digits, are masked to the
# last 4 elsewhere, which is the rule for account numbers; a 16-digit account is removed here, which errs safe.)
_CARD_NUMBER = re.compile(r"(?<!\d)\d(?:[\s-]?\d){14,15}(?!\d)")


def plain_dashes(text: str) -> str:
    """Em dashes (and spaced en dashes) read as machine-written; the app's own text uses commas and colons."""
    return re.sub(r"\s*\u2014\s*|\s+\u2013\s+", ", ", text)


def redact_secrets(text: str) -> str:
    return _CARD_NUMBER.sub("[removed]", _SECRET_WITH_DIGITS.sub(r"\1[removed]", text))


# What a genuine bank or insurer never asks for in a claim. Checked in code on what Gemini read from a reply,
# on top of the red flags Gemini itself reports.
# Genuine letters mention fees and OTPs too ("duplicate passbook charges", "never share your OTP", "Aadhaar OTP
# e-KYC"), so a signal needs the scam's shape: a fee to RELEASE the money, or a secret being ASKED FOR.
_FEE_WORDS = r"(?:fee|charges?|amount|payment)"
SCAM_SIGNALS = {
    "fee": re.compile("|".join([
        _words(r"processing\s+(?:fee|charges?)", r"release\s+(?:fee|charges?)", r"clearance\s+(?:fee|charges?)",
               r"advance\s+(?:fee|payment)", r"(?:gst|tax)\s+to\s+release",
               _FEE_WORDS + r"\b[^.\n]{0,60}?\bto\s+(?:release|process|clear|unlock)"),
        r"(?:शुल्क|फ़ीस|फीस)[^।\n]{0,40}जारी", r"जारी[^।\n]{0,40}(?:शुल्क|फ़ीस|फीस)",
    ]), re.I),
    "secret": SECRET_TERMS,  # only counts in a sentence that asks for it (see scam_signals)
    "remote_access": re.compile(_words(r"anydesk", r"teamviewer", r"quick\s*support", r"screen\s*shar\w*",
                                       r"remote\s+access", r"install\s+(?:the\s+)?app"), re.I),
    "personal_payment": re.compile(_words(r"upi\s+id", r"@ok\w+", r"@ybl", r"@paytm", r"@upi", r"pay\s+to\s+this",
                                          r"scan\s+(?:the\s+)?qr", r"gpay", r"phonepe"), re.I),
}

SCAM_LABEL = {
    "fee": ("asks for a fee or payment to release the money", "पैसा जारी करने के लिए शुल्क या भुगतान माँगता है"),
    "secret": ("asks for an OTP, PIN or password", "OTP, PIN या पासवर्ड माँगता है"),
    "remote_access": ("asks to install an app or share the screen", "कोई ऐप इंस्टॉल करने या स्क्रीन शेयर करने को कहता है"),
    "personal_payment": ("asks for payment to a UPI id or QR code", "किसी UPI आईडी या QR कोड पर भुगतान माँगता है"),
}


# A warning, not a request: "never share your OTP", "do not give your PIN", "no password is needed", "OTP मत बताएँ".
_NEGATION = re.compile(_words(r"never", r"not", r"don'?t", r"no", r"without") + "|" + _stems("नहीं", "मत", "कभी"), re.I)
# Judged clause by clause, so "share the OTP now, no need to visit" is still caught by its first clause.
_CLAUSE_BREAK = re.compile(r"[.!?।\n,;:]|\b(?:and|but|then)\b|(?:और|लेकिन|फिर)", re.I)


def _asks_for_secret(text: str) -> bool:
    """A clause that mentions a PIN, OTP or password, asks for it, and isn't a warning against sharing it."""
    return any(SECRET_TERMS.search(c) and (ASK_TERMS.search(c) or USE_TERMS.search(c)) and not _NEGATION.search(c)
               for c in _CLAUSE_BREAK.split(text))


def scam_signals(*texts: str | None) -> list[str]:
    """Keys of SCAM_SIGNALS found in any of the texts."""
    joined = "\n".join(t for t in texts if t)
    return [key for key, pattern in SCAM_SIGNALS.items()
            if (_asks_for_secret(joined) if key == "secret" else pattern.search(joined))]
