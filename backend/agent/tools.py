"""The agent's tools: Gemini function declarations + dispatch to the shared services.

Tool results are compact JSON with masked identifiers only. Every call is logged by the services layer.
"""

from dataclasses import dataclass

from google.genai import types

from app import services
from app.models import AssetType, Case, LiabilityType
from storage import Storage
from tools.extraction import ExtractionError
from tools.inference import InferenceError
from tools.names import NameCheckError
from tools.questions import QuestionDraft, find_gaps

ASSET_TYPES = list(AssetType.__args__)
LIABILITY_TYPES = list(LiabilityType.__args__)


def _obj(properties: dict | None = None, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties or {}, "required": required or []}


DECLARATIONS = [
    types.FunctionDeclaration(
        name="extract_document",
        description="Read one uploaded document (photo/PDF) and add what it shows to the asset map.",
        parameters_json_schema=_obj({"document_id": {"type": "string"}}, ["document_id"]),
    ),
    types.FunctionDeclaration(
        name="infer_hidden_assets",
        description="Look through all extracted transactions for assets or loans that probably exist but have no "
                    "document. Adds them as PROBABLE items with evidence. Call once after documents are read.",
        parameters_json_schema=_obj(),
    ),
    types.FunctionDeclaration(
        name="check_names",
        description="Compare how the deceased's and nominees' names are written across the documents. Institutions "
                    "often delay claims over differences, so the family should know early. Call once after documents "
                    "are read.",
        parameters_json_schema=_obj(),
    ),
    types.FunctionDeclaration(
        name="add_asset",
        description="Record an asset the FAMILY mentioned in their message (not something you guessed). It is "
                    "added as probable until confirmed.",
        parameters_json_schema=_obj({
            "type": {"type": "string", "enum": ASSET_TYPES},
            "institution": {"type": "string"},
            "family_statement": {"type": "string", "description": "What the family said, briefly quoted."},
        }, ["type", "institution", "family_statement"]),
    ),
    types.FunctionDeclaration(
        name="add_liability",
        description="Record a loan or card the FAMILY mentioned in their message. Added as probable.",
        parameters_json_schema=_obj({
            "type": {"type": "string", "enum": LIABILITY_TYPES},
            "institution": {"type": "string"},
            "family_statement": {"type": "string"},
        }, ["type", "institution", "family_statement"]),
    ),
    types.FunctionDeclaration(
        name="lookup_procedure",
        description="Get the claim procedure for an item type from the knowledge base. Base ALL procedural advice "
                    "on this. Returns found=false when there is nothing on file.",
        parameters_json_schema=_obj({"item_type": {"type": "string", "enum": [*ASSET_TYPES, *LIABILITY_TYPES,
                                                                               "general"]}}, ["item_type"]),
    ),
    types.FunctionDeclaration(
        name="ask_user",
        description="Ask the family 2 to 4 gentle follow-up questions about gaps. Use only gap ids listed in the "
                    "case context. Questions appear in the app for them to answer later; do not wait for answers.",
        parameters_json_schema=_obj({
            "questions": {"type": "array", "items": _obj({
                "gap_id": {"type": "string"},
                "text": {"type": "string", "description": "One warm, plain sentence in the case language."},
                "why": {"type": "string", "description": "Very short reason, in the case language."},
            }, ["gap_id", "text", "why"])},
        }, ["questions"]),
    ),
    types.FunctionDeclaration(
        name="build_action_plan",
        description="Build the ordered, per-institution checklist from the asset map and the knowledge base.",
        parameters_json_schema=_obj(),
    ),
    types.FunctionDeclaration(
        name="generate_letter",
        description="Draft a letter for one item: a claim letter for a confirmed item, or a request to confirm "
                    "whether it exists for a probable item.",
        parameters_json_schema=_obj({"item_id": {"type": "string"}}, ["item_id"]),
    ),
]

@dataclass
class ToolContext:
    storage: Storage
    case_id: str
    run_id: str
    client: object = None  # only used for extraction/inference; the agent's own client is separate

    def case(self) -> Case:
        return self.storage.get_case(self.case_id)


