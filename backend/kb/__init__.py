"""Procedure knowledge base. All procedural guidance shown to families comes from procedures.json via lookup()."""

import json
from functools import lru_cache
from pathlib import Path

KB_PATH = Path(__file__).parent / "procedures.json"
NOT_FOUND = {
    "en": "We don't have steps for this yet. Please confirm with the institution.",
    "hi": "इसके लिए हमारे पास अभी जानकारी नहीं है। कृपया संस्था से पुष्टि करें।",
}


@lru_cache(maxsize=1)
def entries() -> dict[str, dict]:
    data = json.loads(KB_PATH.read_text())
    return {key: value for key, value in data.items() if not key.startswith("_")}


def key_for(item_type: str) -> str | None:
    return next((key for key, entry in entries().items() if item_type in entry["applies_to"]), None)


def lookup(item_type: str, language: str = "en") -> dict:
    """Procedure for an asset/liability type in the case language, or found=False with the standard message."""
    key = item_type if item_type in entries() else key_for(item_type)
    if key is None:
        return {"found": False, "item_type": item_type, "message": NOT_FOUND[language]}
    e = entries()[key]
    pick = lambda field: (e.get(field) or {}).get(language) or (e.get(field) or {}).get("en")  # noqa: E731
    return {
        "found": True,
        "key": key,
        "title": pick("title"),
        "steps": pick("steps") or [],
        "documents_required": pick("documents_required") or [],
        "typical_timeline": pick("typical_timeline"),
        "time_sensitive": pick("time_sensitive"),
        "priority": e["priority"],
        "source_name": e["source_name"],
        "verified": e["verified"],
    }
