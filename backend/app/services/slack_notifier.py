"""Slack notifications via incoming webhook. Best-effort — never raises."""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _webhook_url() -> str | None:
    # Prefer DB config (editable at runtime) then env.
    try:
        from app.database import get_db
        row = get_db().table("config").select("slack_webhook_url").eq("id", 1).single().execute()
        if row.data and row.data.get("slack_webhook_url"):
            return row.data["slack_webhook_url"]
    except Exception:
        pass
    return settings.slack_webhook_url


def _post(blocks: list[dict], text: str) -> None:
    url = _webhook_url()
    if not url:
        logger.debug("No Slack webhook configured — skipping notification")
        return
    try:
        httpx.post(url, json={"text": text, "blocks": blocks}, timeout=10)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Slack post failed: {e}")


def notify_new_work_order(wo: dict) -> None:
    emoji = "🚨" if wo.get("is_emergency") else "🔧"
    link = f"{settings.dashboard_url}/?wo={wo['id']}"
    addr = wo.get("property_address") or "Unknown property"
    unit = f" · Unit {wo['unit']}" if wo.get("unit") else ""
    priority = wo.get("priority") or "—"
    issue = wo.get("issue") or "(no description)"
    missing = wo.get("missing_fields") or []
    missing_line = f"\n⚠️ Missing: {', '.join(missing)}" if missing else ""

    text = f"{emoji} New work order to review: {addr}{unit} — {issue}"
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"{emoji} *New work order to review*\n*{addr}*{unit}\n"
                    f"*Issue:* {issue}\n*Priority:* {priority}"
                    f"{missing_line}"}},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Review & approve"},
             "url": link, "style": "primary"}]},
    ]
    _post(blocks, text)


def notify_submitted(wo: dict) -> None:
    addr = wo.get("property_address") or "work order"
    ref = wo.get("appfolio_ref")
    ref_line = f" (AppFolio ref {ref})" if ref else ""
    _post(
        [{"type": "section", "text": {"type": "mrkdwn",
            "text": f"✅ Work order submitted to AppFolio: *{addr}*{ref_line}"}}],
        f"✅ Work order submitted: {addr}",
    )


def notify_failure(wo: dict, error: str) -> None:
    addr = wo.get("property_address") or "work order"
    link = f"{settings.dashboard_url}/?wo={wo['id']}"
    _post(
        [{"type": "section", "text": {"type": "mrkdwn",
            "text": f"❌ AppFolio submission FAILED for *{addr}*\n> {error}\n"
                    f"Falling back to manual entry — <{link}|open in dashboard>"}}],
        f"❌ AppFolio submission failed: {addr}",
    )
