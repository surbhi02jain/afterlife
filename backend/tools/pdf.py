"""Password-protected PDFs. Indian banks, insurers and fund registrars email statements locked with a password
the family can usually work out (often part of the name plus the date of birth). The family types it once in the
app; we keep only the unlocked copy. The password itself is never stored, logged or sent to Gemini.

This only opens a file the family already has. It is not a way into the deceased's accounts.
"""

import io

from pypdf import PasswordType, PdfReader, PdfWriter


class WrongPassword(ValueError):
    """Message is safe to show the user."""


def _rewrite(reader: PdfReader) -> bytes:
    out = io.BytesIO()
    PdfWriter(clone_from=reader).write(out)  # written without encryption
    return out.getvalue()


def prepare(data: bytes) -> tuple[bytes, bool]:
    """(bytes to store, still locked?) for an uploaded PDF. PDFs that open without a password (owner-only
    restrictions, common on bank statements) are unlocked right away. A file pypdf can't parse is kept as-is:
    Gemini reads it, or the extraction fails and says so."""
    try:
        reader = PdfReader(io.BytesIO(data))
        if not reader.is_encrypted:
            return data, False
    except Exception:
        return data, False
    if reader.decrypt("") == PasswordType.NOT_DECRYPTED:
        return data, True
    return _rewrite(reader), False


def unlock(data: bytes, password: str) -> bytes:
    """The unlocked PDF. Raises WrongPassword if the password doesn't open it."""
    reader = PdfReader(io.BytesIO(data))
    if not reader.is_encrypted:
        return data
    if reader.decrypt(password) == PasswordType.NOT_DECRYPTED:
        raise WrongPassword("That password didn't open this file. Please check it and try again.")
    return _rewrite(reader)
