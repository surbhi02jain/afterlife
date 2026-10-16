"""End-to-end demo case from the CLI: create case -> upload demo docs -> extract -> asset map -> inference.

  .venv/bin/python scripts/run_demo_case.py            # everything live (10 Gemini calls)
  .venv/bin/python scripts/run_demo_case.py --replay   # extraction replays REAL recorded Gemini replies
                                                       # (demo/recorded/extraction); inference is live

Then checks the result against demo/README.md: both planted assets must appear as PROBABLE with evidence,
and nothing already documented may be duplicated. Exits non-zero if the check fails.
"""

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import services  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.models import Case  # noqa: E402
from storage import get_storage  # noqa: E402
from tools.asset_map import asset_map_view  # noqa: E402
from tools.inference import InferenceError  # noqa: E402

DEMO_DIR = ROOT / "demo" / "docs"
FIXTURE_DIR = ROOT / "demo" / "recorded" / "extraction"


class ReplayClient:
    """Answers extraction calls with the recorded Gemini reply for the exact same file bytes."""

    def __init__(self):
        self.replies = {}
        for png in DEMO_DIR.glob("*.png"):
            fixture = FIXTURE_DIR / f"{png.stem}.json"
            if fixture.exists():
                self.replies[hashlib.sha256(png.read_bytes()).hexdigest()] = json.loads(fixture.read_text())
        self.models = self

    def generate_content(self, *, model, contents, config):
        digest = hashlib.sha256(contents[0].inline_data.data).hexdigest()
        if digest not in self.replies:
            raise RuntimeError("No recorded reply for this file; run scripts/run_extraction.py --record")
        return SimpleNamespace(text=self.replies[digest]["raw_response"], candidates=[])


def money(value):
    return "amount unknown" if value is None else f"Rs {value:,.2f}"


def print_map(view: dict) -> None:
    for group in ("assets", "liabilities"):
        for status in ("confirmed", "probable", "rejected"):
            items = view[group][status]
            if not items:
                continue
            print(f"\n{group.upper()} - {status.upper()} ({len(items)})")
            for i in items:
                print(f"  - {i['type']:16} {i['institution'] or '?':42} {i['identifier_masked'] or '':9} "
                      f"{money(i['amount']):>18}  conf={i['confidence']}  id-check={i['identifier_check']}")
                if i["nominee"]:
                    print(f"      nominee: {i['nominee']}")
                if i["next_expected_debit"]:
                    print(f"      next auto-debit expected: {i['next_expected_debit']}")
                if status == "probable":
                    print(f"      why: {i['reason']}")
                    for e in i["evidence"]:
                        print(f"      evidence: {e['date']}  {e['direction']:6} {money(e['amount']):>14}  "
                              f"{e['description']}  [{e['document_name']}]")
    t = view["totals"]
    print(f"\nTOTALS (confirmed only): assets {money(t['confirmed_assets_total'])} across "
          f"{t['confirmed_assets_count']} items, liabilities {money(t['confirmed_liabilities_total'])}, "
          f"net {money(t['net_confirmed'])}; probable items not counted: {t['probable_assets_count']}")


def verify(case: Case) -> list[str]:
    problems = []
    probable = [a for a in case.assets if a.status == "probable"]

    def find(type_, word):
        return [a for a in probable if a.type == type_ and word in (a.institution or "").lower()]

    for type_, word, needle in [("demat_account", "anand", "DIV"), ("life_insurance", "kavach", "KAVACH")]:
        hits = find(type_, word)
        if not hits:
            problems.append(f"planted {type_} ({word}) was NOT found as probable")
            continue
        if not any(needle in e.description.upper() for e in hits[0].evidence):
            problems.append(f"{type_} ({word}) has no evidence mentioning {needle}")
    for type_, word in [("mutual_fund", "navodaya"), ("life_insurance", "jeevan"), ("epf", "")]:
        if [a for a in probable if a.type == type_ and word in (a.institution or "").lower()]:
            problems.append(f"documented {type_} {word} was duplicated as probable")
    if [l for l in case.liabilities if l.status == "probable"]:
        problems.append("documented home loan was duplicated as a probable liability")
    if any(a.status == "confirmed" and a.origin == "inference" for a in case.assets):
        problems.append("an inferred asset was marked confirmed without a document or user decision")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", action="store_true", help="replay recorded extraction replies")
    args = parser.parse_args()

    settings = get_settings()
    storage = get_storage()
    case = storage.create_case(Case(deceased_name="Suresh Narayan Rao (synthetic demo)", date_of_death=date(2026, 9, 2),
                                    relationship="son", language="en", is_demo=True))
    print(f"Case {case.id}  (storage={settings.storage_backend})")

    for png in sorted(DEMO_DIR.glob("*.png")):
        services.add_document(storage, case.id, png.name, "image/png", png.read_bytes())
    mode = "replaying recorded replies" if args.replay else f"live with {settings.extraction_model}"
    print(f"Uploaded 9 documents; extracting ({mode})...")
    case = services.extract_pending(storage, case.id, client=ReplayClient() if args.replay else None)
    for d in case.documents:
        e = d.extraction
        summary = f"{e.document_type.value:22} {e.institution}" if e else d.error
        print(f"  {d.status:9} {d.filename:28} {summary}")
    if any(d.status != "extracted" for d in case.documents):
        print("Some documents failed; stopping.")
        return 1

    print(f"\nInferring hidden assets (live with {settings.reasoning_model})...")
    try:
        run = services.run_inference(storage, case.id)
    except InferenceError as exc:
        print(f"  FAILED: {exc}")
        return 1
    print(f"  proposed={run.proposed} added={len(run.added)} merged_into_existing={len(run.merged)} "
          f"discarded={len(run.discarded)}")
    for reason in run.discarded:
        print(f"  discarded: {reason}")

    case = storage.get_case(case.id)
    print_map(asset_map_view(case))

    problems = verify(case)
    print("\nCHECK against demo/README.md: " + ("PASS - both planted assets found as probable with evidence, "
                                               "no duplicates" if not problems else "FAIL"))
    for p in problems:
        print(f"  - {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
