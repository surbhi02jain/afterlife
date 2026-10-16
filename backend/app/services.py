"""Case operations shared by the API, the CLI scripts and the agent.

Every operation records a plain-language entry (English + Hindi) in the case's activity log, so the
"AI activity" panel is complete no matter whether the agent or the UI triggered it.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import kb
from app import demo
from app.gemini import GeminiNotConfigured
from app.models import ActivityEntry, Case, Document, InferenceRun, ItemStatus, Letter, Question, new_id
from storage import Storage
from tools.asset_map import refresh_recurring, sync_documents
from tools.extraction import ExtractionError, extract_document, parse_extraction
from tools.i18n import label
from tools.inference import InferenceError, apply_proposals, collect_transactions, propose
from tools.letters import draft_letter
from tools.plan import build_plan
from tools.questions import (QuestionError, add_questions, apply_answer, confirm_drafts_first, draft_questions,
                             find_gaps)


def log(case: Case, tool: str, en: str, hi: str, *, ok: bool = True, run_id: str | None = None, **detail) -> None:
    case.activity.append(ActivityEntry(tool=tool, ok=ok, summary_en=en, summary_hi=hi, run_id=run_id, detail=detail))


def record(storage: Storage, case_id: str, tool: str, en: str, hi: str, **kwargs) -> None:
    storage.update_case(case_id, lambda c: log(c, tool, en, hi, **kwargs))


# --- documents ---------------------------------------------------------------------------------------

def add_document(storage: Storage, case_id: str, filename: str, content_type: str, data: bytes) -> Document:
    doc = Document(filename=filename, content_type=content_type, size_bytes=len(data), storage_key="")
    doc.storage_key = storage.save_file(case_id, doc.id, data, content_type)
    storage.update_case(case_id, lambda case: case.documents.append(doc))
    return doc


def create_demo_case(storage: Storage) -> Case:
    case = storage.create_case(demo.new_demo_case())
    for path in demo.demo_documents():
        add_document(storage, case.id, path.name, "image/png", path.read_bytes())
    record(storage, case.id, "create_demo_case", "Loaded the sample family's 9 documents",
           "नमूना परिवार के 9 दस्तावेज़ लोड किए")
    return storage.get_case(case.id)


def extract_case_document(storage: Storage, case_id: str, document_id: str, *, client=None,
                          run_id: str | None = None) -> Document:
    """Run Gemini extraction for one document and record the outcome on the case.

    Raises ExtractionError (after recording status=failed) so callers never mistake a failure for data.
    """
    case = storage.get_case(case_id)
    doc = case.get_document(document_id)
    if doc is None:
        raise KeyError(document_id)

    def finish(**fields):
        def mutate(c: Case):
            target = c.get_document(document_id)
            for key, value in fields.items():
                setattr(target, key, value)
            if target.status == "extracted":
                sync_documents(c)  # fold the new document into the asset map
                saved = " (saved reading of the sample document)" if fields.get("extracted_with_model", "").endswith(
                    "(recorded)") else ""
                log(c, "extract_document", f"Read {target.filename}{saved}", f"{target.filename} पढ़ा",
                    run_id=run_id, document_id=document_id, document_type=target.extraction.document_type.value,
                    transactions=len(target.extraction.transactions))
            elif target.status == "failed":
                log(c, "extract_document", f"Couldn't read {target.filename}", f"{target.filename} पढ़ा नहीं जा सका",
                    ok=False, run_id=run_id, document_id=document_id, error=target.error)
        return storage.update_case(case_id, mutate).get_document(document_id)

    finish(status="extracting", error=None)
    data = storage.read_file(doc.storage_key)
    recorded = demo.recorded_reply(data) if case.is_demo and demo.replay_enabled() else None
    try:
        if recorded:
            document, model = parse_extraction(recorded["raw_response"]), f"{recorded['model']} (recorded)"
        else:
            result = extract_document(data, doc.content_type, client=client)
            document, model = result.document, result.model
    except (ExtractionError, GeminiNotConfigured) as exc:
        finish(status="failed", error=str(exc))
        raise ExtractionError(str(exc)) from exc
    return finish(status="extracted", error=None, extraction=document, extracted_with_model=model)


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


# --- asset map ---------------------------------------------------------------------------------------

def sync_asset_map(storage: Storage, case_id: str) -> Case:
    return storage.update_case(case_id, sync_documents)


def run_inference(storage: Storage, case_id: str, *, client=None, run_id: str | None = None) -> InferenceRun:
    """Ask Gemini for hidden assets (outside the case lock), then verify and merge them in."""
    case = storage.get_case(case_id)
    refs = collect_transactions(case)
    if not refs:
        raise InferenceError("There are no transactions to look through yet. Please add a statement or passbook.")
    try:
        result, model = propose(case, refs, client=client)
    except (InferenceError, GeminiNotConfigured) as exc:
        record(storage, case_id, "infer_hidden_assets", "Couldn't look for hidden assets just now",
               "अभी छिपी संपत्तियाँ नहीं खोजी जा सकीं", ok=False, run_id=run_id, error=str(exc))
        raise InferenceError(str(exc)) from exc

    runs = []

    def mutate(c: Case):
        run = apply_proposals(c, result, refs, model)
        n = len(run.added)
        log(c, "infer_hidden_assets", f"Found {n} probable asset{'s' if n != 1 else ''} that may need confirming",
            f"{n} संभावित संपत्तियाँ मिलीं जिनकी पुष्टि करनी है", run_id=run_id, added=n, merged=len(run.merged),
            discarded=len(run.discarded), transactions_checked=len(refs))
        runs.append(run)

    storage.update_case(case_id, mutate)
    return runs[-1]


def refresh_letters(c: Case) -> None:
    """Redraft letters the family hasn't edited, so new answers and confirmations show up in them."""
    for n, letter in enumerate(c.letters):
        if not letter.edited and c.get_item(letter.item_id):
            fresh = draft_letter(c, letter.item_id)
            fresh.id, fresh.created_at = letter.id, letter.created_at
            c.letters[n] = fresh


