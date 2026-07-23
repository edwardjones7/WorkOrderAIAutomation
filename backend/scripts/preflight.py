"""Preflight — verify every external connection before relying on the agent.

Run:  cd backend && .venv/Scripts/python scripts/preflight.py

Checks Supabase, the Storage bucket, Anthropic (Claude), and Gmail OAuth, and
prints a ✓/✗ per service so you know exactly what's wired.
"""

import os
import sys

# Make `app` importable when run as `python scripts/preflight.py` from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OK = "[ OK ]"
BAD = "[FAIL]"


def check(name: str, fn) -> bool:
    try:
        detail = fn()
        print(f"  {OK} {name}" + (f" — {detail}" if detail else ""))
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  {BAD} {name} — {str(e)[:160]}")
        return False


def supabase_check():
    from app.database import get_db
    rows = get_db().table("config").select("id").limit(1).execute()
    if not rows.data:
        raise RuntimeError("config table empty — did you run supabase_schema.sql?")
    return "connected, schema present"


def storage_check():
    from app.database import get_db
    from app.services.ingest import STORAGE_BUCKET
    buckets = get_db().storage.list_buckets()
    names = [getattr(b, "name", None) or (b.get("name") if isinstance(b, dict) else None) for b in buckets]
    if STORAGE_BUCKET not in names:
        raise RuntimeError(f'bucket "{STORAGE_BUCKET}" not found — create it (private) in Supabase Storage')
    return f'bucket "{STORAGE_BUCKET}" exists'


def ai_check():
    """Test whichever extraction provider is actually configured."""
    from app.config import settings
    from app.services.extractor import _resolve_provider

    provider = _resolve_provider()
    if provider == "anthropic":
        from anthropic import Anthropic
        Anthropic(api_key=settings.anthropic_api_key).messages.create(
            model=settings.extractor_model, max_tokens=5,
            messages=[{"role": "user", "content": "Reply OK."}],
        )
        return f"Anthropic — model {settings.extractor_model} responding"
    if provider == "gemini":
        from google import genai
        client = genai.Client(api_key=settings.gemini_api_key)
        client.models.generate_content(model=settings.gemini_model, contents="Reply OK.")
        return f"Gemini — model {settings.gemini_model} responding"
    raise RuntimeError("no provider configured (set ANTHROPIC_API_KEY or GEMINI_API_KEY)")


def gmail_check():
    from app.services import gmail_client
    svc = gmail_client._get_service()
    profile = svc.users().getProfile(userId="me").execute()
    ids = gmail_client.list_candidate_message_ids()
    return f'inbox {profile.get("emailAddress")} · {len(ids)} candidate work-order email(s) right now'


def main():
    print("\nEmailAgent preflight\n" + "-" * 40)
    results = [
        check("Supabase connection", supabase_check),
        check("Storage bucket", storage_check),
        check("AI extraction", ai_check),
        check("Gmail OAuth", gmail_check),
    ]
    print("-" * 40)
    if all(results):
        print(f"{OK} All systems go. Start the backend and hit 'Check email now'.\n")
        sys.exit(0)
    else:
        print(f"{BAD} Fix the failed items above, then re-run.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
