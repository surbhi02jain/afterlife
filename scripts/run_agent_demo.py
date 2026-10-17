"""Phase 3 end-to-end from the CLI: demo case -> Afterlife agent (live Gemini function calling) -> results.

  .venv/bin/python scripts/run_agent_demo.py            # English
  .venv/bin/python scripts/run_agent_demo.py --hi       # Hindi case

Extraction of the 9 demo documents replays their REAL recorded Gemini replies (DEMO_REPLAY_EXTRACTION, on by
default for demo cases). Inference, the agent loop and its tool calls are live. Prints the activity log, the
action plan and one letter, and exits non-zero if the planted assets, plan or letters are missing.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from agent.loop import AgentError, run_agent  # noqa: E402
from app import services  # noqa: E402
from app.config import get_settings  # noqa: E402
from storage import get_storage  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hi", action="store_true", help="run the case in Hindi")
    args = parser.parse_args()

    storage = get_storage()
    case = services.create_demo_case(storage)
    if args.hi:
        storage.update_case(case.id, lambda c: setattr(c, "language", "hi"))
    print(f"Demo case {case.id}; agent model {get_settings().reasoning_model}\n")

    try:
        result = run_agent(storage, case.id)
    except AgentError as exc:
        print(f"AGENT FAILED: {exc}")
        return 1
    case = storage.get_case(case.id)
    lang = case.language

    print("=" * 30, "AGENT TOOL CALLS", "=" * 30)
    for c in result.tool_calls:
        args_text = ", ".join(f"{k}={str(v)[:40]}" for k, v in c["args"].items() if k != "questions")
        if "questions" in c["args"]:
            args_text = f"{len(c['args']['questions'])} questions"
        print(f"  step {c['step']}: {c['tool']}({args_text}){'' if c['ok'] else '  -> ERROR'}")
    print(f"  steps used: {result.steps} (cap 10), stopped early: {result.stopped_early}")

    print("\n" + "=" * 30, "ACTIVITY LOG", "=" * 30)
    for a in case.activity:
        print(f"  {a.at:%H:%M:%S}  {'ok ' if a.ok else 'ERR'}  {a.tool:20} {a.summary_hi if lang == 'hi' else a.summary_en}")
    print("\n  Summary panel:", " | ".join(line[lang] for line in services.activity_summary(case)))

    print("\n" + "=" * 30, "AGENT REPLY", "=" * 30)
    print(result.reply)

    print("\n" + "=" * 30, "QUESTIONS FOR THE FAMILY", "=" * 30)
    for q in case.questions:
        print(f"  - {q.text}   [{q.target}{' / ' + ', '.join(q.options) if q.options else ''}]")

    print("\n" + "=" * 30, "ACTION PLAN", "=" * 30)
    plan = case.plan
    if plan:
        print(f"  {plan.days_since_death} days since the death. First, for everyone:")
        for s in plan.general_steps:
            print(f"    * {s}")
        for t in plan.tasks:
            items = ", ".join(f"{i.type} {i.identifier_masked or ''} ({i.status})" for i in t.items)
            print(f"\n  {t.order}. {t.institution}  -  {items}")
            print(f"     Nominee: {t.nominee or 'unknown'}")
            print(f"     First: {t.first_step}")
            for flag in t.time_sensitive:
                print(f"     ! {flag}")
            print(f"     Documents: {'; '.join(t.documents_required)}")
            print(f"     Why this order: {t.why_this_order}")
            print(f"     Source: {', '.join(t.source_names)} (verified: {t.verified})")
        print(f"\n  {plan.disclaimer}")

    print("\n" + "=" * 30, "LETTERS", "=" * 30)
    for l in case.letters:
        print(f"  - {l.title} [{l.kind}]")
    letter = next((l for l in case.letters if l.kind == "existence_enquiry"), case.letters[0] if case.letters else None)
    if letter:
        print(f"\n----- {letter.title} -----\n{letter.body}\n-----")

    problems = []
    probable = {(a.type, (a.institution or "").lower().split()[0]) for a in case.assets if a.status == "probable"}
    if not any(t == "demat_account" for t, _ in probable):
        problems.append("demat account not found as probable")
    if not any(t == "life_insurance" and "kavach" in w for t, w in probable):
        problems.append("Kavach policy not found as probable")
    if not case.plan:
        problems.append("no action plan")
    if not case.letters:
        problems.append("no letters")
    if not case.questions:
        problems.append("no follow-up questions")
    print("\nCHECK:", "PASS" if not problems else "FAIL - " + "; ".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
