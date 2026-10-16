"""Case operations shared by the API, the CLI scripts and (later) the agent."""

from concurrent.futures import ThreadPoolExecutor

from app.gemini import GeminiNotConfigured
from app.models import Case, Document
from storage import Storage
from tools.extraction import ExtractionError, extract_document


def add_document(storage: Storage, case_id: str, filename: str, content_type: str, data: bytes) -> Document:
    doc = Document(filename=filename, content_type=content_type, size_bytes=len(data), storage_key="")
    doc.storage_key = storage.save_file(case_id, doc.id, data, content_type)
    storage.update_case(case_id, lambda case: case.documents.append(doc))
    return doc


def extract_case_document(storage: Storage, case_id: str, document_id: str, *, client=None) -> Document:
    """Run Gemini extraction for one document and record the outcome on the case.

    Raises ExtractionError (after recording status=failed) so callers never mistake a failure for data.
    """
    case = storage.get_case(case_id)
    doc = case.get_document(document_id)
    if doc is None:
        raise KeyError(document_id)

    def set_status(**fields):
        def mutate(c: Case):
            target = c.get_document(document_id)
            for key, value in fields.items():
                setattr(target, key, value)
        return storage.update_case(case_id, mutate).get_document(document_id)

    set_status(status="extracting", error=None)
    try:
        result = extract_document(storage.read_file(doc.storage_key), doc.content_type, client=client)
    except (ExtractionError, GeminiNotConfigured) as exc:
        set_status(status="failed", error=str(exc))
        raise ExtractionError(str(exc)) from exc
    return set_status(status="extracted", error=None, extraction=result.document, extracted_with_model=result.model)


def extract_pending(storage: Storage, case_id: str, *, client=None, max_workers: int = 4) -> Case:
    """Extract every document that isn't extracted yet, a few at a time. Failures stay recorded per document."""
    pending = [d.id for d in storage.get_case(case_id).documents if d.status != "extracted"]

    def run(document_id: str):
        try:
            extract_case_document(storage, case_id, document_id, client=client)
        except ExtractionError:
            pass  # already recorded on the document as status=failed with the error message

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        list(pool.map(run, pending))
    return storage.get_case(case_id)
