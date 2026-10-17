"""Document extraction: one uploaded file in, one validated ExtractedDocument out."""

from dataclasses import dataclass

from google.genai import errors, types
from pydantic import ValidationError

from app.config import get_settings
from app.gemini import GeminiUnreachable, generate, get_client
from app.models import ExtractedDocument

SUPPORTED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/heic",
    "image/heif",
    "application/pdf",
}

EXTRACTION_PROMPT = """\
You are reading ONE financial document belonging to a person in India who has recently died.
Their family uploaded it (a photo, scan, PDF or phone screenshot) so we can list what accounts,
policies, investments and loans exist. Extract what is printed, accurately.

Rules:
- Copy only what you can see. If a field is not on the document, use null (or an empty list).
  Never guess names, nominees or numbers.
- document_type: pick the closest value. SMS screenshots about loan EMIs are loan_sms; UPI app
  transaction lists are upi_history; a bank passbook photo is passbook. Use other if nothing fits.
- identifier: the main account / policy / folio / loan / UAN / member number, exactly as printed,
  including any X or * masking.
- Dates: always YYYY-MM-DD. Indian documents use day-first order (05/08/2026 is 5 August 2026).
  If a date has no year, infer it from the statement period.
- Amounts: plain positive numbers in rupees. "1,25,000.50" -> 125000.5. Drop "Rs", "INR", "₹".
- transactions: include every row you can read, in order. direction is "credit" for money coming
  IN to this account (Cr, deposit, received, refund) and "debit" for money going OUT (Dr,
  withdrawal, paid, sent). For UPI apps, "Paid to"/"Sent" = debit and "Received from" = credit.
  Keep the narration text as printed; it is used later to spot other accounts and policies.
- amounts: the important figures on the page (opening/closing balance, sum assured, premium,
  EMI, outstanding, NAV value, EPF balance). dates: the important non-transaction dates
  (statement period, due date, maturity, date of commencement).
- confidence: high if the page is clear and you read everything; medium if some parts were
  unclear; low if most of it was hard to read.
"""


class ExtractionError(RuntimeError):
    """Gemini could not produce a valid extraction. Message is safe to show the user."""


@dataclass
class ExtractionResult:
    document: ExtractedDocument
    raw_response: str
    model: str


def extract_document(data: bytes, mime_type: str, *, client=None, model: str | None = None) -> ExtractionResult:
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise ExtractionError(f"Unsupported file type {mime_type}. Please upload a photo (PNG/JPEG) or a PDF.")
    if not data:
        raise ExtractionError("The file is empty.")

    client = client or get_client()
    model = model or get_settings().extraction_model

    try:
        response = generate(
            client,
            model=model,
            contents=[
                types.Part.from_bytes(data=data, mime_type=mime_type),
                "Extract this document.",
            ],
            config=types.GenerateContentConfig(
                system_instruction=EXTRACTION_PROMPT,
                response_mime_type="application/json",
                response_json_schema=ExtractedDocument.model_json_schema(),
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
            ),
        )
    except errors.APIError as exc:
        raise ExtractionError(f"Gemini request failed ({exc.code}): {exc.message}") from exc
    except GeminiUnreachable as exc:
        raise ExtractionError(str(exc)) from exc

    raw = response.text
    if not raw:
        reason = response.candidates[0].finish_reason if response.candidates else "no candidates"
        raise ExtractionError(f"Gemini returned an empty response (finish reason: {reason}).")

    return ExtractionResult(document=parse_extraction(raw), raw_response=raw, model=model)


def parse_extraction(raw: str) -> ExtractedDocument:
    """Validate a raw JSON reply against the schema. Used for live calls and recorded fixtures."""
    try:
        return ExtractedDocument.model_validate_json(raw)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc'])) or '(root)'}: {e['msg']}" for e in exc.errors()[:5])
        raise ExtractionError(f"Gemini's reply did not match the extraction schema: {problems}") from exc
