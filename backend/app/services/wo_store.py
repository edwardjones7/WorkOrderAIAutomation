"""Work-order state store — status transitions + append-only audit log.

Mirrors LeadGen's pipeline.py: every write is best-effort so a logging failure
never breaks the pipeline, and every status change lands in `wo_events`.
"""

import logging
from datetime import datetime, timezone

from app.database import get_db

logger = logging.getLogger(__name__)


def log_event(
    work_order_id: str | None,
    event_type: str,
    *,
    from_status: str | None = None,
    to_status: str | None = None,
    actor: str = "system",
    detail: dict | None = None,
) -> None:
    """Append an event to wo_events. Best-effort — swallows errors."""
    try:
        get_db().table("wo_events").insert({
            "work_order_id": work_order_id,
            "event_type": event_type,
            "from_status": from_status,
            "to_status": to_status,
            "actor": actor,
            "detail": detail or {},
        }).execute()
    except Exception as e:  # noqa: BLE001 — logging must never crash callers
        logger.warning(f"wo_events insert failed ({event_type}): {e}")


def transition_status(
    work_order_id: str,
    to_status: str,
    *,
    actor: str = "system",
    extra: dict | None = None,
    detail: dict | None = None,
) -> dict | None:
    """Move a work order to `to_status`, log the change, return the updated row."""
    db = get_db()
    try:
        current = (
            db.table("work_orders").select("status").eq("id", work_order_id).single().execute()
        ).data
        from_status = current["status"] if current else None
    except Exception:
        from_status = None

    update = {"status": to_status, **(extra or {})}
    try:
        result = db.table("work_orders").update(update).eq("id", work_order_id).execute()
    except Exception as e:  # noqa: BLE001
        logger.error(f"transition_status failed for {work_order_id}: {e}")
        return None

    log_event(
        work_order_id,
        "status_change",
        from_status=from_status,
        to_status=to_status,
        actor=actor,
        detail=detail,
    )
    return result.data[0] if result.data else None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
