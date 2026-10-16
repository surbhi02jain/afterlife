from functools import lru_cache

from app.config import get_settings
from storage.base import CaseNotFound, Storage

__all__ = ["CaseNotFound", "Storage", "get_storage"]


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "local":
        from storage.local import LocalStorage

        return LocalStorage(settings.local_data_dir)
    if settings.storage_backend == "gcp":
        from storage.gcp import GcpStorage

        return GcpStorage(settings.gcp_project, settings.gcs_bucket, settings.firestore_database)
    raise ValueError(f"Unknown STORAGE_BACKEND={settings.storage_backend!r} (use local or gcp)")
