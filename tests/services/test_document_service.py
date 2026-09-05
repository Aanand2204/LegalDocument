"""Tests for services/document_service.py."""
from __future__ import annotations

import io

import pytest
from docx import Document as DocxDocument

from app.services import document_service
from tests.conftest import make_minimal_pdf


def test_extract_pdf_returns_text_and_hash():
    data = make_minimal_pdf("Effective date 01 January 2024")
    result = document_service.extract_document("sample.pdf", data)

    assert "2024" in result.text
    assert result.sha256 == document_service.compute_sha256(data)


def test_extract_docx_returns_text():
    doc = DocxDocument()
    doc.add_paragraph("This Vendor Agreement is between ABC Ltd and XYZ Corp.")
    buffer = io.BytesIO()
    doc.save(buffer)

    result = document_service.extract_document("sample.docx", buffer.getvalue())

    assert "ABC Ltd" in result.text


def test_unsupported_extension_raises():
    with pytest.raises(document_service.UnsupportedDocumentType):
        document_service.extract_document("sample.txt", b"hello")


def test_hash_is_deterministic_and_content_sensitive():
    assert document_service.compute_sha256(b"identical") == document_service.compute_sha256(b"identical")
    assert document_service.compute_sha256(b"a") != document_service.compute_sha256(b"b")
