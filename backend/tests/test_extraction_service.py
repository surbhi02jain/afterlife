import pytest
from google.genai import errors

from app.models import ExtractedDocument
from tests.conftest import FakeClient
from tools.extraction import ExtractionError, extract_document


def test_sends_schema_and_parses_reply(fake_client):
    result = extract_document(b"png-bytes", "image/png", client=fake_client, model="test-model")

    assert result.model == "test-model"
    assert result.document.institution == "Sahyadri National Bank"
    call = fake_client.models.calls[0]
    assert call["model"] == "test-model"
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].response_json_schema == ExtractedDocument.model_json_schema()
    assert call["contents"][0].inline_data.mime_type == "image/png"


def test_unsupported_type_is_rejected_before_calling_gemini(fake_client):
    with pytest.raises(ExtractionError, match="Unsupported file type"):
        extract_document(b"x", "text/plain", client=fake_client)
    assert fake_client.models.calls == []


def test_empty_reply_raises():
    with pytest.raises(ExtractionError, match="empty response"):
        extract_document(b"x", "image/png", client=FakeClient(text=""))


def test_invalid_reply_raises_instead_of_returning_partial_data():
    with pytest.raises(ExtractionError, match="did not match"):
        extract_document(b"x", "image/png", client=FakeClient(text='{"document_type": "bank_statement"}'))


def test_api_error_is_wrapped():
    error = errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    with pytest.raises(ExtractionError, match="429"):
        extract_document(b"x", "image/png", client=FakeClient(error=error))
