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
    _words(r"use", r"using", r"used", r"withdraw\w*", r"transfer\w*", r"swipe\w*", r"unlock\w*", r"access\w*",
           r"log\s*in", r"login", r"sign\s*in", r"get\s+into", r"break\s+into", r"pay\s+(?:with|using|by|from)",
           r"take\s+out", r"move\s+(?:the\s+)?money"),
    _stems("इस्तेमाल", "उपयोग", "निकाल", "ट्रांसफर", "खोल", "लॉग"),
]), re.I)
ASK_TERMS = re.compile("|".join([
    _words(r"what(?:'s|\s+is|\s+was)", r"tell", r"know", r"find", r"get", r"give", r"share", r"recover\w*",
           r"reset\w*", r"remember", r"guess\w*", r"crack\w*", r"bypass\w*", r"enter", r"type", r"need"),
    _stems("बता", "चाहिए", "पता", "डाल"),
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
    return bool(ACCESS_TERMS.search(message) and USE_TERMS.search(message))


def touches_legal_topic(*texts: str) -> bool:
    return any(LEGAL_TERMS.search(t or "") for t in texts)


def with_legal_note(reply: str, language: str) -> str:
    note = LEGAL_NOTE[language]
    return reply if note in reply else f"{reply.rstrip()}\n\n{note}"
