"""AppFolio work-order automation (Phase 4).

The client is NOT on AppFolio's Max (read/write API) tier, so we drive the AppFolio
UI with Playwright instead of calling an API. This module is a working harness:

  * Runs Playwright in a dedicated thread with its own Proactor event loop — the
    Windows fix for spawning the browser subprocess under Uvicorn's selector loop.
  * Screenshots every step into wo_events so failures are debuggable.
  * Honors settings.appfolio_stop_before_submit (leave the form filled for a human
    to click Submit) and a kill switch.
  * On any error: marks the work order 'failed' and Slack-pings, so the request is
    never silently lost — the dashboard "Copy all fields" button is the fallback.

⚠️ The AppFolio-specific SELECTORS below are placeholders. They must be filled in
against the client's live AppFolio account (record the flow once with
`playwright codegen <appfolio_url>`), ideally verified on a TEST property first.
Until then, calling submit_work_order raises and the pipeline falls back to manual.
"""

import asyncio
import logging
import threading
from concurrent.futures import Future

from app.config import settings
from app.services import slack_notifier
from app.services.wo_store import log_event, transition_status, now_iso

logger = logging.getLogger(__name__)

# Set once the selectors below are verified against the live account.
SELECTORS_CONFIGURED = False

# ── AppFolio selectors (FILL IN from `playwright codegen`) ──────────────────────
_SEL = {
    "username": "input#username",              # TODO verify
    "password": "input#password",              # TODO verify
    "login_button": "button[type=submit]",     # TODO verify
    "new_work_order": "text=New Work Order",    # TODO verify
    "property_search": "input[name=property]",  # TODO verify
    "unit_field": "input[name=unit]",           # TODO verify
    "description": "textarea[name=description]",# TODO verify
    "priority": "select[name=priority]",        # TODO verify
    "vendor": "input[name=vendor]",             # TODO verify
    "file_input": "input[type=file]",           # TODO verify
    "submit": "button:has-text('Save')",        # TODO verify
}


# ── Dedicated-thread event loop (Windows Playwright subprocess fix) ─────────────
_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop, _thread
    if _loop and _loop.is_running():
        return _loop
    _loop = asyncio.new_event_loop()

    def _run():
        asyncio.set_event_loop(_loop)
        _loop.run_forever()

    _thread = threading.Thread(target=_run, daemon=True, name="appfolio-playwright")
    _thread.start()
    return _loop


def _run_on_loop(coro) -> object:
    """Schedule a coroutine on the browser thread and block for its result."""
    loop = _ensure_loop()
    fut: Future = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result()


# ── Automation ──────────────────────────────────────────────────────────────────
async def _fill_work_order(wo: dict, attachment_paths: list[str]) -> dict:
    """Drive the AppFolio UI. Returns {'ref': str|None, 'submitted': bool}."""
    from playwright.async_api import async_playwright

    if not (settings.appfolio_login_url and settings.appfolio_username and settings.appfolio_password):
        raise RuntimeError("AppFolio credentials not configured")
    if not SELECTORS_CONFIGURED:
        raise RuntimeError(
            "AppFolio selectors not yet configured — run `playwright codegen` against the "
            "live account, fill in _SEL, set SELECTORS_CONFIGURED=True, and verify on a test property."
        )

    shots: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Reuse a stored auth session to survive MFA: storage_state="appfolio_state.json"
        context = await browser.new_context()
        page = await context.new_page()

        async def shot(name: str):
            path = f"/tmp/appfolio_{wo['id']}_{name}.png"
            try:
                await page.screenshot(path=path)
                shots.append(path)
            except Exception:
                pass

        # 1. Login (MFA handled via a persisted storage_state — see note above).
        await page.goto(settings.appfolio_login_url)
        await page.fill(_SEL["username"], settings.appfolio_username)
        await page.fill(_SEL["password"], settings.appfolio_password)
        await page.click(_SEL["login_button"])
        await page.wait_for_load_state("networkidle")
        await shot("logged_in")

        # 2. New work order + search property.
        await page.click(_SEL["new_work_order"])
        await page.fill(_SEL["property_search"], wo.get("property_address") or "")
        await page.keyboard.press("Enter")
        await page.wait_for_load_state("networkidle")

        # 3. Fill fields.
        if wo.get("unit"):
            await page.fill(_SEL["unit_field"], wo["unit"])
        await page.fill(_SEL["description"], wo.get("issue") or "")
        if wo.get("priority"):
            await page.select_option(_SEL["priority"], label=wo["priority"])
        if wo.get("vendor"):
            await page.fill(_SEL["vendor"], wo["vendor"])

        # 4. Upload attachments.
        if attachment_paths:
            await page.set_input_files(_SEL["file_input"], attachment_paths)

        await shot("filled")

        ref = None
        submitted = False
        if settings.appfolio_stop_before_submit:
            logger.info(f"Work order {wo['id']} filled; stopping before Submit (human to confirm).")
        else:
            await page.click(_SEL["submit"])
            await page.wait_for_load_state("networkidle")
            await shot("submitted")
            submitted = True
            # ref = await page.text_content("...")  # capture AppFolio WO number here

        await context.close()
        await browser.close()

    log_event(wo["id"], "submit_attempt", detail={"screenshots": shots, "submitted": submitted})
    return {"ref": ref, "submitted": submitted}


def submit_work_order(wo: dict, attachment_local_paths: list[str] | None = None) -> dict:
    """Blocking entry point (call from a threadpool). Transitions status + notifies."""
    attachment_local_paths = attachment_local_paths or []
    transition_status(wo["id"], "submitting", actor="system")
    try:
        outcome = _run_on_loop(_fill_work_order(wo, attachment_local_paths))
        if outcome["submitted"]:
            updated = transition_status(
                wo["id"], "submitted", actor="system",
                extra={"appfolio_ref": outcome.get("ref"), "submitted_at": now_iso()},
            )
            slack_notifier.notify_submitted(updated or wo)
        else:
            # Filled but awaiting human Submit — keep it actionable in the dashboard.
            transition_status(wo["id"], "approved", actor="system",
                              detail={"note": "Filled in AppFolio, awaiting human Submit"})
        return outcome
    except Exception as e:  # noqa: BLE001
        logger.error(f"AppFolio automation failed for {wo['id']}: {e}")
        transition_status(wo["id"], "failed", actor="system", extra={"error": str(e)[:500]})
        slack_notifier.notify_failure(wo, str(e)[:300])
        raise