def set_item_status(storage: Storage, case_id: str, item_id: str, status: ItemStatus) -> Case:
    def mutate(c: Case):
        item = c.get_item(item_id)
        if item is None:
            raise KeyError(item_id)
        item.status = status
        item.decided_by_user = True
        refresh_recurring(c, date.today())
        if c.plan:
            c.plan = build_plan(c)
        refresh_letters(c)

    return storage.update_case(case_id, mutate)


def add_family_item(storage: Storage, case_id: str, item_type: str, institution: str, statement: str,
                    identifier_hint: str | None = None, run_id: str | None = None):
    """An asset/liability the family mentioned. Stays probable until a document or the family confirms it."""
    from app.models import Evidence
    from tools.asset_map import Candidate, upsert

    created = []

    def mutate(c: Case):
        cand = Candidate(type=item_type, institution=institution, identifier=identifier_hint, confidence="medium",
                         origin="family", reason=statement,
                         evidence=[Evidence(document_id="family", document_name="Family's note", description=statement)])
        item, _ = upsert(c, cand)
        log(c, "add_asset" if not cand.is_liability else "add_liability",
            f"Noted the {label(item_type, 'en')} at {institution} that the family mentioned",
            f"परिवार द्वारा बताया गया {label(item_type, 'hi')} ({institution}) नोट किया", run_id=run_id,
            item_id=item.id)
        created.append(item)

    storage.update_case(case_id, mutate)
    return created[0]


# --- procedures, questions, plan, letters ------------------------------------------------------------

def lookup_procedure(storage: Storage, case_id: str, item_type: str, run_id: str | None = None) -> dict:
    case = storage.get_case(case_id)
    result = kb.lookup(item_type, case.language)
    name_en, name_hi = label(item_type, "en"), label(item_type, "hi")
    if result["found"]:
        record(storage, case_id, "lookup_procedure", f"Looked up what to do for the {name_en}",
               f"{name_hi} के लिए कदम देखे", run_id=run_id, item_type=item_type, source=result["source_name"])
    else:
        record(storage, case_id, "lookup_procedure", f"No saved steps for the {name_en}; please confirm with the institution",
               f"{name_hi} के लिए कदम उपलब्ध नहीं; कृपया संस्था से पुष्टि करें", ok=False, run_id=run_id,
               item_type=item_type)
    return result


def _save_questions(storage: Storage, case_id: str, drafts, run_id: str | None) -> list[Question]:
    created = []

    def mutate(c: Case):
        gaps = find_gaps(c)
        created.extend(add_questions(c, gaps, confirm_drafts_first(c, gaps, drafts)))
        n = len(created)
        log(c, "ask_user", f"Prepared {n} question{'s' if n != 1 else ''} for the family",
            f"परिवार के लिए {n} प्रश्न तैयार किए", run_id=run_id, questions=n)

    storage.update_case(case_id, mutate)
    return created


def ask_questions(storage: Storage, case_id: str, drafts, run_id: str | None = None) -> list[Question]:
    """Used by the agent, which writes the question text itself (no extra model call)."""
    return _save_questions(storage, case_id, drafts, run_id)