def item_summary(item) -> dict:
    return {"item_id": item.id, "status": item.status, "type": item.type, "institution": item.institution,
            "identifier": item.identifier_masked, "amount": item.amount, "nominee": item.nominee,
            "confidence": item.confidence}


def gap_summary(case: Case) -> list[dict]:
    return [{"gap_id": g.id, "about": g.fact} for g in find_gaps(case)]


def dispatch(ctx: ToolContext, name: str, args: dict) -> dict:
    """Run one tool call. Errors are returned to the model (and logged by services), never raised."""
    s, cid, rid = ctx.storage, ctx.case_id, ctx.run_id
    try:
        if name == "extract_document":
            doc = ctx.case().get_document(str(args.get("document_id", "")))
            if doc is None:
                return {"error": "No document with that id."}
            if doc.status == "extracted":
                return {"document_id": doc.id, "status": "already extracted"}
            doc = services.extract_case_document(s, cid, doc.id, client=ctx.client, run_id=rid)
            e = doc.extraction
            return {"document_id": doc.id, "filename": doc.filename, "status": doc.status,
                    "document_type": e.document_type.value, "institution": e.institution,
                    "transactions": len(e.transactions)}

        if name == "infer_hidden_assets":
            run = services.run_inference(s, cid, client=ctx.client, run_id=rid)
            case = ctx.case()
            return {"added": [item_summary(case.get_item(i)) | {"reason": case.get_item(i).reason,
                                                                "evidence_count": len(case.get_item(i).evidence)}
                              for i in run.added],
                    "merged_into_existing": len(run.merged), "discarded": run.discarded,
                    "open_gaps": gap_summary(case)}

        if name == "check_names":
            check = services.check_names(s, cid, client=ctx.client, run_id=rid)
            return {"names_compared": check.compared,
                    "differences": [{"kind": i.kind, "names": [n["name"] for n in i.names], "explanation": i.explanation}
                                    for i in check.issues],
                    "note": "The Plan screen shows these with what to do (from the knowledge base)."}

        if name in ("add_asset", "add_liability"):
            item_type = str(args.get("type", ""))
            allowed = ASSET_TYPES if name == "add_asset" else LIABILITY_TYPES
            if item_type not in allowed:
                return {"error": f"type must be one of {allowed}"}
            item = services.add_family_item(s, cid, item_type, str(args.get("institution", "")).strip(),
                                            str(args.get("family_statement", "")).strip(), run_id=rid)
            return item_summary(item)

        if name == "lookup_procedure":
            return services.lookup_procedure(s, cid, str(args.get("item_type", "")), run_id=rid)

        if name == "ask_user":
            drafts = [QuestionDraft.model_validate(q) for q in args.get("questions", []) if isinstance(q, dict)]
            created = services.ask_questions(s, cid, drafts, run_id=rid)
            return {"created": [{"question_id": q.id, "text": q.text} for q in created],
                    "ignored": len(drafts) - len(created),
                    "note": "Questions with unknown gap ids are ignored."}

        if name == "build_action_plan":
            plan = services.make_plan(s, cid, run_id=rid).plan
            return {"tasks": [{"order": t.order, "institution": t.institution, "first_step": t.first_step,
                               "time_sensitive": t.time_sensitive, "needs_confirmation": t.needs_confirmation,
                               "item_ids": [i.item_id for i in t.items]} for t in plan.tasks],
                    "disclaimer": plan.disclaimer}

        if name == "generate_letter":
            item_id = str(args.get("item_id", ""))
            if ctx.case().get_item(item_id) is None:
                return {"error": "No item with that id."}
            letter = services.make_letter(s, cid, item_id, run_id=rid)
            return {"letter_id": letter.id, "title": letter.title, "kind": letter.kind}

        return {"error": f"Unknown tool {name}"}
    except (ExtractionError, InferenceError, NameCheckError) as exc:
        return {"error": str(exc)}
    except (KeyError, ValueError) as exc:
        services.record(s, cid, name, f"A step ({name}) didn't work", f"एक चरण ({name}) पूरा नहीं हुआ", ok=False,
                        run_id=rid, error=str(exc))
        return {"error": f"{type(exc).__name__}: {exc}"}
