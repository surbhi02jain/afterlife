"""Afterlife agent, built on Google's Agent Development Kit (ADK).

ADK runs the Gemini function-calling loop: it sends the case and the tools, runs the tools Gemini asks for (one by
one, in the order asked) and stops at MAX_STEPS model calls. Afterlife keeps what matters in its own code:
  - guardrails run before ADK is involved (credential requests never reach the model) and on the final reply;
  - every tool goes through agent.tools.dispatch(), which logs each step and returns errors to the model;
  - each model call waits for the per-model RPM throttle (GEMINI_RPM), like every other Gemini call in the app.
"""

import asyncio
import logging
from dataclasses import dataclass, field

from google.adk.agents import LlmAgent, RunConfig
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.models import BaseLlm, Gemini
from google.adk.runners import InMemoryRunner
from google.adk.tools import BaseTool
from google.genai import errors, types

from agent.guardrails import REFUSAL, asks_to_use_credentials, touches_legal_topic, with_legal_note
from agent.tools import DECLARATIONS, ToolContext, dispatch, gap_summary
from app import gemini, services
from app.config import get_settings
from app.gemini import GeminiNotConfigured
from app.models import Case, new_id
from storage import Storage
from tools.asset_map import debits_after_death
from tools.i18n import inr, nice_date

log = logging.getLogger("afterlife.agent")

MAX_STEPS = 10
ANALYSE_MESSAGE = "Please go through everything we uploaded and tell us what to do next."

SYSTEM_PROMPT = """\
You are Afterlife, a calm and kind assistant helping an Indian family with the money matters of a
loved one who has died. The person writing to you is grieving. Be warm, brief and plain. No jargon.

When asked to go through the case, work in this order (call independent tools in parallel):
1. extract_document for every document whose status is uploaded or failed.
2. infer_hidden_assets once.
3. lookup_procedure for each distinct item type in the asset map.
4. ask_user once, with 2 to 4 gaps from the latest open gaps list (use their gap ids exactly). ALWAYS include
   every confirm_item gap first (asking the family whether each probable item is real), then fill up with others.
5. build_action_plan.
6. generate_letter for every probable item, and for the first confirmed item in the plan.
7. Reply with 4 to 6 short sentences: what was found, the first thing to do, and that a few questions are
   waiting for them in the app.
For any other message, use only the tools you need, then reply.

Rules you must always follow:
- Probable items are NOT facts. Say "looks like" or "probably", mention the clue (e.g. monthly premium debits),
  and suggest confirming with the institution.
- Procedural steps must come only from lookup_procedure results; name the source. If nothing is found, say
  "please confirm with the institution". Never invent deadlines, form numbers, amounts or phone numbers.
- On wills, succession, legal heirs or disputes, give general guidance only and say it is guidance, not legal advice.
- Never help anyone use the deceased's cards, PINs, passwords, OTPs or online banking. Kindly explain why and
  offer to draft a letter to the institution instead.
- Never write full account or policy numbers; the masked form (XXXX1234) is enough.
- Reply in {language}.
"""


@dataclass
class AgentResult:
    run_id: str
    reply: str
    steps: int
    tool_calls: list[dict] = field(default_factory=list)
    stopped_early: bool = False