def generate_questions(storage: Storage, case_id: str, *, client=None) -> list[Question]:
    """Used by the UI: Gemini phrases 2 to 4 of the deterministic gaps."""
    case = storage.get_case(case_id)
    gaps = find_gaps(case)
    if not gaps:
        return []
    try:
        drafts = draft_questions(case, gaps, client=client).questions
    except (QuestionError, GeminiNotConfigured) as exc:
        raise QuestionError(str(exc)) from exc
    return _save_questions(storage, case_id, drafts, None)


def answer_question(storage: Storage, case_id: str, question_id: str, answer: str) -> Case:
    def mutate(c: Case):
        q = apply_answer(c, question_id, answer)
        log(c, "answer_question", "Updated the case with the family's answer", "परिवार के उत्तर से जानकारी अपडेट की",
            question_id=q.id, target=q.target)
        refresh_recurring(c, date.today())
        if c.plan:
            c.plan = build_plan(c)
        refresh_letters(c)

    return storage.update_case(case_id, mutate)


def make_plan(storage: Storage, case_id: str, run_id: str | None = None) -> Case:
    def mutate(c: Case):
        c.plan = build_plan(c)
        n = len(c.plan.tasks)
        log(c, "build_action_plan", f"Prepared {n} step{'s' if n != 1 else ''} in a suggested order",
            f"सुझाए गए क्रम में {n} कदम तैयार किए", run_id=run_id, tasks=n)

    return storage.update_case(case_id, mutate)


def set_task_status(storage: Storage, case_id: str, task_id: str, status: str) -> Case:
    def mutate(c: Case):
        task = next((t for t in (c.plan.tasks if c.plan else []) if t.id == task_id), None)
        if task is None:
            raise KeyError(task_id)
        task.board_status = status

    return storage.update_case(case_id, mutate)


def make_letter(storage: Storage, case_id: str, item_id: str, run_id: str | None = None) -> Letter:
    """Draft (or redraft) the letter for an item. A letter the family has edited is never overwritten."""
    made = []

    def mutate(c: Case):
        existing = next((l for l in c.letters if l.item_id == item_id), None)
        if existing and existing.edited:
            made.append(existing)
            return
        letter = draft_letter(c, item_id)
        if existing:
            letter.id = existing.id
            c.letters[c.letters.index(existing)] = letter
        else:
            c.letters.append(letter)
        log(c, "generate_letter", f"Drafted a letter to {letter.institution}", f"{letter.institution} को पत्र तैयार किया",
            run_id=run_id, letter_id=letter.id, kind=letter.kind)
        made.append(letter)

    storage.update_case(case_id, mutate)
    return made[0]


def edit_letter(storage: Storage, case_id: str, letter_id: str, title: str | None, body: str) -> Letter:
    from app.models import utc_now

    def mutate(c: Case):
        letter = c.get_letter(letter_id)
        if letter is None:
            raise KeyError(letter_id)
        letter.body, letter.edited, letter.updated_at = body, True, utc_now()
        if title:
            letter.title = title

    return storage.update_case(case_id, mutate).get_letter(letter_id)


def ensure_share_token(storage: Storage, case_id: str) -> str:
    def mutate(c: Case):
        c.share_token = c.share_token or new_id()

    return storage.update_case(case_id, mutate).share_token


def activity_summary(case: Case) -> list[dict]:
    """The plain-language headline lines for the AI activity panel ('Read 6 documents', ...)."""
    lines = []
    read = sum(1 for d in case.documents if d.status == "extracted")
    if read:
        lines.append({"en": f"Read {read} document{'s' if read != 1 else ''}", "hi": f"{read} दस्तावेज़ पढ़े"})
    probable = sum(1 for i in [*case.assets, *case.liabilities] if i.status == "probable")
    if case.inference_runs:
        lines.append({"en": f"Found {probable} probable asset{'s' if probable != 1 else ''}",
                      "hi": f"{probable} संभावित संपत्तियाँ मिलीं"})
    open_q = sum(1 for q in case.questions if q.status == "open")
    if case.questions:
        lines.append({"en": f"{open_q} question{'s' if open_q != 1 else ''} waiting for you",
                      "hi": f"{open_q} प्रश्न आपके उत्तर की प्रतीक्षा में"})
    if case.plan:
        n = len(case.plan.tasks)
        lines.append({"en": f"Prepared {n} step{'s' if n != 1 else ''}", "hi": f"{n} कदम तैयार किए"})
    if case.letters:
        n = len(case.letters)
        lines.append({"en": f"Drafted {n} letter{'s' if n != 1 else ''}", "hi": f"{n} पत्र तैयार किए"})
    return lines
