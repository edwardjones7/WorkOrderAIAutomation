"""Gmail API client — reads inbound work-order emails and their attachments.

Auth uses OAuth "installed app" credentials + a long-lived refresh token
(see scripts/gmail_auth.py to mint one). Only read scope is required.
"""

import base64
import logging
from email.utils import parsedate_to_datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Gmail search query for candidate work orders. Broad on purpose — Claude makes the
# final is_work_order call, so we favor recall here. `newer_than:2d` bounds the scan.
# Broad recall net across subject AND body — Gemini makes the final is_work_order call,
# so we'd rather over-fetch a few non-orders (it filters them) than miss a real one.
CANDIDATE_QUERY = (
    "newer_than:2d ("
    '"work order" OR "maintenance" OR "maintenance request" OR "service request" OR '
    "repair OR broken OR leak OR leaking OR flood OR flooding OR clog OR clogged OR "
    '"no heat" OR "no hot water" OR heat OR furnace OR HVAC OR "air conditioning" OR AC OR '
    "thermostat OR plumbing OR toilet OR sink OR faucet OR drain OR pipe OR "
    "electrical OR outlet OR breaker OR wiring OR sparked OR "
    "appliance OR dishwasher OR disposal OR refrigerator OR stove OR oven OR washer OR dryer OR "
    "pest OR roach OR rodent OR mold OR "
    "tenant OR resident OR unit OR apartment OR apt"
    ")"
)

_service = None


def _get_service():
    global _service
    if _service is None:
        if not (settings.google_client_id and settings.google_client_secret and settings.google_refresh_token):
            raise RuntimeError("Gmail OAuth not configured (google_client_id/secret/refresh_token)")
        creds = Credentials(
            token=None,
            refresh_token=settings.google_refresh_token,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
        _service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return _service


def _sender_allowed(from_email: str) -> bool:
    allowlist = [s.strip().lower() for s in settings.wo_sender_allowlist.split(",") if s.strip()]
    if not allowlist:
        return True
    return any(a in (from_email or "").lower() for a in allowlist)


def list_candidate_message_ids() -> list[str]:
    """Return Gmail message IDs matching the candidate query."""
    svc = _get_service()
    resp = svc.users().messages().list(userId="me", q=CANDIDATE_QUERY, maxResults=25).execute()
    return [m["id"] for m in resp.get("messages", [])]


def _header(headers: list[dict], name: str) -> str | None:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value")
    return None


def _walk_parts(part: dict, body_parts: list[str], attachments: list[dict]) -> None:
    """Recursively collect text bodies and attachment stubs from a MIME tree."""
    mime = part.get("mimeType", "")
    filename = part.get("filename")
    body = part.get("body", {})

    if filename:  # attachment
        attachments.append({
            "filename": filename,
            "mime": mime,
            "size_bytes": body.get("size"),
            "attachment_id": body.get("attachmentId"),
        })
    elif mime == "text/plain" and body.get("data"):
        body_parts.append(base64.urlsafe_b64decode(body["data"]).decode("utf-8", "ignore"))
    elif mime == "text/html" and body.get("data") and not body_parts:
        # Fall back to HTML only if no plain-text part found
        body_parts.append(base64.urlsafe_b64decode(body["data"]).decode("utf-8", "ignore"))

    for sub in part.get("parts", []) or []:
        _walk_parts(sub, body_parts, attachments)


def get_message(message_id: str) -> dict | None:
    """Fetch and parse one message. Returns None if the sender isn't allowed."""
    svc = _get_service()
    msg = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])

    from_email = _header(headers, "From") or ""
    if not _sender_allowed(from_email):
        logger.info(f"Skipping message {message_id}: sender not in allowlist ({from_email})")
        return None

    body_parts: list[str] = []
    attachments: list[dict] = []
    _walk_parts(payload, body_parts, attachments)

    date_raw = _header(headers, "Date")
    received_at = None
    if date_raw:
        try:
            received_at = parsedate_to_datetime(date_raw).isoformat()
        except Exception:
            pass

    return {
        "gmail_message_id": message_id,
        "gmail_thread_id": msg.get("threadId"),
        "from_email": from_email,
        "subject": _header(headers, "Subject"),
        "received_at": received_at,
        "raw_body": "\n".join(body_parts).strip(),
        "attachments": attachments,
    }


def download_attachment(message_id: str, attachment_id: str) -> bytes:
    """Download raw attachment bytes."""
    svc = _get_service()
    att = svc.users().messages().attachments().get(
        userId="me", messageId=message_id, id=attachment_id
    ).execute()
    return base64.urlsafe_b64decode(att["data"])
