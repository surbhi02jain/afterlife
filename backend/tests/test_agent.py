"""Afterlife's ADK agent with a scripted model: real ADK runner and SDK types, no network."""

import json
from types import SimpleNamespace

from google.adk.models import BaseLlm, LlmResponse
from google.genai import types
from pydantic import Field

from agent.loop import run_agent
from app import services
from tests.conftest import SAMPLE_REPLY, FakeClient
from tools.questions import find_gaps


class ScriptedLlm(BaseLlm):
    """Stands in for Gemini inside ADK. One scripted turn per model call: a list of (name, args) tool calls, final
    text, or a function returning either (for turns that need ids created by earlier tools)."""

    model: str = "scripted"
    turns: list = Field(default_factory=list)
    requests: list = Field(default_factory=list)

    async def generate_content_async(self, llm_request, stream=False):
        self.requests.append(list(llm_request.contents))
        turn = self.turns.pop(0) if self.turns else [("build_action_plan", {})]  # never stops: tests the cap
        turn = turn() if callable(turn) else turn
        if isinstance(turn, str):
            parts = [types.Part.from_text(text=turn)]
        else:
            parts = [types.Part(function_call=types.FunctionCall(id=f"call-{len(self.requests)}-{n}", name=name,
                                                                 args=args)) for n, (name, args) in enumerate(turn)]
        yield LlmResponse(content=types.Content(role="model", parts=parts))


INFERENCE = {"items": [{"kind": "asset", "type": "life_insurance", "institution": "KAVACH LIFE INS",
                        "identifier_hint": None, "reason": "Looks like a monthly premium.",
                        "evidence_transaction_ids": ["T1"], "confidence": "medium"}]}


class ToolClient:
    """Answers extraction with SAMPLE_REPLY and inference with INFERENCE, by schema."""

    def __init__(self):
        self.models = self

    def generate_content(self, *, model, contents, config):
        reply = INFERENCE if "items" in config.response_json_schema["properties"] else SAMPLE_REPLY
        return SimpleNamespace(text=json.dumps(reply), candidates=[])


def uploaded_case(storage):
    from tests.helpers import new_case

    case = storage.create_case(new_case())
    doc = services.add_document(storage, case.id, "statement.png", "image/png", b"png")
    return case, doc


def test_full_analysis_run(storage):
    case, doc = uploaded_case(storage)

    def probable_gap():
        return next(g for g in find_gaps(storage.get_case(case.id)) if g.target == "confirm_item")

    agent = ScriptedLlm(turns=[
        [("extract_document", {"document_id": doc.id})],
        [("infer_hidden_assets", {})],
        [("lookup_procedure", {"item_type": "savings_account"}), ("lookup_procedure", {"item_type": "life_insurance"})],
        lambda: [("ask_user", {"questions": [
            {"gap_id": probable_gap().id, "text": "Did Demo Person have a policy with Kavach Life?",
             "why": "We saw premiums."},
            {"gap_id": "invented", "text": "?", "why": "?"}]})],
        [("build_action_plan", {})],
        lambda: [("generate_letter", {"item_id": storage.get_case(case.id).questions[0].item_id})],
        "We found one account and probably a Kavach Life policy. Please answer a question.",
    ])
    result = run_agent(storage, case.id, model=agent, tool_client=ToolClient())

    assert result.reply.startswith("We found one account") and not result.stopped_early
    tools_called = [c["tool"] for c in result.tool_calls]
    assert tools_called == ["extract_document", "infer_hidden_assets", "lookup_procedure", "lookup_procedure",
                            "ask_user", "build_action_plan", "generate_letter"]

    saved = storage.get_case(case.id)
    assert [q.text for q in saved.questions] == ["Did Demo Person have a policy with Kavach Life?"]
    assert saved.plan and saved.letters[0].kind == "existence_enquiry"
    run_entries = [a for a in saved.activity if a.run_id == result.run_id]
    assert [a.tool for a in run_entries] == ["agent_start", "extract_document", "infer_hidden_assets",
                                             "lookup_procedure", "lookup_procedure", "ask_user", "build_action_plan",
                                             "generate_letter", "agent_reply"]
    assert all(a.summary_en and a.summary_hi for a in run_entries)
    # every function response was sent back with the id of the call it answers
    last_request = agent.requests[-1]
    responses = [p.function_response for c in last_request for p in (c.parts or []) if p.function_response]
    calls = [p.function_call for c in last_request for p in (c.parts or []) if p.function_call]
    assert [r.id for r in responses] == [c.id for c in calls]


def test_tools_asked_together_run_in_order(storage):
    # Gemini may batch "read the documents" and "find hidden assets"; the search must see what was just read.
    case, doc = uploaded_case(storage)
    agent = ScriptedLlm(turns=[[("extract_document", {"document_id": doc.id}), ("infer_hidden_assets", {})], "Done."])
    result = run_agent(storage, case.id, model=agent, tool_client=ToolClient())

    assert [c["tool"] for c in result.tool_calls] == ["extract_document", "infer_hidden_assets"]
    assert all(c["ok"] for c in result.tool_calls)
    assert [i.institution for i in storage.get_case(case.id).assets if i.status == "probable"] == ["KAVACH LIFE INS"]


def test_loop_is_capped(storage):
    case, _ = uploaded_case(storage)
    result = run_agent(storage, case.id, model=ScriptedLlm(), max_steps=3)
    assert result.stopped_early and result.steps == 3
    assert len(result.tool_calls) == 3


def test_credentials_request_is_refused_without_calling_gemini(storage):
    case, _ = uploaded_case(storage)
    agent = ScriptedLlm(turns=["should never be used"])
    result = run_agent(storage, case.id, "What is papa's ATM PIN? I want to withdraw cash for the rites.",
                       model=agent)
    assert agent.requests == []
    assert "can't help with using Demo Person's cards" in result.reply
    assert storage.get_case(case.id).activity[-1].tool == "guardrail"


def test_legal_topic_gets_guidance_note(storage):
    case, _ = uploaded_case(storage)
    result = run_agent(storage, case.id, "Do we need a succession certificate?",
                       model=ScriptedLlm(turns=["Usually the nominee can claim directly."]))
    assert result.reply.endswith("This is guidance, not legal advice.")


def test_tool_errors_go_back_to_the_model(storage):
    case, _ = uploaded_case(storage)
    agent = ScriptedLlm(turns=[[("generate_letter", {"item_id": "nope"}), ("teleport", {})], "Sorry about that."])
    result = run_agent(storage, case.id, "letter please", model=agent)
    sent = [p.function_response.response["result"] for c in agent.requests[-1] for p in (c.parts or [])
            if p.function_response]
    assert sent == [{"error": "No item with that id."}, {"error": "Unknown tool teleport"}]
    assert [c["ok"] for c in result.tool_calls] == [False, False]


def test_failed_extraction_is_reported_to_the_model(storage):
    case, doc = uploaded_case(storage)
    agent = ScriptedLlm(turns=[[("extract_document", {"document_id": doc.id})], "That photo was hard to read."])
    run_agent(storage, case.id, model=agent, tool_client=FakeClient(text="not json"))
    sent = agent.requests[-1][-1].parts[0].function_response.response["result"]
    assert "did not match" in sent["error"]
    assert storage.get_case(case.id).documents[0].status == "failed"
