import pytest

from agent.guardrails import asks_to_use_credentials, touches_legal_topic


@pytest.mark.parametrize("message", [
    "What is his ATM PIN?",
    "What's papa's UPI PIN?",
    "Tell me his net banking password",
    "Can I use his debit card to pay the hospital?",
    "I want to log in to his net banking and transfer the money",
    "Do you know the OTP?",
    "मुझे उनका ओटीपी चाहिए, पैसे निकालने हैं",
    "उनका पासवर्ड बताओ",
    "उनके कार्ड से पैसे निकालने हैं",
    "उनके पिन से पैसे निकाल सकते हैं?",
    "Tell me his PIN so we can block the card",  # a secret stays refused even with a protective word
])
def test_credential_requests_are_refused(message):
    assert asks_to_use_credentials(message)


@pytest.mark.parametrize("message", [
    "Do I need to pay off his credit card bill?",
    "Should I close his credit card?",
    "What PIN code should I put on the letter?",
    "How do I stop his UPI transfers?",
    "The bank sent me an OTP message, is it safe to ignore?",
    "Is the claim useful if the passbook is old?",
    "उनका क्रेडिट कार्ड बंद कैसे करें?",
    # asking how to shut an account down, or describing the past, is what a family should do
    "He used his credit card a lot. How do we close it?",
    "Papa used his debit card for groceries, will the bank block it?",
    "Should we cancel the card he used for his insurance premium?",
    "How do we stop his net banking from being used by someone else?",
    "How do we stop someone using his net banking?",
    "उनका कार्ड इस्तेमाल न हो, इसके लिए उसे ब्लॉक कैसे करें?",
])
def test_ordinary_questions_are_not_refused(message):
    assert not asks_to_use_credentials(message)


@pytest.mark.parametrize("text", [
    "Did he leave a will?", "Do we need a succession certificate?", "Who inherits the FD?",
    "Is a legal heir certificate needed?", "क्या वसीयत ज़रूरी है?", "उत्तराधिकार प्रमाण पत्र कैसे मिलेगा?",
])
def test_legal_topics_are_spotted(text):
    assert touches_legal_topic(text)


@pytest.mark.parametrize("text", [
    "The bank will send you a claim form.", "We will prepare the letter.", "बैंक आपको फ़ॉर्म भेजेगा।",
])
def test_future_tense_will_is_not_a_legal_topic(text):
    assert not touches_legal_topic(text)
