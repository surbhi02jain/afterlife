"""Production storage: Firestore for cases, Cloud Storage for uploads.

Uploads are also auto-deleted by a 24h bucket lifecycle rule (see scripts/deploy.sh).
"""

import threading
from collections import defaultdict
from typing import Callable

from google.cloud import firestore, storage as gcs

from app.models import Case, utc_now
from storage.base import CaseNotFound, Storage

COLLECTION = "cases"


class GcpStorage(Storage):
    def __init__(self, project: str, bucket: str, database: str = "(default)"):
        if not bucket:
            raise ValueError("GCS_BUCKET must be set when STORAGE_BACKEND=gcp")
        self.db = firestore.Client(project=project or None, database=database)
        self.bucket = gcs.Client(project=project or None).bucket(bucket)
        # Writers to the same case inside this instance queue up instead of fighting over the transaction;
        # Firestore's own retries then only have to handle the rare clash between instances.
        self._case_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._locks_guard = threading.Lock()

    def _lock_for(self, case_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._case_locks[case_id]

    def _ref(self, case_id: str):
        return self.db.collection(COLLECTION).document(case_id)

    @staticmethod
    def _to_dict(case: Case) -> dict:
        return case.model_dump(mode="json")

    def create_case(self, case: Case) -> Case:
        self._ref(case.id).set(self._to_dict(case))
        return case

    def get_case(self, case_id: str) -> Case:
        snap = self._ref(case_id).get()
        if not snap.exists:
            raise CaseNotFound(case_id)
        return Case.model_validate(snap.to_dict())

    def update_case(self, case_id: str, mutate: Callable[[Case], None]) -> Case:
        ref = self._ref(case_id)

        @firestore.transactional
        def run(transaction) -> Case:
            snap = ref.get(transaction=transaction)
            if not snap.exists:
                raise CaseNotFound(case_id)
            case = Case.model_validate(snap.to_dict())
            mutate(case)
            case.updated_at = utc_now()
            transaction.set(ref, self._to_dict(case))
            return case

        with self._lock_for(case_id):
            return run(self.db.transaction(max_attempts=10))

    def find_by_share_token(self, token: str) -> Case | None:
        if not token:
            return None
        query = self.db.collection(COLLECTION).where(filter=firestore.FieldFilter("share_token", "==", token)).limit(1)
        for snap in query.stream():
            return Case.model_validate(snap.to_dict())
        return None

    def delete_case(self, case_id: str) -> None:
        self._ref(case_id).delete()
        blobs = list(self.bucket.list_blobs(prefix=f"{case_id}/"))
        if blobs:
            self.bucket.delete_blobs(blobs)

    def save_file(self, case_id: str, document_id: str, data: bytes, content_type: str) -> str:
        key = f"{case_id}/{document_id}"
        self.bucket.blob(key).upload_from_string(data, content_type=content_type)
        return key

    def read_file(self, storage_key: str) -> bytes:
        return self.bucket.blob(storage_key).download_as_bytes()
