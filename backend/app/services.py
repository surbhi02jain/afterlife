"""Case operations shared by the API, the CLI scripts and (later) the agent."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

from app.gemini import GeminiNotConfigured
from app.models import Case, Document, InferenceRun, ItemStatus
from storage import Storage
from tools.asset_map import refresh_recurring, sync_documents
from tools.extraction import ExtractionError, extract_document
from tools.inference import InferenceError, apply_proposals, collect_transactions, propose


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
            if target.status == "extracted":
                sync_documents(c)  # fold the new document into the asset map
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


def sync_asset_map(storage: Storage, case_id: str) -> Case:
    return storage.update_case(case_id, sync_documents)


def run_inference(storage: Storage, case_id: str, *, client=None) -> InferenceRun:
    """Ask Gemini for hidden assets (outside the case lock), then verify and merge them in."""
    case = storage.get_case(case_id)
    refs = collect_transactions(case)
    if not refs:
        raise InferenceError("There are no transactions to look through yet. Please add a statement or passbook.")
    try:
        result, model = propose(case, refs, client=client)
    except GeminiNotConfigured as exc:
        raise InferenceError(str(exc)) from exc

    runs = []
    storage.update_case(case_id, lambda c: runs.append(apply_proposals(c, result, refs, model)))
    return runs[0]


def set_item_status(storage: Storage, case_id: str, item_id: str, status: ItemStatus) -> Case:
    def mutate(c: Case):
        item = c.get_item(item_id)
        if item is None:
            raise KeyError(item_id)
        item.status = status
        item.decided_by_user = True
        refresh_recurring(c, date.today())

    return storage.update_case(case_id, mutate)
