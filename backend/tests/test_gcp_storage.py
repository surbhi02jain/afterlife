"""GcpStorage against the Firestore emulator + fake-gcs-server. Skipped unless the emulators are configured:

  docker run -d -p 8681:8681 gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators \\
      gcloud emulators firestore start --host-port=0.0.0.0:8681
  docker run -d -p 4443:4443 fsouza/fake-gcs-server:1.52.2 -scheme http -port 4443 -public-host localhost:4443
  curl -X POST localhost:4443/storage/v1/b -H 'content-type: application/json' -d '{"name":"afterlife-test"}'
  FIRESTORE_EMULATOR_HOST=localhost:8681 STORAGE_EMULATOR_HOST=http://localhost:4443 .venv/bin/pytest backend -k gcp
"""

import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.models import Document
from storage.base import CaseNotFound
from tests.helpers import new_case

pytestmark = pytest.mark.skipif(not (os.getenv("FIRESTORE_EMULATOR_HOST") and os.getenv("STORAGE_EMULATOR_HOST")),
                                reason="Firestore/GCS emulators not configured")


@pytest.fixture
def gcp():
    from storage.gcp import GcpStorage

    return GcpStorage(project="demo-afterlife", bucket="afterlife-test")


def test_case_round_trip_and_not_found(gcp):
    case = gcp.create_case(new_case(language="hi"))
    loaded = gcp.get_case(case.id)
    assert loaded.model_dump() == case.model_dump()
    with pytest.raises(CaseNotFound):
        gcp.get_case("missing")


def test_concurrent_updates_are_not_lost(gcp):
    case = gcp.create_case(new_case())

    def add(n):
        gcp.update_case(case.id, lambda c: c.documents.append(
            Document(filename=f"f{n}.png", content_type="image/png", size_bytes=1, storage_key=f"k{n}")))

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(add, range(12)))
    assert sorted(d.filename for d in gcp.get_case(case.id).documents) == sorted(f"f{n}.png" for n in range(12))


def test_share_token_lookup(gcp):
    case = gcp.create_case(new_case())
    gcp.update_case(case.id, lambda c: setattr(c, "share_token", f"tok{case.id}"))
    assert gcp.find_by_share_token(f"tok{case.id}").id == case.id
    assert gcp.find_by_share_token("nope") is None


def test_files_and_delete_my_data(gcp):
    case = gcp.create_case(new_case())
    key = gcp.save_file(case.id, "doc1", b"\x89PNG data", "image/png")
    gcp.save_file(case.id, "doc2", b"%PDF data", "application/pdf")
    assert gcp.read_file(key) == b"\x89PNG data"
    gcp.delete_file(key)
    with pytest.raises(FileNotFoundError):
        gcp.read_file(key)
    gcp.delete_file(key)  # idempotent

    gcp.delete_case(case.id)
    with pytest.raises(CaseNotFound):
        gcp.get_case(case.id)
    assert list(gcp.bucket.list_blobs(prefix=f"{case.id}/")) == []
    gcp.delete_case(case.id)  # idempotent
