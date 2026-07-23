"""Unit tests for extraction helpers that don't require the Anthropic API.

Run:  cd backend && python -m pytest
The live-model extraction test is marked and skipped unless ANTHROPIC_API_KEY is set.
"""

import os

import pytest

from app.services.extractor import _build_content, _missing_fields, _IMAGE_TYPES, REQUIRED_FIELDS


def test_missing_fields_all_present():
    wo = {"property_address": "245 Main St", "unit": "2B", "issue": "leak", "priority": "High"}
    assert _missing_fields(wo) == []


def test_missing_fields_reports_gaps():
    wo = {"property_address": "245 Main St", "issue": "leak"}
    missing = _missing_fields(wo)
    assert "unit" in missing and "priority" in missing
    assert set(missing).issubset(set(REQUIRED_FIELDS))


def test_build_content_text_only():
    content = _build_content("Leaking sink", "Please fix", [])
    assert content[0]["type"] == "text"
    assert "Leaking sink" in content[0]["text"]
    assert len(content) == 1


def test_build_content_includes_image_block():
    fake_png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    content = _build_content("subj", "body", [{"filename": "leak.png", "mime": "image/png", "data": fake_png}])
    assert any(b.get("type") == "image" for b in content)


def test_build_content_includes_pdf_block():
    content = _build_content("subj", "body", [{"filename": "wo.pdf", "mime": "application/pdf", "data": b"%PDF-1.4"}])
    assert any(b.get("type") == "document" for b in content)


def test_build_content_skips_unsupported_type():
    content = _build_content("subj", "body", [{"filename": "x.docx", "mime": "application/vnd.doc", "data": b"x"}])
    # only the leading text block, no image/document
    assert len(content) == 1


@pytest.mark.skipif(not os.environ.get("RUN_LIVE_TESTS"), reason="set RUN_LIVE_TESTS=1 + real ANTHROPIC_API_KEY")
@pytest.mark.asyncio
async def test_live_extraction_classifies_work_order():
    from app.services.extractor import extract_work_order

    body = "Tenant at 245 Main Street Apt 2B reports the kitchen sink is leaking underneath. Please dispatch ASAP."
    result = await extract_work_order("Maintenance Request", body, [])
    assert result["is_work_order"] is True
    assert "2" in (result.get("unit") or "")
    assert result.get("issue")
