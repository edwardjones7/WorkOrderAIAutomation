"""Work-order REST API for the dashboard."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query

from app.database import get_db
from app.models.work_order import WorkOrderUpdate
from app.services import slack_notifier
from app.services.ingest import STORAGE_BUCKET
from app.services.wo_store import log_event, transition_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/work-orders", tags=["work-orders"])


@router.get("")
def list_work_orders(
    status: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
):
    db = get_db()
    q = db.table("work_orders").select("*")
    if status:
        # allow comma-separated list, e.g. ?status=needs_review,approved
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        q = q.in_("status", statuses) if len(statuses) > 1 else q.eq("status", statuses[0])
    q = q.order("received_at", desc=True).range(offset, offset + limit - 1)
    return q.execute().data


@router.get("/stats")
def stats():
    db = get_db()
    rows = db.table("work_orders").select("status").execute().data or []
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return counts


@router.get("/{wo_id}")
def get_work_order(wo_id: str):
    db = get_db()
    wo = db.table("work_orders").select("*").eq("id", wo_id).single().execute().data
    if not wo:
        raise HTTPException(404, "Work order not found")
    atts = db.table("attachments").select("*").eq("work_order_id", wo_id).execute().data or []
    # Sign attachment URLs (1h) for preview in the dashboard.
    for a in atts:
        if a.get("storage_path"):
            try:
                signed = db.storage.from_(STORAGE_BUCKET).create_signed_url(a["storage_path"], 3600)
                a["signed_url"] = signed.get("signedURL") or signed.get("signedUrl")
            except Exception:
                a["signed_url"] = None
    events = (
        db.table("wo_events").select("*").eq("work_order_id", wo_id)
        .order("created_at", desc=True).limit(50).execute().data or []
    )
    return {**wo, "attachments": atts, "events": events}


@router.patch("/{wo_id}")
def update_work_order(wo_id: str, update: WorkOrderUpdate):
    db = get_db()
    data = update.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(400, "No fields to update")
    result = db.table("work_orders").update(data).eq("id", wo_id).execute()
    if not result.data:
        raise HTTPException(404, "Work order not found")
    log_event(wo_id, "note", actor="user", detail={"edited_fields": list(data.keys())})
    return result.data[0]


@router.post("/{wo_id}/ignore")
def ignore_work_order(wo_id: str):
    wo = transition_status(wo_id, "ignored", actor="user")
    if not wo:
        raise HTTPException(404, "Work order not found")
    return wo


@router.post("/{wo_id}/approve")
async def approve_work_order(wo_id: str):
    """Human approval → hand off to AppFolio automation (or manual fallback)."""
    db = get_db()
    wo = db.table("work_orders").select("*").eq("id", wo_id).single().execute().data
    if not wo:
        raise HTTPException(404, "Work order not found")

    transition_status(wo_id, "approved", actor="user")
    log_event(wo_id, "approved", to_status="approved", actor="user")

    # Fire the browser automation off the request thread. If selectors aren't yet
    # configured it will fail gracefully -> 'failed' + Slack, and the dashboard
    # "Copy all fields" fallback covers manual entry.
    from app.services.appfolio_agent import submit_work_order

    async def _run():
        try:
            await asyncio.to_thread(submit_work_order, wo, [])
        except Exception as e:  # noqa: BLE001 — already logged + Slack-notified inside
            logger.info(f"Automation for {wo_id} ended in fallback: {e}")

    asyncio.create_task(_run())
    return {"ok": True, "status": "approved", "message": "Approved — submitting to AppFolio"}


@router.get("/{wo_id}/copy-text")
def copy_text(wo_id: str):
    """Plain-text block for the manual 'Copy all fields' fallback button."""
    db = get_db()
    wo = db.table("work_orders").select("*").eq("id", wo_id).single().execute().data
    if not wo:
        raise HTTPException(404, "Work order not found")
    lines = [
        f"Property: {wo.get('property_address') or ''}",
        f"Unit: {wo.get('unit') or ''}",
        f"Resident: {wo.get('resident_name') or ''}",
        f"Category: {wo.get('category') or ''}",
        f"Priority: {wo.get('priority') or ''}",
        f"Vendor: {wo.get('vendor') or ''}",
        f"Description: {wo.get('issue') or ''}",
    ]
    return {"text": "\n".join(lines)}
