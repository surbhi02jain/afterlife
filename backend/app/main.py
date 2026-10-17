"""Saath API. Also serves the built frontend (frontend/dist) so the app ships as one container."""

import mimetypes

from fastapi import Depends, FastAPI, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agent.loop import ANALYSE_MESSAGE, AgentError, run_agent
from app import services
from app.config import REPO_ROOT, get_settings
from app.models import BoardStatus, Case, CaseCreate, CaseUpdate, Document, InferenceRun, ItemStatus, Letter
from storage import CaseNotFound, Storage, get_storage
from tools.asset_map import asset_map_view
from tools.extraction import SUPPORTED_MIME_TYPES, ExtractionError
from tools.inference import InferenceError
from tools.letters import letter_pdf
from tools.questions import QuestionError

app = FastAPI(title="Saath", version="0.3.0")


def load_case(case_id: str, storage: Storage = Depends(get_storage)) -> Case:
    try:
        return storage.get_case(case_id)
    except CaseNotFound:
        raise HTTPException(404, "Case not found")


def document_view(d: Document) -> dict:
    e = d.extraction
    return {"id": d.id, "filename": d.filename, "status": d.status, "error": d.error, "size_bytes": d.size_bytes,
            "document_type": e.document_type.value if e else None, "institution": e.institution if e else None,
            "transactions": len(e.transactions) if e else 0, "confidence": e.confidence if e else None,
            "saved_reading": bool(d.extracted_with_model and d.extracted_with_model.endswith("(recorded)"))}


def case_view(case: Case) -> dict:
    """What the app shows. Raw extractions and storage keys stay server-side."""
    return {
        "id": case.id, "deceased_name": case.deceased_name, "date_of_death": case.date_of_death.isoformat(),
        "relationship": case.relationship, "language": case.language, "is_demo": case.is_demo,
        "created_at": case.created_at, "updated_at": case.updated_at, "share_token": case.share_token,
        "documents": [document_view(d) for d in case.documents],
        "asset_map": asset_map_view(case),
        "facts": case.facts.model_dump(),
        "questions": [q.model_dump(mode="json") for q in case.questions],
        "plan": case.plan.model_dump(mode="json") if case.plan else None,
        "letters": [l.model_dump(mode="json") for l in case.letters],
        "activity_summary": services.activity_summary(case),
        "activity": [a.model_dump(mode="json") for a in case.activity],
    }


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

@app.post("/api/cases", status_code=201)
def create_case(body: CaseCreate, storage: Storage = Depends(get_storage)):
    return case_view(storage.create_case(Case(**body.model_dump())))


@app.post("/api/demo", status_code=201)
def create_demo_case(storage: Storage = Depends(get_storage)):
    """The 'Try with a demo family' button: a synthetic case with the 9 demo documents uploaded."""
    return case_view(services.create_demo_case(storage))


@app.get("/api/cases/{case_id}")
def get_case(case: Case = Depends(load_case)):
    return case_view(case)


