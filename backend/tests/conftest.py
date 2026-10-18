import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import gemini
from app.main import app
from storage import get_storage
from storage.local import LocalStorage

SAMPLE_REPLY = {
    "institution": "Sahyadri National Bank", "document_type": "bank_statement", "identifier": "30218847201931",
    "holder_name": "SURESH NARAYAN RAO", "nominee": "Kamala Suresh Rao",
    "amounts": [{"label": "closing balance", "value": 199548.6, "currency": "INR"}],
    "dates": [{"label": "statement from", "date": "2026-06-01"}],
    "transactions": [
        {"date": "2026-06-07", "description": "NACH DR-KAVACH LIFE INS-PREM", "amount": 3150, "direction": "debit"},
        {"date": "2026-06-18", "description": "ACH CR-NAVBHARAT POWER LTD-FINAL DIVIDEND", "amount": 1840,
         "direction": "credit"},
    ],
    "language_detected": "en", "confidence": "high",
}


class FakeModels:
    def __init__(self, text=None, error=None):
        self.text, self.error, self.calls = text, error, []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text, candidates=[SimpleNamespace(finish_reason="STOP")])


class FakeClient:
    """Stands in for google.genai.Client in tests; never touches the network."""

    def __init__(self, text=None, error=None):
        self.models = FakeModels(text, error)


@pytest.fixture(autouse=True)
def no_real_gemini(monkeypatch):
    """Tests never see the real key (.env is loaded at import) and never wait on the rate limiter."""
    monkeypatch.setenv("GEMINI_API_KEY", "")
    gemini.get_client.cache_clear()
    monkeypatch.setattr(gemini, "get_rate_limiter", lambda: gemini.RateLimiter(0))
    monkeypatch.setattr(gemini, "get_daily_budget", lambda: gemini.DailyBudget(0))
    yield
    gemini.get_client.cache_clear()


@pytest.fixture
def fake_client():
    return FakeClient(text=json.dumps(SAMPLE_REPLY))


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path)


@pytest.fixture
def api(storage):
    app.dependency_overrides[get_storage] = lambda: storage
    yield TestClient(app)
    app.dependency_overrides.clear()
