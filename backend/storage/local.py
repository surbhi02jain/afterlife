"""Local dev storage: one JSON file per case, uploads as files on disk."""

import shutil
import threading
from pathlib import Path
from typing import Callable

from app.models import Case, utc_now
from storage.base import CaseNotFound, Storage


class LocalStorage(Storage):
    def __init__(self, root: Path):
        self.root = Path(root)
        self.cases_dir = self.root / "cases"
        self.uploads_dir = self.root / "uploads"
        self.cases_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _case_path(self, case_id: str) -> Path:
        if not case_id.isalnum():  # ids are uuid hex; blocks path traversal
            raise CaseNotFound(case_id)
        return self.cases_dir / f"{case_id}.json"

    def _write(self, case: Case) -> None:
        path = self._case_path(case.id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(case.model_dump_json(indent=2))
        tmp.replace(path)

    def _read(self, case_id: str) -> Case:
        path = self._case_path(case_id)
        if not path.exists():
            raise CaseNotFound(case_id)
        return Case.model_validate_json(path.read_text())

    def create_case(self, case: Case) -> Case:
        with self._lock:
            self._write(case)
        return case

    def get_case(self, case_id: str) -> Case:
        with self._lock:
            return self._read(case_id)

    def update_case(self, case_id: str, mutate: Callable[[Case], None]) -> Case:
        with self._lock:
            case = self._read(case_id)
            mutate(case)
            case.updated_at = utc_now()
            self._write(case)
            return case

    def find_by_share_token(self, token: str) -> Case | None:
        if not token or not token.isalnum():
            return None
        with self._lock:
            for path in self.cases_dir.glob("*.json"):
                case = Case.model_validate_json(path.read_text())
                if case.share_token == token:
                    return case
        return None

    def delete_case(self, case_id: str) -> None:
        with self._lock:
            path = self._case_path(case_id)
            path.unlink(missing_ok=True)
            shutil.rmtree(self.uploads_dir / case_id, ignore_errors=True)

    def save_file(self, case_id: str, document_id: str, data: bytes, content_type: str) -> str:
        self._case_path(case_id)  # validates id
        folder = self.uploads_dir / case_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / document_id).write_bytes(data)
        return f"{case_id}/{document_id}"

    def read_file(self, storage_key: str) -> bytes:
        path = (self.uploads_dir / storage_key).resolve()
        if self.uploads_dir.resolve() not in path.parents:
            raise FileNotFoundError(storage_key)
        return path.read_bytes()
