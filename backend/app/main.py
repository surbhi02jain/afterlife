"""Virasat API. Also serves the built frontend (frontend/dist) so the app ships as one container."""

import hashlib
import hmac
import mimetypes
import secrets

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import kb
from agent.loop import ANALYSE_MESSAGE, AgentError, run_agent
from app import demo, services
from app.config import REPO_ROOT, get_settings
from app.models import BoardStatus, Case, CaseCreate, CaseUpdate, Document, InferenceRun, ItemStatus, Letter
from storage import CaseNotFound, Storage, get_storage
from tools.asset_map import asset_map_view
from tools.extraction import SUPPORTED_MIME_TYPES, ExtractionError
from tools.finance import could_be_same_person
from tools.inference import InferenceError
from tools.letters import letter_pdf
from tools.memories import AUDIO_MIME_TYPES, MAX_TYPED_CHARS, MemoryReadError
from tools.names import NameCheckError
from tools.replies import ReplyError
from tools.pdf import WrongPassword
from tools.questions import QuestionError

app = FastAPI(title="Virasat", version="0.3.0")


def _key_cookie(case_id: str) -> str:
    return f"afterlife_case_{case_id}"


def _key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def load_case(case_id: str, request: Request, storage: Storage = Depends(get_storage)) -> Case:
    """A case opens only in the browser that created it, so a copied or forwarded link shows nothing.
    A wrong or missing key gets the same 404 as a case that doesn't exist: no hint that it does.
    Cases from before keys existed (no hash) stay open."""
    try:
        case = storage.get_case(case_id)
    except CaseNotFound:
        raise HTTPException(404, "Case not found")
    key = request.cookies.get(_key_cookie(case.id), "")
    if case.owner_key_hash and not hmac.compare_digest(_key_hash(key), case.owner_key_hash):
        raise HTTPException(404, "Case not found")
    return case


def _give_key(storage: Storage, case: Case, request: Request, response: Response) -> Case:
    """Issue the case's private key to this browser: a cookie page scripts can't read, sent only to this case's
    own API routes and only from this site. Only its hash is stored."""
    key = secrets.token_urlsafe(32)
    case = storage.update_case(case.id, lambda c: setattr(c, "owner_key_hash", _key_hash(key)))
    https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"  # Cloud Run terminates TLS
    response.set_cookie(_key_cookie(case.id), key, max_age=365 * 24 * 3600, path=f"/api/cases/{case.id}",
                        httponly=True, samesite="strict", secure=https)
    return case


def document_view(d: Document, deceased_name: str) -> dict:
    e = d.extraction
    # a flag for the family to check (wrong file, or someone else's papers), never a block
    other_holder = e.holder_name if e and not could_be_same_person(e.holder_name, deceased_name) else None
    return {"id": d.id, "filename": d.filename, "content_type": d.content_type, "status": d.status, "error": d.error, "size_bytes": d.size_bytes,
            "document_type": e.document_type.value if e else None, "institution": e.institution if e else None,
            "transactions": len(e.transactions) if e else 0, "confidence": e.confidence if e else None,
            "saved_reading": bool(d.extracted_with_model and d.extracted_with_model.endswith("(recorded)")),
            "other_holder": other_holder}


