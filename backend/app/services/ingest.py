"""Ingestion orchestrator: Gmail candidate -> download attachments -> Storage ->
Claude extraction -> work_orders row -> Slack notify.

Idempotent: a message already present in work_orders (unique gmail_message_id) is
skipped. Safe to run on every poll tick.
"""

import logging

from app.config import settings
from app.database import get_db
from app.services import gmail_client, extractor, slack_notifier
from app.services.wo_store import log_event

logger = logging.getLogger(__name__)

STORAGE_BUCKET = "attachments"

# Below this confidence a "work order" still goes to needs_review (never auto-ignored)
# so a human always sees borderline cases. Non-work-orders are marked ignored.
_LOW_CONF = 0.35


def _already_ingested(message_id: str) -> bool:
    try:
        res = (
            get_db().table("work_orders").select("id").eq("gmail_message_id", message_id).limit(1).execute()
        )
        return bool(res.data)
    except Exception:
        return False


def _upload_attachment(work_order_placeholder: str, filename: str, mime: str, data: bytes) -> str | None:
    """Upload bytes to Supabase Storage, return the storage path (or None on failure)."""
    path = f"{work_order_placeholder}/{filename}"
    try:
        get_db().storage.from_(STORAGE_BUCKET).upload(
            path, data, {"content-type": mime or "application/octet-stream", "upsert": "true"}
        )
        return path
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Attachment upload failed for {filename}: {e}")
        return None


async def process_message(message_id: str) -> dict | None:
    """Process a single Gmail message into a work_orders row. Returns the row or None."""
    if _already_ingested(message_id):
        return None

    parsed = gmail_client.get_message(message_id)
    if parsed is None:  # sender not allowed
        return None

    db = get_db()

    # Download attachments (bytes for extraction + upload to Storage).
    attachments_for_ai: list[dict] = []
    attachment_meta: list[dict] = []
    for att in parsed.get("attachments", []):
        att_id = att.get("attachment_id")
        if not att_id:
            continue
        try:
            data = gmail_client.download_attachment(message_id, att_id)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not download attachment {att.get('filename')}: {e}")
            continue
        attachments_for_ai.append({"filename": att["filename"], "mime": att["mime"], "data": data})
        attachment_meta.append({**att, "_data": data})

    # Extract.
    result = await extractor.extract_work_order(
        parsed.get("subject"), parsed.get("raw_body"), attachments_for_ai
    )

    # Decide status. Human always approves (per client config), so real work orders
    # land in needs_review; clear non-work-orders are auto-ignored.
    if not result.get("is_work_order") or result.get("confidence", 0) < _LOW_CONF:
        status = "ignored" if not result.get("is_work_order") else "needs_review"
    else:
        status = "needs_review"

    row = {
        "gmail_message_id": parsed["gmail_message_id"],
        "gmail_thread_id": parsed.get("gmail_thread_id"),
        "from_email": parsed.get("from_email"),
        "subject": parsed.get("subject"),
        "received_at": parsed.get("received_at"),
        "raw_body": parsed.get("raw_body"),
        "extracted": {k: v for k, v in result.items() if k != "missing_fields"},
        "property_address": result.get("property_address"),
        "unit": result.get("unit"),
        "resident_name": result.get("resident_name"),
        "issue": result.get("issue"),
        "category": result.get("category"),
        "priority": result.get("priority"),
        "vendor": result.get("vendor"),
        "is_emergency": bool(result.get("is_emergency")),
        "is_work_order": bool(result.get("is_work_order")),
        "confidence": result.get("confidence"),
        "missing_fields": result.get("missing_fields", []),
        "status": status,
    }

    try:
        inserted = db.table("work_orders").insert(row).execute()
    except Exception as e:  # noqa: BLE001 — unique-index race => already ingested
        logger.info(f"Insert skipped for {message_id} (likely duplicate): {e}")
        return None

    wo = inserted.data[0]
    wo_id = wo["id"]
    log_event(wo_id, "ingested", to_status=status, detail={"from": parsed.get("from_email")})

    # Persist attachments (upload under the real work-order id).
    for att in attachment_meta:
        path = _upload_attachment(wo_id, att["filename"], att["mime"], att["_data"])
        try:
            db.table("attachments").insert({
                "work_order_id": wo_id,
                "filename": att["filename"],
                "mime": att["mime"],
                "size_bytes": att.get("size_bytes"),
                "storage_path": path,
            }).execute()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Attachment row insert failed: {e}")

    # Notify the team for anything needing review.
    if status == "needs_review":
        slack_notifier.notify_new_work_order(wo)

    logger.info(f"Ingested {message_id} -> work_order {wo_id} ({status})")
    return wo


async def process_new_emails() -> int:
    """Poll Gmail once and process all candidate messages. Returns count ingested."""
    try:
        cfg = get_db().table("config").select("ingestion_enabled").eq("id", 1).single().execute()
        if cfg.data and cfg.data.get("ingestion_enabled") is False:
            logger.info("Ingestion disabled by config kill switch — skipping poll")
            return 0
    except Exception:
        pass

    try:
        ids = gmail_client.list_candidate_message_ids()
    except Exception as e:  # noqa: BLE001
        logger.error(f"Gmail poll failed: {e}")
        return 0

    count = 0
    for mid in ids:
        try:
            if await process_message(mid):
                count += 1
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to process message {mid}: {e}")
    if count:
        logger.info(f"Poll complete: {count} new work order(s) ingested")
    return count
