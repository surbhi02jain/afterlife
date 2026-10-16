"""Storage interface. Cases are JSON documents; uploads are blobs keyed by case."""

from abc import ABC, abstractmethod
from typing import Callable

from app.models import Case


class CaseNotFound(KeyError):
    pass


class Storage(ABC):
    # --- cases -------------------------------------------------------------
    @abstractmethod
    def create_case(self, case: Case) -> Case: ...

    @abstractmethod
    def get_case(self, case_id: str) -> Case:
        """Raises CaseNotFound."""

    @abstractmethod
    def update_case(self, case_id: str, mutate: Callable[[Case], None]) -> Case:
        """Atomically load the case, apply `mutate` in place, save and return it. Raises CaseNotFound.

        Keep `mutate` fast: never call Gemini inside it.
        """

    @abstractmethod
    def delete_case(self, case_id: str) -> None:
        """Delete the case record AND all of its uploaded files. Idempotent."""

    # --- uploads -----------------------------------------------------------
    @abstractmethod
    def save_file(self, case_id: str, document_id: str, data: bytes, content_type: str) -> str:
        """Store bytes and return a storage key."""

    @abstractmethod
    def read_file(self, storage_key: str) -> bytes: ...
