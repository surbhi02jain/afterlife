"""The synthetic demo family: its documents and the REAL Gemini replies recorded for them.

For demo cases only, extraction can replay the recorded reply for a file whose bytes exactly match a demo document
(saves quota and makes the 3-minute demo predictable). This is never used for real uploads, it is logged in the
activity log as a saved reading, and it can be switched off with DEMO_REPLAY_EXTRACTION=false.
"""

import hashlib
import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.config import REPO_ROOT
from app.models import Case

DEMO_DOCS_DIR = REPO_ROOT / "demo" / "docs"
RECORDED_DIR = REPO_ROOT / "demo" / "recorded" / "extraction"

# Fictional person; the app shows a "sample family" banner for is_demo cases.
DEMO_CASE = dict(deceased_name="Suresh Narayan Rao", date_of_death=date(2026, 9, 2),
                 relationship="son", language="en")


def replay_enabled() -> bool:
    return os.getenv("DEMO_REPLAY_EXTRACTION", "true").lower() in ("1", "true", "yes")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=1)
def _recorded_by_hash() -> dict[str, dict]:
    replies = {}
    for doc in DEMO_DOCS_DIR.glob("*.png"):
        recorded = RECORDED_DIR / f"{doc.stem}.json"
        if recorded.exists():
            replies[sha256(doc.read_bytes())] = json.loads(recorded.read_text())
    return replies


def recorded_reply(data: bytes) -> dict | None:
    """{'raw_response', 'model', 'source_file'} for an exact demo document, else None."""
    return _recorded_by_hash().get(sha256(data))


def demo_documents() -> list[Path]:
    return sorted(DEMO_DOCS_DIR.glob("*.png"))


def new_demo_case() -> Case:
    return Case(**DEMO_CASE, is_demo=True)
