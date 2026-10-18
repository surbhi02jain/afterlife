"""The synthetic demo family: its documents and the REAL Gemini replies recorded for them.

For demo cases only, extraction can replay the recorded reply for a file whose bytes exactly match a demo document
(saves quota and makes the 3-minute demo predictable). This is never used for real uploads, it is logged in the
activity log as a saved reading, and it can be switched off with DEMO_REPLAY_EXTRACTION=false.

One demo document (the mutual fund statement) is a password-protected PDF, like the real thing. Its recorded reply
is keyed by the bytes of the UNLOCKED copy, which is what the app stores once the family types the password.

The same holds for the sample family's other inputs (demo/samples: a recorded memory and two replies from
institutions) and its name check: a recorded REAL reply is replayed only for a byte-identical input.
"""

import hashlib
import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.config import REPO_ROOT
from app.models import Case
from tools import pdf

DEMO_DOCS_DIR = REPO_ROOT / "demo" / "docs"
RECORDED_ROOT = REPO_ROOT / "demo" / "recorded"
RECORDED_DIR = RECORDED_ROOT / "extraction"
SAMPLES_DIR = REPO_ROOT / "demo" / "samples"

# The sample family's other inputs, for buttons a judge can press without their own files.
SAMPLE_MEMORY = SAMPLES_DIR / "memory_hi.wav"  # Kamala, in Hindi, on what she remembers (synthetic voice)
SAMPLE_REPLIES = {  # sample reply -> the institution whose task it belongs to
    "reply_kavach_life.png": "Kavach Life Insurance",
    "message_fake_bank.png": "Sahyadri National Bank",
}

# Fictional person; the app shows a "sample family" banner for is_demo cases.
DEMO_CASE = dict(deceased_name="Suresh Narayan Rao", date_of_death=date(2026, 9, 2),
                 relationship="son", language="en")
# Fictional, like everything else here: first 4 letters of the name + day and month of birth (15 March).
DEMO_PDF_PASSWORD = "SURE1503"


def replay_enabled() -> bool:
    return os.getenv("DEMO_REPLAY_EXTRACTION", "true").lower() in ("1", "true", "yes")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=1)
def _recorded_by_hash() -> dict[str, dict]:
    replies = {}
    for doc in demo_documents():
        recorded = RECORDED_DIR / f"{doc.stem}.json"
        if recorded.exists():
            replies[sha256(readable_bytes(doc))] = json.loads(recorded.read_text())
    return replies


@lru_cache(maxsize=None)
def _recorded_inputs(kind: str) -> dict[str, dict]:
    """Recorded Gemini replies for memories, name checks and institution replies, keyed by the sha256 of the exact
    input they answer (the recording, the name list, the letter image). Written by scripts/record_samples.py."""
    folder = RECORDED_ROOT / kind
    return {f["input_sha256"]: f for f in (json.loads(p.read_text()) for p in sorted(folder.glob("*.json")))}


def recorded(kind: str, data: bytes | None) -> dict | None:
    """{'raw_response', 'model', 'input_sha256', ...} for a byte-identical sample input, else None."""
    return _recorded_inputs(kind).get(sha256(data)) if data else None


def recorded_reply(data: bytes) -> dict | None:
    """{'raw_response', 'model', 'source_file'} for an exact demo document, else None."""
    return _recorded_by_hash().get(sha256(data))


def demo_documents() -> list[Path]:
    return sorted([*DEMO_DOCS_DIR.glob("*.png"), *DEMO_DOCS_DIR.glob("*.pdf")])


def content_type(path: Path) -> str:
    return "application/pdf" if path.suffix == ".pdf" else "image/png"


def readable_bytes(path: Path) -> bytes:
    """The file as the app reads it: demo PDFs unlocked with the demo password."""
    data = path.read_bytes()
    return pdf.unlock(data, DEMO_PDF_PASSWORD) if path.suffix == ".pdf" else data


def new_demo_case() -> Case:
    return Case(**DEMO_CASE, is_demo=True)


def sample_replies_by_task(case: Case) -> dict[str, list[str]]:
    """For the demo screens: which sample reply belongs to which plan task (matched by institution)."""
    from tools.finance import same_institution

    found: dict[str, list[str]] = {}
    for task in case.plan.tasks if case.plan else []:
        for name, institution in SAMPLE_REPLIES.items():
            if same_institution(task.institution, institution):
                found.setdefault(task.id, []).append(name)
    return found