def case_context(case: Case) -> str:
    from datetime import date

    days = (date.today() - case.date_of_death).days
    docs = "\n".join(f"- {d.id} | {d.filename} | {d.status}"
                     + (f" | {d.extraction.document_type.value} | {d.extraction.institution}" if d.extraction else "")
                     for d in case.documents) or "- none"
    items = "\n".join(f"- {i.id} | {i.status} | {i.type} | {i.institution} | {i.identifier_masked or 'no number'} | "
                      f"amount {inr(i.amount)} | nominee {i.nominee or 'unknown'}"
                      for i in [*case.assets, *case.liabilities]) or "- nothing yet"
    questions = "\n".join(f"- {q.status}: {q.text}" for q in case.questions) or "- none"
    gaps = "\n".join(f"- {g['gap_id']}: {g['about']}" for g in gap_summary(case)) or "- none"
    moved = "\n".join(f"- {f['date']} | {inr(f['amount'])} | {f['institution'] or 'unknown'} | {f['description']}"
                      for f in debits_after_death(case)) or "- none"
    return (f"CASE\nDeceased: {case.deceased_name}, died {nice_date(case.date_of_death)} ({days} days ago). "
            f"Writing to you: their {case.relationship}.\n\nDOCUMENTS (id | file | status | type | institution)\n{docs}"
            f"\n\nASSET MAP (id | status | type | institution | number | amount | nominee)\n{items}"
            f"\n\nMONEY THAT LEFT AN ACCOUNT AFTER THE DEATH (mention this first: the family should tell the bank today)\n{moved}"
            f"\n\nQUESTIONS ALREADY ASKED\n{questions}\n\nOPEN GAPS YOU MAY ASK ABOUT\n{gaps}"
            f"\n\nPLAN: {'built with ' + str(len(case.plan.tasks)) + ' tasks' if case.plan else 'not built yet'}"
            f"\nLETTERS: {len(case.letters)} drafted")


class AfterlifeTool(BaseTool):
    """One ADK tool per Afterlife tool: the declaration Gemini sees, and a run that goes through dispatch()."""

    def __init__(self, declaration: types.FunctionDeclaration, ctx: ToolContext, result: "AgentResult",
                 lock: asyncio.Lock):
        super().__init__(name=declaration.name, description=declaration.description)
        self.declaration, self.ctx, self.result, self.lock = declaration, ctx, result, lock

    def _get_declaration(self) -> types.FunctionDeclaration:
        return self.declaration

    async def run_async(self, *, args, tool_context) -> dict:
        # ADK starts all calls of one turn at once, but they depend on each other (hidden-asset search needs the
        # documents read first), so the run's lock makes them go one by one, in the order Gemini asked.
        async with self.lock:
            output = await asyncio.to_thread(dispatch, self.ctx, self.name, dict(args))  # blocking: storage, Gemini
            self.result.tool_calls.append({"step": self.result.steps, "tool": self.name, "args": dict(args),
                                           "ok": "error" not in output})
        return {"result": output}


def _gemini(model: str) -> Gemini:
    key = get_settings().gemini_api_key
    if not key:
        raise GeminiNotConfigured("GEMINI_API_KEY is not set. Add it to .env or the environment.")
    # ADK builds the client (one per event loop). 429s and brief 5xx spikes are retried with backoff:
    # 6 attempts wait 2+4+8+16+32 = ~62s in total, enough for Gemini's usual "retry in ~56s".
    return Gemini(model=model, client_kwargs={"api_key": key}, retry_options=types.HttpRetryOptions(
        attempts=6, initial_delay=2.0, max_delay=60.0, exp_base=2.0, http_status_codes=[429, 500, 502, 503, 504]))


async def _run(agent: LlmAgent, case_id: str, text: str, max_steps: int, result: "AgentResult") -> str:
    runner = InMemoryRunner(agent=agent, app_name="afterlife")
    session = await runner.session_service.create_session(app_name="afterlife", user_id=case_id)
    message = types.Content(role="user", parts=[types.Part.from_text(text=text)])
    reply = ""
    try:
        async for event in runner.run_async(user_id=case_id, session_id=session.id, new_message=message,
                                            run_config=RunConfig(max_llm_calls=max_steps)):
            if event.is_final_response() and event.content:
                reply = "".join(p.text for p in event.content.parts or [] if p.text and not p.thought).strip()
    except LlmCallsLimitExceededError:
        result.stopped_early = True
    finally:
        await runner.close()
    return reply


