"""One-time helper: mint a Gmail refresh token for the ingestion service.

Prereqs:
  1. In Google Cloud Console, enable the Gmail API.
  2. Create an OAuth client of type "Desktop app". Download nothing — just copy the
     client ID and secret.
  3. pip install google-auth-oauthlib
  4. Run:  python scripts/gmail_auth.py
     It opens a browser, you log in as the mailbox owner, and it prints a
     GOOGLE_REFRESH_TOKEN to paste into backend/.env.

Read-only scope only.
"""

import os
import sys

# Make `app` importable when run as `python scripts/gmail_auth.py` from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _creds_from_env() -> tuple[str | None, str | None]:
    """Read client id/secret from backend/.env via settings, falling back to env vars."""
    try:
        from app.config import settings
        return settings.google_client_id, settings.google_client_secret
    except Exception:
        return os.environ.get("GOOGLE_CLIENT_ID"), os.environ.get("GOOGLE_CLIENT_SECRET")


def main() -> None:
    client_id, client_secret = _creds_from_env()
    client_id = client_id or input("Google client ID: ").strip()
    client_secret = client_secret or input("Google client secret: ").strip()

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    # access_type=offline + prompt=consent guarantees a refresh token is returned.
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    if not creds.refresh_token:
        print("No refresh token returned. Revoke prior access and retry with prompt=consent.", file=sys.stderr)
        sys.exit(1)

    print("\n=== Paste this into backend/.env ===")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
