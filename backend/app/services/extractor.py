"""AI extraction — turns an email (text + PDF/image attachments) into a structured
work order. Two interchangeable providers, auto-selected at runtime:

  * Anthropic Claude (paid) — multimodal + forced tool-use.
  * Google Gemini (free tier) — multimodal + JSON-schema-constrained output.

Both read photos and PDFs natively, so there is no separate OCR step, and both
guarantee a schema-valid object (no fence-stripping / json.loads fragility). Any
failure returns a safe _FALLBACK so the pipeline never crashes.

Provider selection (see `_resolve_provider`): honor EXTRACTOR_PROVIDER if set,
else use Anthropic when ANTHROPIC_API_KEY is present, else Gemini when
GEMINI_API_KEY is present, else return the fallback.
"""

import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Fields we consider required for a complete AppFolio work order.
REQUIRED_FIELDS = ["property_address", "unit", "issue", "priority"]

_FALLBACK = {
    "is_work_order": False,
    "confidence": 0.0,
    "property_address": None,
    "unit": None,
    "resident_name": None,
    "issue": None,
    "category": None,
    "priority": None,
    "vendor": None,
    "is_emergency": False,
    "summary": "Extraction unavailable.",
}

_SYSTEM_PROMPT = """\
You are a property-management maintenance coordinator. You read an inbound email \
(and any attached PDFs or photos) and decide whether it is a maintenance WORK ORDER \
that needs to be logged in AppFolio, then extract the details.

Rules:
- A work order = a request to fix/repair/service something at a rental property \
(leak, no heat, broken appliance, electrical issue, pest, etc.). Newsletters, \
receipts, leasing inquiries, spam, and general chit-chat are NOT work orders.
- Extract only what the email/attachments actually state. Never invent an address, \
unit, or name. Leave a field null if it isn't present.
- category: one of Plumbing, Electrical, HVAC, Appliance, Pest, General, Other.
- priority: Low, Medium, High, or Emergency. is_emergency=true for flooding, gas \
smell, no heat in freezing weather, fire, sewage, or anything unsafe.
- Read every attachment. If a photo/PDF shows the address, unit, or the problem, use it.
- confidence = your certainty (0-1) that this is a real, actionable work order with \
the details you extracted.
Always call the record_work_order tool with your result."""

_TOOL = {
    "name": "record_work_order",
    "description": "Record the structured work-order extraction.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_work_order": {"type": "boolean", "description": "True only if this is an actionable maintenance work order."},
            "confidence": {"type": "number", "description": "0-1 certainty."},
            "property_address": {"type": ["string", "null"]},
            "unit": {"type": ["string", "null"], "description": "Unit/apartment number, e.g. '2B'."},
            "resident_name": {"type": ["string", "null"]},
            "issue": {"type": ["string", "null"], "description": "Concise description of the problem."},
            "category": {"type": ["string", "null"], "enum": ["Plumbing", "Electrical", "HVAC", "Appliance", "Pest", "General", "Other", None]},
            "priority": {"type": ["string", "null"], "enum": ["Low", "Medium", "High", "Emergency", None]},
            "vendor": {"type": ["string", "null"], "description": "Requested/assigned vendor if named."},
            "is_emergency": {"type": "boolean"},
            "summary": {"type": "string", "description": "One-line summary for the dashboard."},
        },
        "required": ["is_work_order", "confidence", "issue", "summary"],
    },
}

# Media types Claude accepts as image blocks.
_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def _build_content(subject: str | None, body: str | None, attachments: list[dict]) -> list[dict]:
    """Assemble the multimodal user message: email text + image/PDF blocks.

    attachments: list of {filename, mime, data(bytes)}.
    """
    import base64

    content: list[dict] = [{
        "type": "text",
        "text": f"Subject: {subject or '(none)'}\n\nBody:\n{body or '(empty)'}",
    }]

    for att in attachments:
        mime = (att.get("mime") or "").lower()
        data = att.get("data")
        if not data:
            continue
        b64 = base64.standard_b64encode(data).decode("ascii")
        if mime in _IMAGE_TYPES:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mime, "data": b64},
            })
        elif mime == "application/pdf":
            content.append({
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
            })
        # other types (docx, etc.) are skipped — noted by caller
    return content