@app.patch("/api/cases/{case_id}")
def update_case(body: CaseUpdate, case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    changes = body.model_dump(exclude_unset=True, exclude_none=True)

    def mutate(c: Case):
        for key, value in changes.items():
            setattr(c, key, value)

    return case_view(storage.update_case(case.id, mutate))


@app.delete("/api/cases/{case_id}", status_code=204)
def delete_case(case_id: str, storage: Storage = Depends(get_storage)):
    """'Delete my data': removes the case record and every uploaded file."""
    storage.delete_case(case_id)
    return Response(status_code=204)


# --- documents ---------------------------------------------------------------

def _content_type(upload: UploadFile) -> str:
    declared = (upload.content_type or "").lower()
    if declared in SUPPORTED_MIME_TYPES:
        return declared
    guessed, _ = mimetypes.guess_type(upload.filename or "")
    return (guessed or declared or "application/octet-stream").lower()


MAX_FILES_PER_UPLOAD = 20  # every file is held in memory until all are checked


# Plain `def` so FastAPI runs it on a worker thread: storage calls block and would stall every other request.
@app.post("/api/cases/{case_id}/documents", status_code=201)
def upload_documents(
    files: list[UploadFile], case: Case = Depends(load_case), storage: Storage = Depends(get_storage)
):
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(413, f"Please upload at most {MAX_FILES_PER_UPLOAD} files at a time.")
    limit = get_settings().max_upload_bytes
    prepared = []
    for upload in files:
        content_type = _content_type(upload)
        if content_type not in SUPPORTED_MIME_TYPES:
            raise HTTPException(415, f"{upload.filename}: please upload a photo (PNG/JPEG/WEBP/HEIC) or a PDF.")
        data = upload.file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"{upload.filename} is larger than {limit // (1024 * 1024)} MB.")
        if not data:
            raise HTTPException(400, f"{upload.filename} is empty.")
        prepared.append((upload.filename or "upload", content_type, data))
    return [document_view(services.add_document(storage, case.id, *item)) for item in prepared]


@app.get("/api/cases/{case_id}/documents")
def list_documents(case: Case = Depends(load_case)):
    return [document_view(d) for d in case.documents]


