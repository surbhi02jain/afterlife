"""Settings read from environment variables (and a repo-root .env file for local dev)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env", override=False)

# Checked against https://ai.google.dev/gemini-api/docs/models on 2026-10-16.
DEFAULT_EXTRACTION_MODEL = "gemini-3.8-flash"
DEFAULT_REASONING_MODEL = "gemini-4-argon"


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    extraction_model: str
    reasoning_model: str
    storage_backend: str
    local_data_dir: Path
    gcp_project: str
    gcs_bucket: str
    firestore_database: str
    max_upload_bytes: int
    gemini_rpm: int


def get_settings() -> Settings:
    data_dir = Path(os.getenv("LOCAL_DATA_DIR", "./data"))
    if not data_dir.is_absolute():
        data_dir = REPO_ROOT / data_dir
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        extraction_model=os.getenv("EXTRACTION_MODEL") or DEFAULT_EXTRACTION_MODEL,
        reasoning_model=os.getenv("REASONING_MODEL") or DEFAULT_REASONING_MODEL,
        storage_backend=os.getenv("STORAGE_BACKEND", "local"),
        local_data_dir=data_dir,
        gcp_project=os.getenv("GCP_PROJECT", ""),
        gcs_bucket=os.getenv("GCS_BUCKET", ""),
        firestore_database=os.getenv("FIRESTORE_DATABASE", "(default)"),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(15 * 1024 * 1024))),
        gemini_rpm=int(os.getenv("GEMINI_RPM", "0")),  # 0 = no client-side throttle
    )
