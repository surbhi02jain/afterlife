"""Saath API."""

import mimetypes

from fastapi import Depends, FastAPI, HTTPException, Response, UploadFile

from app import services
from app.config import get_settings
from app.models import Case, CaseCreate, CaseUpdate, Document
from storage import CaseNotFound, Storage, get_storage
from tools.extraction import SUPPORTED_MIME_TYPES, ExtractionError

app = FastAPI(title="Saath", version="0.1.0")


def load_case(case_id: str, storage: Storage = Depends(get_storage)) -> Case:
    try:
        return storage.get_case(case_id)
    except CaseNotFound:
        raise HTTPException(404, "Case not found")


@app.get("/api/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "storage_backend": settings.storage_backend,
        "extraction_model": settings.extraction_model,
        "reasoning_model": settings.reasoning_model,
        "gemini_configured": bool(settings.gemini_api_key),
    }


# --- cases -----------------------------------------------------------------

@app.post("/api/cases", response_model=Case, status_code=201)
def create_case(body: CaseCreate, storage: Storage = Depends(get_storage)):
    return storage.create_case(Case(**body.model_dump()))


@app.get("/api/cases/{case_id}", response_model=Case)
def get_case(case: Case = Depends(load_case)):
    return case


@app.patch("/api/cases/{case_id}", response_model=Case)
def update_case(body: CaseUpdate, case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    changes = body.model_dump(exclude_unset=True, exclude_none=True)

    def mutate(c: Case):
        for key, value in changes.items():
            setattr(c, key, value)

    return storage.update_case(case.id, mutate)


@app.delete("/api/cases/{case_id}", status_code=204)
def delete_case(case_id: str, storage: Storage = Depends(get_storage)):
    storage.delete_case(case_id)
    return Response(status_code=204)


# --- documents ---------------------------------------------------------------

def _content_type(upload: UploadFile) -> str:
    declared = (upload.content_type or "").lower()
    if declared in SUPPORTED_MIME_TYPES:
        return declared
    guessed, _ = mimetypes.guess_type(upload.filename or "")
    return (guessed or declared or "application/octet-stream").lower()


@app.post("/api/cases/{case_id}/documents", response_model=list[Document], status_code=201)
async def upload_documents(
    files: list[UploadFile], case: Case = Depends(load_case), storage: Storage = Depends(get_storage)
):
    limit = get_settings().max_upload_bytes
    prepared = []
    for upload in files:
        content_type = _content_type(upload)
        if content_type not in SUPPORTED_MIME_TYPES:
            raise HTTPException(415, f"{upload.filename}: please upload a photo (PNG/JPEG/WEBP/HEIC) or a PDF.")
        data = await upload.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"{upload.filename} is larger than {limit // (1024 * 1024)} MB.")
        if not data:
            raise HTTPException(400, f"{upload.filename} is empty.")
        prepared.append((upload.filename or "upload", content_type, data))
    return [services.add_document(storage, case.id, *item) for item in prepared]


@app.get("/api/cases/{case_id}/documents", response_model=list[Document])
def list_documents(case: Case = Depends(load_case)):
    return case.documents


@app.post("/api/cases/{case_id}/documents/{document_id}/extract", response_model=Document)
def extract_one(document_id: str, case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    if case.get_document(document_id) is None:
        raise HTTPException(404, "Document not found")
    try:
        return services.extract_case_document(storage, case.id, document_id)
    except ExtractionError as exc:
        raise HTTPException(502, str(exc))


@app.post("/api/cases/{case_id}/extract", response_model=Case)
def extract_all(case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    """Extract every pending document. Per-file failures are recorded on each document (status=failed)."""
    return services.extract_pending(storage, case.id)