def case_view(case: Case) -> dict:
    """What the app shows. Raw extractions and storage keys stay server-side."""
    return {
        "id": case.id, "deceased_name": case.deceased_name, "date_of_death": case.date_of_death.isoformat(),
        "relationship": case.relationship, "language": case.language, "is_demo": case.is_demo,
        "created_at": case.created_at, "updated_at": case.updated_at,
        "documents": [document_view(d, case.deceased_name) for d in case.documents],
        "asset_map": asset_map_view(case),
        "facts": case.facts.model_dump(),
        "questions": [q.model_dump(mode="json") for q in case.questions],
        "plan": case.plan.model_dump(mode="json") if case.plan else None,
        "letters": [l.model_dump(mode="json") for l in case.letters],
        "memories": [m.model_dump(mode="json") for m in case.memories],
        "name_check": case.name_check.model_dump(mode="json") if case.name_check else None,
        "name_guidance": kb.lookup("name_mismatch", case.language) if case.name_check and case.name_check.issues else None,
        "replies": [r.model_dump(mode="json") for r in case.replies],
        "samples": {"memory": demo.SAMPLE_MEMORY.name, "replies": demo.sample_replies_by_task(case)}
        if case.is_demo else None,
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
def create_case(body: CaseCreate, request: Request, response: Response, storage: Storage = Depends(get_storage)):
    case = storage.create_case(Case(**body.model_dump()))
    return case_view(_give_key(storage, case, request, response))


@app.post("/api/demo", status_code=201)
def create_demo_case(request: Request, response: Response, storage: Storage = Depends(get_storage)):
    """The 'Try with a demo family' button: a synthetic case with the 9 demo documents uploaded."""
    return case_view(_give_key(storage, services.create_demo_case(storage), request, response))


@app.get("/api/cases/{case_id}")
def get_case(case: Case = Depends(load_case)):
    return case_view(case)


@app.patch("/api/cases/{case_id}")
def update_case(body: CaseUpdate, case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    return case_view(services.update_case_details(storage, case.id, changes))


@app.post("/api/cases/{case_id}/leave", status_code=204)
def leave_case(case: Case = Depends(load_case)):
    """'Leave this case on this device' (a shared computer): this browser forgets the key. The case stays, but since
    only the creating browser held the key, nobody can open it again; the screen says so before asking."""
    response = Response(status_code=204)
    response.delete_cookie(_key_cookie(case.id), path=f"/api/cases/{case.id}", httponly=True, samesite="strict")
    return response


@app.delete("/api/cases/{case_id}", status_code=204)
def delete_case(case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    """'Delete my data': removes the case record and every uploaded file. Only the case's own browser can."""
    storage.delete_case(case.id)
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
    return [document_view(services.add_document(storage, case.id, *item), case.deceased_name) for item in prepared]


@app.get("/api/cases/{case_id}/documents")
def list_documents(case: Case = Depends(load_case)):
    return [document_view(d, case.deceased_name) for d in case.documents]


@app.delete("/api/cases/{case_id}/documents/{document_id}")
def remove_document(document_id: str, case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    """Remove one upload: its file, its extraction and anything only it proved. Returns the updated case."""
    if case.get_document(document_id) is None:
        raise HTTPException(404, "Document not found")
    try:
        return case_view(services.remove_document(storage, case.id, document_id))
    except KeyError:
        raise HTTPException(404, "Document not found")


class UnlockBody(BaseModel):
    password: str = Field(min_length=1, max_length=200)


@app.get("/api/cases/{case_id}/documents/{document_id}/file")
def document_file(document_id: str, case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    """The uploaded file itself, so the family can see what they sent. Behind the same private case key."""
    doc = case.get_document(document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    try:
        data = storage.read_file(doc.storage_key)
    except FileNotFoundError:
        raise HTTPException(410, "This file is no longer stored (uploads are deleted after 24 hours).")
    # content_type was checked against SUPPORTED_MIME_TYPES at upload; no-store keeps it out of a shared computer's cache
    return Response(data, media_type=doc.content_type, headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Disposition": "inline"})


@app.post("/api/cases/{case_id}/documents/{document_id}/unlock")
def unlock_document(document_id: str, body: UnlockBody, case: Case = Depends(load_case),
                    storage: Storage = Depends(get_storage)):
    """Open a password-protected PDF with the password the family types. The password is never stored."""
    try:
        return document_view(services.unlock_document(storage, case.id, document_id, body.password), case.deceased_name)
    except KeyError:
        raise HTTPException(404, "Document not found")
    except WrongPassword as exc:
        raise HTTPException(400, str(exc))
    except FileNotFoundError:
        raise HTTPException(410, "This file is no longer stored (uploads are deleted after 24 hours). "
                                 "Please upload it again.")


@app.post("/api/cases/{case_id}/documents/{document_id}/extract")
def extract_one(document_id: str, case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    if case.get_document(document_id) is None:
        raise HTTPException(404, "Document not found")
    try:
        return document_view(services.extract_case_document(storage, case.id, document_id), case.deceased_name)
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
    """Run the Virasat agent over the whole case: extract, infer, look up procedures, ask, plan, draft letters."""
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
    filename = "virasat-letter-" + "".join(ch for ch in letter.institution.lower() if ch.isalnum())[:30] + ".pdf"
    return Response(letter_pdf(letter), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# --- family memories, name check, replies from institutions ---------------------

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # about 5 minutes of the 16 kHz WAV the app records


def _audio_type(upload: UploadFile) -> str:
    declared = (upload.content_type or "").split(";")[0].strip().lower()
    return declared or (mimetypes.guess_type(upload.filename or "")[0] or "").lower()


@app.post("/api/cases/{case_id}/memories", status_code=201)
def add_memory(audio: UploadFile | None = None, text: str | None = Form(default=None, max_length=MAX_TYPED_CHARS),
               case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    """What the family remembers: a voice recording, or typed text. The recording is never stored."""
    if (audio is None) == (not text or not text.strip()):
        raise HTTPException(400, "Please record a message or type what you remember (one of the two).")
    data, mime = None, None
    if audio is not None:
        mime = _audio_type(audio)
        if mime not in AUDIO_MIME_TYPES:
            raise HTTPException(415, "Please record again: this kind of recording can't be read.")
        data = audio.file.read(MAX_AUDIO_BYTES + 1)
        if len(data) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "The recording is too long. Please keep it under 5 minutes.")
        if not data:
            raise HTTPException(400, "The recording is empty.")
    try:
        memory = services.add_memory(storage, case.id, audio=data, mime_type=mime,
                                     text=text.strip() if text and audio is None else None)
    except MemoryReadError as exc:
        raise HTTPException(502, str(exc))
    return {"memory": memory.model_dump(mode="json"), "case": case_view(storage.get_case(case.id))}


@app.post("/api/cases/{case_id}/name-check")
def check_names(case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    try:
        services.check_names(storage, case.id)
    except NameCheckError as exc:
        raise HTTPException(502, str(exc))
    return case_view(storage.get_case(case.id))


@app.post("/api/cases/{case_id}/plan/tasks/{task_id}/replies", status_code=201)
def add_reply(task_id: str, file: UploadFile, case: Case = Depends(load_case), storage: Storage = Depends(get_storage)):
    """A reply the institution sent back (letter, email, SMS screenshot). Read, acted on, and not stored."""
    content_type = _content_type(file)
    if content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(415, f"{file.filename}: please upload a photo (PNG/JPEG/WEBP/HEIC) or a PDF.")
    limit = get_settings().max_upload_bytes
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"{file.filename} is larger than {limit // (1024 * 1024)} MB.")
    if not data:
        raise HTTPException(400, f"{file.filename} is empty.")
    try:
        reply = services.add_reply(storage, case.id, task_id, file.filename or "reply", content_type, data)
    except KeyError:
        raise HTTPException(404, "Task not found. Please prepare the plan first.")
    except ReplyError as exc:
        raise HTTPException(502, str(exc))
    return {"reply": reply.model_dump(mode="json"), "case": case_view(storage.get_case(case.id))}


class RequirementDone(BaseModel):
    done: bool


@app.patch("/api/cases/{case_id}/replies/{reply_id}/requirements/{requirement_id}")
def set_requirement(reply_id: str, requirement_id: str, body: RequirementDone, case: Case = Depends(load_case),
                    storage: Storage = Depends(get_storage)):
    try:
        return case_view(services.set_requirement(storage, case.id, reply_id, requirement_id, body.done))
    except KeyError:
        raise HTTPException(404, "Not found")


@app.get("/api/demo/samples/{name}")
def demo_sample(name: str):
    """The sample family's recording and reply letters, so the demo can be tried without your own files."""
    allowed = {demo.SAMPLE_MEMORY.name: demo.SAMPLE_MEMORY,
               **{n: demo.SAMPLES_DIR / n for n in demo.SAMPLE_REPLIES}}
    path = allowed.get(name)
    if path is None or not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(path)


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
