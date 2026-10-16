"""Saath agent: Gemini function calling over the case tools, with a capped loop and an activity log."""

from dataclasses import dataclass, field

from google.genai import errors, types

from agent.guardrails import REFUSAL, asks_to_use_credentials, touches_legal_topic, with_legal_note
from agent.tools import TOOL, ToolContext, dispatch, gap_summary
from app import services
from app.config import get_settings
from app.gemini import GeminiNotConfigured, generate, get_client
from app.models import Case, new_id
from storage import Storage
from tools.i18n import inr, nice_date

MAX_STEPS = 10
ANALYSE_MESSAGE = "Please go through everything we uploaded and tell us what to do next."

SYSTEM_PROMPT = """\
You are Saath ("together"), a calm and kind assistant helping an Indian family with the money matters of a
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
    return (f"CASE\nDeceased: {case.deceased_name}, died {nice_date(case.date_of_death)} ({days} days ago). "
            f"Writing to you: their {case.relationship}.\n\nDOCUMENTS (id | file | status | type | institution)\n{docs}"
            f"\n\nASSET MAP (id | status | type | institution | number | amount | nominee)\n{items}"
            f"\n\nQUESTIONS ALREADY ASKED\n{questions}\n\nOPEN GAPS YOU MAY ASK ABOUT\n{gaps}"
            f"\n\nPLAN: {'built with ' + str(len(case.plan.tasks)) + ' tasks' if case.plan else 'not built yet'}"
            f"\nLETTERS: {len(case.letters)} drafted")


def run_agent(storage: Storage, case_id: str, message: str = ANALYSE_MESSAGE, *, client=None,
              tool_client=None, model: str | None = None, max_steps: int = MAX_STEPS) -> AgentResult:
    """client: the agent's Gemini client. tool_client: client used by extraction/inference tools (tests)."""
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

    client = client or get_client()
    model = model or get_settings().reasoning_model
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT.format(language="Hindi (Devanagari script)" if lang == "hi" else "English"),
        tools=[TOOL],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MEDIUM),
    )
    contents = [types.Content(role="user", parts=[types.Part.from_text(
        text=f"{case_context(case)}\n\nMESSAGE FROM THE FAMILY:\n{message}")])]
    ctx = ToolContext(storage, case_id, run_id, tool_client)
    result = AgentResult(run_id=run_id, reply="", steps=0)

    for step in range(1, max_steps + 1):
        result.steps = step
        try:
            response = generate(client, model=model, contents=contents, config=config)
        except (errors.APIError, GeminiNotConfigured) as exc:
            detail = f"{exc.code}: {exc.message}" if isinstance(exc, errors.APIError) else str(exc)
            services.record(storage, case_id, "agent_error", "Saath couldn't finish just now", "साथ अभी पूरा नहीं कर सका",
                            ok=False, run_id=run_id, error=detail[:500])
            raise AgentError(f"Gemini request failed ({detail})") from exc

        calls = response.function_calls or []
        if not calls:
            result.reply = (response.text or "").strip()
            break
        contents.append(response.candidates[0].content)  # keeps thought signatures intact
        parts = []
        for call in calls:
            args = dict(call.args or {})
            output = dispatch(ctx, call.name, args)
            result.tool_calls.append({"step": step, "tool": call.name, "args": args, "ok": "error" not in output})
            parts.append(types.Part(function_response=types.FunctionResponse(
                id=call.id, name=call.name, response={"result": output})))
        contents.append(types.Content(role="user", parts=parts))
    else:
        result.stopped_early = True
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
