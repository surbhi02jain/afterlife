"""Name check across documents: catch the mismatches that stall claims before an institution does.

In India the same person is often written differently on different papers ("Suresh Narayan Rao", "S. N. Rao",
"Suresh N. Rao"), and nominees too ("Kamala Suresh Rao", "Kamla Rao"). Institutions often ask the family to prove
the names belong to one person before they pay. Telling initials and spelling variants of Indian names apart from
a genuinely different person is judgement, so Gemini compares the names; code keeps it honest:
  - nothing is sent when every name already matches exactly (no call needed);
  - every name Gemini quotes must appear, character for character, where it says (document holder/nominee, the name
    the family typed, or the claimant), or the finding is dropped and logged;
  - what to do about a mismatch comes only from the knowledge base (kb "name_mismatch"), never from the model.
"""

import re

from google.genai import errors, types
from pydantic import ValidationError

from app.config import get_settings
from app.gemini import GeminiUnreachable, generate, get_client
from app.models import Case, NameCheck, NameCheckResult, NameIssue

NAME_PROMPT = """\
You compare how people's names are written across a family's financial papers in India, after {name} died.
Institutions often refuse or delay a claim when the deceased's or the nominee's name differs between papers, until
the family proves the names belong to one person. Find those differences so the family can prepare early.

You get a list of names, each with where it appears (a document ref like D3, FAMILY for the deceased's name as
the family typed it, CLAIMANT for the family member who will sign) and its role.

Report:
- deceased_name_differs: the deceased's name is written differently in different places (initials instead of
  names, a missing or extra middle name, a spelling variant, a different order). Include every variant.
- nominee_name_differs: a nominee is written differently in different places, or differs from the claimant who
  is clearly the same person. Include every variant.
- not_the_deceased: a document's holder looks like a different person altogether (another first name or surname).
Ignore differences of letter case, punctuation, spacing, and titles (Mr., Shri, Smt., Late), and relationship notes
in brackets like "(Wife)". If nothing differs, return an empty list.
Copy each name exactly as it is given in the list. Write explanations in {language} (use commas or colons, never em dashes): warm, plain, one or two
sentences, saying which papers differ (say what the paper is, e.g. "the EPF passbook", not its ref). Do not give legal
advice and do not tell them what to file.
"""

_TITLES = re.compile(r"\b(?:mr|mrs|ms|miss|shri|sri|smt|kumari|late|dr)\b\.?", re.I)


class NameCheckError(RuntimeError):
    """Gemini could not check the names. Message is safe to show the user."""


def normalize(name: str) -> str:
    """For deciding whether two names already agree: no titles, brackets, punctuation, case or extra spaces."""
    name = re.sub(r"\(.*?\)", " ", name)
    name = _TITLES.sub(" ", name)
    return " ".join(re.findall(r"[^\W\d_]+", name.lower()))


def name_list(case: Case) -> list[dict]:
    """Every name to compare, with a ref Gemini can cite: D1.. for documents in upload order."""
    names = [{"ref": "FAMILY", "role": "deceased", "name": case.deceased_name, "where": "the name you typed"}]
    if case.facts.claimant_name:
        names.append({"ref": "CLAIMANT", "role": "claimant", "name": case.facts.claimant_name,
                      "where": "the name for signing letters"})
    for n, doc in enumerate(case.documents, start=1):
        e = doc.extraction
        if doc.status != "extracted" or not e:
            continue
        for role, value in (("holder", e.holder_name), ("nominee", e.nominee)):
            if value and value.strip():
                names.append({"ref": f"D{n}", "role": role, "name": value.strip(), "where": doc.filename})
    return names


def needs_check(names: list[dict]) -> bool:
    """Only ask Gemini when some names differ once titles and punctuation are ignored."""
    by_role = {}
    for n in names:
        if n["role"] == "claimant":
            continue  # the claimant is often not the nominee (a son signing for his mother): no reason to call
        group = "deceased" if n["role"] in ("holder", "deceased") else "nominee"
        by_role.setdefault(group, set()).add(normalize(n["name"]))
    return any(len(variants) > 1 for variants in by_role.values())


def build_prompt(names: list[dict]) -> str:
    return "NAMES:\n" + "\n".join(f"- {n['ref']} | {n['role']} | {n['name']}" for n in names)


def ask_gemini(case: Case, names: list[dict], *, client=None, model: str | None = None) -> tuple[str, str]:
    """(raw reply, model)."""
    client = client or get_client()
    model = model or get_settings().reasoning_model
    language = "Hindi (Devanagari script)" if case.language == "hi" else "English"
    try:
        response = generate(
            client, model=model, contents=build_prompt(names),
            config=types.GenerateContentConfig(
                system_instruction=NAME_PROMPT.format(name=case.deceased_name, language=language),
                response_mime_type="application/json",
                response_json_schema=NameCheckResult.model_json_schema(),
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MEDIUM),
            ),
        )
    except errors.APIError as exc:
        raise NameCheckError(f"Gemini request failed ({exc.code}): {exc.message}") from exc
    except GeminiUnreachable as exc:
        raise NameCheckError(str(exc)) from exc
    if not response.text:
        raise NameCheckError("Gemini returned an empty response for the name check.")
    return response.text, model


def parse_result(raw: str) -> NameCheckResult:
    try:
        return NameCheckResult.model_validate_json(raw)
    except ValidationError as exc:
        raise NameCheckError(f"Gemini's name check did not match the schema: {exc.errors()[:3]}") from exc


def verify(names: list[dict], result: NameCheckResult, model: str) -> NameCheck:
    """Keep only findings whose every quoted name really appears where Gemini says, and that really differ."""
    actual = {(n["ref"], n["role"], n["name"]) for n in names}
    where = {n["ref"]: n["where"] for n in names}
    check = NameCheck(model=model, compared=len(names))
    for finding in result.findings:
        quoted = [(m.ref, m.role, m.name.strip()) for m in finding.mentions]
        wrong = [q for q in quoted if q not in actual]
        if wrong:
            check.discarded.append(f"{finding.kind}: quoted names not found as given: {wrong}")
            continue
        variants = {normalize(name) for _, _, name in quoted}
        if finding.kind != "not_the_deceased" and len(variants) < 2:
            check.discarded.append(f"{finding.kind}: the quoted names don't actually differ")
            continue
        groups: dict[str, dict] = {}  # one row per way of writing it; case and titles don't make a new one
        for ref, _, name in quoted:
            row = groups.setdefault(normalize(name), {"name": name, "where": []})
            if where[ref] not in row["where"]:
                row["where"].append(where[ref])
        check.issues.append(NameIssue(kind=finding.kind, explanation=_readable(finding.explanation, where),
                                      names=list(groups.values())))
    return check


def _readable(explanation: str, where: dict[str, str]) -> str:
    """Gemini sometimes says 'document D9'; the family knows the file, not our ref."""
    return re.sub(r"\b(D\d+)\b", lambda m: where.get(m.group(1), m.group(1)), explanation.strip())
