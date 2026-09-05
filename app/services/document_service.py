"""PDF/DOCX text extraction, page detection, and document-integrity hashing.

No LLM involved — this is deterministic parsing (plan section 2,
"Document Processing"). agents/intake_agent.py and the other agents all
consume the plain text this module extracts; they never see the raw
file.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


class UnsupportedDocumentType(ValueError):
    pass


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    sha256: str


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages_text)


def _extract_docx(data: bytes) -> str:
    doc = DocxDocument(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)


def extract_document(filename: str, data: bytes) -> ExtractedDocument:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf(data)
    elif suffix == ".docx":
        text = _extract_docx(data)
    else:
        raise UnsupportedDocumentType(f"Unsupported document type: {suffix!r}. Use .pdf or .docx.")

    return ExtractedDocument(text=text, sha256=compute_sha256(data))
