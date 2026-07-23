"""Phase-4 DEMO — fills the mock AppFolio 'New Work Order' form from a real,
AI-extracted work order using Playwright, exactly the way the production
automation will drive the real AppFolio UI.

Run (from backend/):
    .venv/Scripts/python scripts/demo_appfolio_fill.py            # newest needs_review order
    .venv/Scripts/python scripts/demo_appfolio_fill.py <wo_id>    # a specific one
    HEADLESS=1 .venv/Scripts/python scripts/demo_appfolio_fill.py # no visible window

A browser window opens and you watch it type the work order in, then submit.
When you get real AppFolio access, swap FORM_URL + the selector map for the live
page (record it with `playwright codegen`) — the fill logic is unchanged.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

from app.database import get_db

FORM_URL = (Path(__file__).parent.parent / "mock_appfolio" / "new_work_order.html").resolve().as_uri()

# Selector map — the ONLY thing that changes when pointing at real AppFolio.
SEL = {
    "property": "#property",
    "unit": "#unit",
    "resident": "#resident",
    "category": "#category",
    "priority": "#priority",
    "vendor": "#vendor",
    "description": "#description",
    "submit": "#submit-wo",
    "ref": "#wo-ref",
}


def _pick_work_order(wo_id: str | None) -> dict:
    db = get_db()
    if wo_id:
        row = db.table("work_orders").select("*").eq("id", wo_id).single().execute().data
        if not row:
            sys.exit(f"No work order with id {wo_id}")
        return row
    rows = (
        db.table("work_orders").select("*")
        .in_("status", ["needs_review", "approved"])
        .eq("is_work_order", True)
        .order("received_at", desc=True).limit(1).execute().data
    )
    if not rows:
        sys.exit("No needs_review/approved work orders found — ingest some first.")
    return rows[0]


def main() -> None:
    wo = _pick_work_order(sys.argv[1] if len(sys.argv) > 1 else None)
    headless = bool(os.environ.get("HEADLESS"))

    print(f"\nFilling work order into mock AppFolio:")
    print(f"  {wo.get('property_address')} · Unit {wo.get('unit')} · {wo.get('category')} · {wo.get('priority')}")
    print(f"  {wo.get('issue')}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=0 if headless else 550)
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        page.goto(FORM_URL)

        def fill(sel: str, value):
            if value:
                page.fill(SEL[sel], str(value))

        # Type it in — same calls the real integration will make.
        fill("property", wo.get("property_address"))
        fill("unit", wo.get("unit"))
        fill("resident", wo.get("resident_name"))
        if wo.get("category"):
            page.select_option(SEL["category"], label=wo["category"])
        if wo.get("priority"):
            page.select_option(SEL["priority"], label=wo["priority"])
        fill("vendor", wo.get("vendor"))
        fill("description", wo.get("issue"))

        shot_filled = str(Path(__file__).parent.parent / "mock_appfolio" / "_filled.png")
        page.screenshot(path=shot_filled)

        # Submit + capture the generated reference.
        page.click(SEL["submit"])
        page.wait_for_selector(f"{SEL['ref']}")
        ref = page.text_content(SEL["ref"])
        shot_done = str(Path(__file__).parent.parent / "mock_appfolio" / "_submitted.png")
        page.screenshot(path=shot_done)

        print(f"  Submitted. AppFolio reference: {ref}")
        print(f"  Screenshots: {shot_filled}\n               {shot_done}")

        if not headless:
            page.wait_for_timeout(3500)  # let you see the confirmation
        browser.close()


if __name__ == "__main__":
    main()
