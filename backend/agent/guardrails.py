"""Code-level guardrails that run regardless of what the model does."""

import re

CREDENTIAL_TERMS = re.compile(
    r"\b(pin|m-?pin|upi pin|atm pin|otp|cvv|password|passcode|passwd|net ?banking|login|log in|user ?id|"
    r"card number|debit card|credit card|atm card|पिन|पासवर्ड|ओटीपी|कार्ड)\b", re.I)
USE_TERMS = re.compile(
    r"\b(use|using|login|log in|access|withdraw|transfer|pay|unlock|reset|share|open|get into|"
    r"इस्तेमाल|उपयोग|निकाल|ट्रांसफर|खोल)", re.I)

LEGAL_TERMS = re.compile(
    r"\b(will|succession|legal heir|probate|court|inherit\w*|lawyer|property dispute|affidavit|"
    r"वसीयत|उत्तराधिकार|कानूनी|अदालत|वारिस)", re.I)

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
    return bool(CREDENTIAL_TERMS.search(message) and USE_TERMS.search(message))


def touches_legal_topic(*texts: str) -> bool:
    return any(LEGAL_TERMS.search(t or "") for t in texts)


def with_legal_note(reply: str, language: str) -> str:
    note = LEGAL_NOTE[language]
    return reply if note in reply else f"{reply.rstrip()}\n\n{note}"