def _missing_fields(result: dict) -> list[str]:
    return [f for f in REQUIRED_FIELDS if not result.get(f)]


def _resolve_provider() -> str:
    """Pick the extraction provider. Explicit EXTRACTOR_PROVIDER wins; otherwise
    prefer Anthropic, fall back to the free Gemini path, else 'none'."""
    forced = (settings.extractor_provider or "").strip().lower()
    if forced:
        return forced
    if settings.anthropic_api_key:
        return "anthropic"
    if settings.gemini_api_key:
        return "gemini"
    return "none"


async def _extract_anthropic(
    subject: str | None, body: str | None, attachments: list[dict], model: str | None
) -> dict:
    """Claude multimodal + forced tool-use → schema-valid dict."""
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    content = _build_content(subject, body, attachments)

    resp = await client.messages.create(
        model=model or settings.extractor_model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "record_work_order"},
        messages=[{"role": "user", "content": content}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == "record_work_order":
            return {**_FALLBACK, **block.input}
    return dict(_FALLBACK)


def _gemini_schema():
    """Build the JSON-schema response constraint (Gemini's OpenAPI subset).
    Mirrors _TOOL['input_schema'] — enums for category/priority, nullable optionals.
    Built lazily so `google-genai` is only imported when the Gemini path is used."""
    from google.genai import types

    S = types.Schema
    T = types.Type
    return S(
        type=T.OBJECT,
        properties={
            "is_work_order": S(type=T.BOOLEAN),
            "confidence": S(type=T.NUMBER),
            "property_address": S(type=T.STRING, nullable=True),
            "unit": S(type=T.STRING, nullable=True),
            "resident_name": S(type=T.STRING, nullable=True),
            "issue": S(type=T.STRING, nullable=True),
            "category": S(type=T.STRING, nullable=True,
                          enum=["Plumbing", "Electrical", "HVAC", "Appliance", "Pest", "General", "Other"]),
            "priority": S(type=T.STRING, nullable=True,
                          enum=["Low", "Medium", "High", "Emergency"]),
            "vendor": S(type=T.STRING, nullable=True),
            "is_emergency": S(type=T.BOOLEAN),
            "summary": S(type=T.STRING),
        },
        required=["is_work_order", "confidence", "issue", "summary"],
    )


async def _extract_gemini(
    subject: str | None, body: str | None, attachments: list[dict], model: str | None
) -> dict:
    """Gemini multimodal + JSON-schema output → schema-valid dict."""
    import json

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)

    parts = [types.Part.from_text(
        text=f"Subject: {subject or '(none)'}\n\nBody:\n{body or '(empty)'}"
    )]
    for att in attachments:
        mime = (att.get("mime") or "").lower()
        data = att.get("data")
        if not data:
            continue
        # Gemini reads images and PDFs natively as inline byte parts.
        if mime in _IMAGE_TYPES or mime == "application/pdf":
            parts.append(types.Part.from_bytes(data=data, mime_type=mime))
        # other types (docx, etc.) are skipped — same as the Claude path

    resp = await client.aio.models.generate_content(
        model=model or settings.gemini_model,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=_gemini_schema(),
            max_output_tokens=1024,
        ),
    )
    data = json.loads(resp.text)
    return {**_FALLBACK, **data}


async def extract_work_order(
    subject: str | None,
    body: str | None,
    attachments: list[dict] | None = None,
    *,
    model: str | None = None,
) -> dict:
    """Return a structured extraction dict (see _FALLBACK for shape) plus
    'missing_fields'. Never raises — dispatches to whichever provider is configured."""
    attachments = attachments or []
    result = dict(_FALLBACK)
    provider = _resolve_provider()

    try:
        if provider == "anthropic" and settings.anthropic_api_key:
            result = await _extract_anthropic(subject, body, attachments, model)
        elif provider == "gemini" and settings.gemini_api_key:
            result = await _extract_gemini(subject, body, attachments, model)
        else:
            logger.warning(
                "No extraction provider configured (set ANTHROPIC_API_KEY or GEMINI_API_KEY) — skipping"
            )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Extraction failed ({provider}): {e}")
        result = dict(_FALLBACK)

    result["missing_fields"] = _missing_fields(result)
    return result