@app.post("/api/cases/{case_id}/documents/{document_id}/extract")
def extract_one(document_id: str, case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    if case.get_document(document_id) is None:
        raise HTTPException(404, "Document not found")
    try:
        return document_view(services.extract_case_document(storage, case.id, document_id))
    except ExtractionError as exc:
        raise HTTPException(502, str(exc))


@app.post("/api/cases/{case_id}/extract")
def extract_all(case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    """Extract every pending document. Per-file failures are recorded on each document (status=failed)."""
    return case_view(services.extract_pending(storage, case.id))


# --- asset map -----------------------------------------------------------------

class StatusChange(BaseModel):
    status: ItemStatus  # "rejected" is shown to families as "Not applicable"


class InferenceResponse(BaseModel):
    run: InferenceRun
    asset_map: dict


@app.get("/api/cases/{case_id}/asset-map")
def get_asset_map(case: Case = Depends(load_case)):
    return asset_map_view(case)


@app.post("/api/cases/{case_id}/infer", response_model=InferenceResponse)
def infer_hidden_assets(case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    try:
        run = services.run_inference(storage, case.id)
    except InferenceError as exc:
        raise HTTPException(502, str(exc))
    return InferenceResponse(run=run, asset_map=asset_map_view(storage.get_case(case.id)))


@app.post("/api/cases/{case_id}/items/{item_id}/status")
def change_item_status(item_id: str, body: StatusChange, case: Case = Depends(load_case),
                       storage: Storage = Depends(get_storage)):
    if case.get_item(item_id) is None:
        raise HTTPException(404, "Item not found")
    return asset_map_view(services.set_item_status(storage, case.id, item_id, body.status))


# --- agent ---------------------------------------------------------------------

class AgentMessage(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def _agent_response(storage: Storage, case_id: str, message: str):
    try:
        result = run_agent(storage, case_id, message)
    except AgentError as exc:
        raise HTTPException(502, str(exc))
    return {"reply": result.reply, "run_id": result.run_id, "steps": result.steps,
            "stopped_early": result.stopped_early, "case": case_view(storage.get_case(case_id))}


@app.post("/api/cases/{case_id}/analyse")
def analyse(case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    """Run the Saath agent over the whole case: extract, infer, look up procedures, ask, plan, draft letters."""
    return _agent_response(storage, case.id, ANALYSE_MESSAGE)


@app.post("/api/cases/{case_id}/agent")
def agent_message(body: AgentMessage, case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    return _agent_response(storage, case.id, body.message)


# --- questions, plan, letters --------------------------------------------------

class Answer(BaseModel):
    answer: str = Field(min_length=1, max_length=500)


class TaskStatus(BaseModel):
    board_status: BoardStatus


class LetterEdit(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    body: str = Field(min_length=1, max_length=20000)


class LetterRequest(BaseModel):
    item_id: str


@app.post("/api/cases/{case_id}/questions/generate")
def generate_questions(case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    try:
        services.generate_questions(storage, case.id)
    except QuestionError as exc:
        raise HTTPException(502, str(exc))
    return case_view(storage.get_case(case.id))


@app.post("/api/cases/{case_id}/questions/{question_id}/answer")
def answer_question(question_id: str, body: Answer, case: Case = Depends(load_case),
                    storage: Storage = Depends(get_storage)):
    if case.get_question(question_id) is None:
        raise HTTPException(404, "Question not found")
    return case_view(services.answer_question(storage, case.id, question_id, body.answer))


@app.post("/api/cases/{case_id}/plan")
def build_plan(case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    return case_view(services.make_plan(storage, case.id))


@app.patch("/api/cases/{case_id}/plan/tasks/{task_id}")
def update_task(task_id: str, body: TaskStatus, case: Case = Depends(load_case),
                storage: Storage = Depends(get_storage)):
    try:
        return case_view(services.set_task_status(storage, case.id, task_id, body.board_status))
    except KeyError:
        raise HTTPException(404, "Task not found")


@app.post("/api/cases/{case_id}/letters", status_code=201, response_model=Letter)
def create_letter(body: LetterRequest, case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    if case.get_item(body.item_id) is None:
        raise HTTPException(404, "Item not found")
    return services.make_letter(storage, case.id, body.item_id)


@app.put("/api/cases/{case_id}/letters/{letter_id}", response_model=Letter)
def edit_letter(letter_id: str, body: LetterEdit, case: Case = Depends(load_case),
                storage: Storage = Depends(get_storage)):
    if case.get_letter(letter_id) is None:
        raise HTTPException(404, "Letter not found")
    return services.edit_letter(storage, case.id, letter_id, body.title, body.body)


@app.get("/api/cases/{case_id}/letters/{letter_id}/pdf")
def download_letter(letter_id: str, case: Case = Depends(load_case)):
    letter = case.get_letter(letter_id)
    if letter is None:
        raise HTTPException(404, "Letter not found")
    filename = "saath-letter-" + "".join(ch for ch in letter.institution.lower() if ch.isalnum())[:30] + ".pdf"
    return Response(letter_pdf(letter), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# --- read-only share link ------------------------------------------------------

@app.post("/api/cases/{case_id}/share")
def create_share_link(case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    return {"share_token": services.ensure_share_token(storage, case.id)}


@app.get("/api/share/{token}")
def shared_board(token: str, storage: Storage = Depends(get_storage)):
    """Read-only family board: plan progress and masked asset names. No documents, letters or evidence."""
    case = storage.find_by_share_token(token)
    if case is None:
        raise HTTPException(404, "This link is not valid any more")
    tasks = case.plan.tasks if case.plan else []
    return {
        "deceased_name": case.deceased_name, "language": case.language,
        "tasks": [{"id": t.id, "order": t.order, "institution": t.institution, "first_step": t.first_step,
                   "board_status": t.board_status, "needs_confirmation": t.needs_confirmation,
                   "items": [{"type": i.type, "status": i.status, "identifier_masked": i.identifier_masked}
                             for i in t.items]} for t in tasks],
        "updated_at": case.updated_at,
    }


# --- frontend (built by `npm run build` into frontend/dist) -------------------

DIST = REPO_ROOT / "frontend" / "dist"


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "Not found")
    target = (DIST / path).resolve()
    if path and target.is_file() and DIST.resolve() in target.parents:
        return FileResponse(target)
    index = DIST / "index.html"
    if index.exists():
        return FileResponse(index)  # single-page app: let the client router handle it
    return Response("Frontend not built. Run: cd frontend && npm install && npm run build", media_type="text/plain")