def run_agent(storage: Storage, case_id: str, message: str = ANALYSE_MESSAGE, *, tool_client=None,
              model: str | BaseLlm | None = None, max_steps: int = MAX_STEPS) -> AgentResult:
    """model: a Gemini model id, or any ADK model (tests pass a scripted one). tool_client: Gemini client used by
    the extraction/inference tools (tests)."""
    case = storage.get_case(case_id)
    lang = case.language
    run_id = new_id()[:12]
    services.record(storage, case_id, "agent_start", "Started looking through your case",
                    "आपके मामले को देखना शुरू किया", run_id=run_id, message=message[:200])

    if asks_to_use_credentials(message):
        reply = REFUSAL[lang].format(name=case.deceased_name)
        services.record(storage, case_id, "guardrail", "Declined a request to use the deceased's cards or passwords",
                        "दिवंगत के कार्ड या पासवर्ड के उपयोग का अनुरोध अस्वीकार किया", run_id=run_id)
        return AgentResult(run_id=run_id, reply=reply, steps=0)

    result = AgentResult(run_id=run_id, reply="", steps=0)
    ctx = ToolContext(storage, case_id, run_id, tool_client)
    known = {d.name for d in DECLARATIONS}
    lock = asyncio.Lock()

    async def before_model(callback_context, llm_request):
        result.steps += 1
        await asyncio.to_thread(gemini.get_rate_limiter().acquire, llm_request.model or "agent")  # via the module, so tests can swap it

    def unknown_tool(tool, args, tool_context):
        # ADK lets a before-tool callback answer a call to a tool that doesn't exist; send the error back to Gemini.
        if tool.name not in known:
            output = dispatch(ctx, tool.name, dict(args))
            result.tool_calls.append({"step": result.steps, "tool": tool.name, "args": dict(args), "ok": False})
            return {"result": output}
        return None

    try:
        agent = LlmAgent(
            name="afterlife",
            model=model if isinstance(model, BaseLlm) else _gemini(model or get_settings().reasoning_model),
            instruction=SYSTEM_PROMPT.format(language="Hindi (Devanagari script)" if lang == "hi" else "English"),
            tools=[AfterlifeTool(d, ctx, result, lock) for d in DECLARATIONS],
            generate_content_config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MEDIUM)),
            before_model_callback=before_model,
            before_tool_callback=unknown_tool,
        )
        result.reply = asyncio.run(_run(agent, case_id, f"{case_context(case)}\n\nMESSAGE FROM THE FAMILY:\n{message}",
                                        max_steps, result))
    except Exception as exc:  # Gemini errors, a missing key, or anything ADK raises: logged, shown, never hidden
        detail = f"{exc.code}: {exc.message}" if isinstance(exc, errors.APIError) else str(exc)
        if not isinstance(exc, (errors.APIError, GeminiNotConfigured)):
            log.exception("agent run %s failed", run_id)
        services.record(storage, case_id, "agent_error", "Afterlife couldn't finish just now", "आफ्टरलाइफ़ अभी पूरा नहीं कर सका",
                        ok=False, run_id=run_id, error=detail[:500])
        raise AgentError(f"Gemini request failed ({detail})") from exc

    if result.stopped_early:
        result.steps = max_steps
        result.reply = ("I've done the main steps but stopped there to keep things short. Everything so far is saved."
                        if lang == "en" else "मैंने मुख्य कदम पूरे कर लिए हैं और यहीं रुका हूँ। अब तक का सब सहेजा गया है।")

    if not result.reply:
        result.reply = "Everything is saved. Please look at the plan and the questions in the app." if lang == "en" else \
            "सब सहेजा गया है। कृपया ऐप में योजना और प्रश्न देखें।"
    if touches_legal_topic(message, result.reply):
        result.reply = with_legal_note(result.reply, lang)
    services.record(storage, case_id, "agent_reply", "Wrote a summary for you", "आपके लिए सारांश लिखा", run_id=run_id,
                    steps=result.steps, tool_calls=len(result.tool_calls), stopped_early=result.stopped_early)
    return result


class AgentError(RuntimeError):
    pass
