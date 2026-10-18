"""Record REAL Gemini replies for the sample family's other inputs, so the demo replays them (like extraction).

  .venv/bin/python scripts/record_samples.py                 # memory + replies + name check, prints what Gemini said
  .venv/bin/python scripts/record_samples.py --record        # ...and save them to demo/recorded/{memory,replies,names}
  .venv/bin/python scripts/record_samples.py names --record  # only one kind: memory, replies or names

The name check runs on the demo documents' recorded extractions (all 9 read, no claimant name yet), which is what the
sample family looks like right after "Find what might be missing". Needs GEMINI_API_KEY. One Gemini call per input.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import demo  # noqa: E402
from app.models import Document  # noqa: E402
from tools import memories, names, replies  # noqa: E402
from tools.extraction import parse_extraction  # noqa: E402


def demo_case_with_documents():
    """The sample family with every demo document read, using the recorded extractions."""
    case = demo.new_demo_case()
    for path in demo.demo_documents():
        fixture = json.loads((demo.RECORDED_DIR / f"{path.stem}.json").read_text())
        case.documents.append(Document(filename=path.name, content_type=demo.content_type(path), size_bytes=1,
                                       storage_key="", status="extracted",
                                       extraction=parse_extraction(fixture["raw_response"])))
    return case


def save(kind: str, stem: str, source: str, data: bytes, model: str, raw: str) -> None:
    folder = demo.RECORDED_ROOT / kind
    folder.mkdir(parents=True, exist_ok=True)
    fixture = {"source": source, "model": model, "input_sha256": demo.sha256(data), "raw_response": raw}
    (folder / f"{stem}.json").write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n")
    print(f"     recorded demo/recorded/{kind}/{stem}.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kinds", nargs="*", default=["memory", "replies", "names"])
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    case = demo_case_with_documents()

    if "memory" in args.kinds:
        data = demo.SAMPLE_MEMORY.read_bytes()
        reading, raw, model = memories.read_memory(case, audio=data, mime_type="audio/wav")
        print(f"ok   memory ({model})\n     transcript: {reading.transcript}")
        for clue in reading.clues:
            print(f"     clue: {clue.type} | {clue.institution} | months={clue.months} | {clue.what_they_said}")
        if args.record:
            save("memory", demo.SAMPLE_MEMORY.stem, demo.SAMPLE_MEMORY.name, data, model, raw)

    if "replies" in args.kinds:
        for name in demo.SAMPLE_REPLIES:
            path = demo.SAMPLES_DIR / name
            data = path.read_bytes()
            reading, raw, model = replies.read_reply(data, "image/png", case)
            print(f"ok   {name} ({model}): {reading.outcome}, {len(reading.requirements)} requirements, "
                  f"within {reading.respond_within_days} days, red flags {reading.red_flags}")
            if args.record:
                save("replies", path.stem, name, data, model, raw)

    if "names" in args.kinds:
        listed = names.name_list(case)
        prompt = names.build_prompt(listed)
        raw, model = names.ask_gemini(case, listed)
        check = names.verify(listed, names.parse_result(raw), model)
        print(f"ok   name check ({model}): {len(check.issues)} issues, {len(check.discarded)} discarded")
        for issue in check.issues:
            print(f"     {issue.kind}: {[n['name'] for n in issue.names]} - {issue.explanation}")
        for reason in check.discarded:
            print(f"     discarded: {reason}")
        if args.record:
            save("names", "demo_case", "the sample family's 9 documents", prompt.encode(), model, raw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
