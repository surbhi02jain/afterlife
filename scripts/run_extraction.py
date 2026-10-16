"""Run live Gemini extraction on the demo documents (or any files you pass).

  .venv/bin/python scripts/run_extraction.py                       # all demo docs, summary table
  .venv/bin/python scripts/run_extraction.py --show 01 07          # also print full JSON for files matching 01, 07
  .venv/bin/python scripts/run_extraction.py --record              # save raw replies as pytest fixtures
  .venv/bin/python scripts/run_extraction.py --record --missing    # ...only for docs not recorded yet
  .venv/bin/python scripts/run_extraction.py path/to/photo.jpg     # your own files

Needs GEMINI_API_KEY (env or .env). Exits non-zero if any file fails.
"""

import argparse
import json
import mimetypes
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from tools.extraction import ExtractionError, extract_document  # noqa: E402

DEMO_DIR = ROOT / "demo" / "docs"
FIXTURE_DIR = ROOT / "backend" / "tests" / "fixtures" / "extraction"


def run_one(path: Path):
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    started = time.monotonic()
    try:
        result = extract_document(path.read_bytes(), mime)
        return path, result, None, time.monotonic() - started
    except ExtractionError as exc:
        return path, None, str(exc), time.monotonic() - started


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--show", nargs="*", default=[], help="substrings of filenames to print in full")
    parser.add_argument("--record", action="store_true", help="save raw responses to tests/fixtures/extraction")
    parser.add_argument("--missing", action="store_true", help="only files that have no recorded fixture yet")
    args = parser.parse_args()

    files = args.files or sorted(DEMO_DIR.glob("*.png"))
    if args.missing:
        files = [f for f in files if not (FIXTURE_DIR / f"{f.stem}.json").exists()]
    print(f"Extracting {len(files)} file(s) with {get_settings().extraction_model}\n")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run_one, files))

    failures = 0
    for path, result, error, seconds in results:
        if error:
            failures += 1
            print(f"FAIL {path.name}  ({seconds:.1f}s)\n     {error}")
            continue
        doc = result.document
        print(f"ok   {path.name:28} {doc.document_type.value:22} {str(doc.institution)[:38]:38} "
              f"txns={len(doc.transactions):<3} conf={doc.confidence:6} ({seconds:.1f}s)")
        if args.record:
            FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
            fixture = {"source_file": path.name, "model": result.model, "raw_response": result.raw_response}
            (FIXTURE_DIR / f"{path.stem}.json").write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n")

    for path, result, _, _ in results:
        if result and any(s in path.name for s in args.show):
            print(f"\n===== {path.name} =====")
            print(result.document.model_dump_json(indent=2))

    if args.record:
        print(f"\nRecorded fixtures in {FIXTURE_DIR.relative_to(ROOT)}")
    print(f"\n{len(results) - failures}/{len(results)} succeeded")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
