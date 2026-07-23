# Testing EmailAgent with a real Gmail

Goal: prove the full pipeline — a real email lands as a parsed, reviewable work order
in the dashboard. ~45–60 min of setup, mostly one-time account stuff. You do **not**
need AppFolio or Playwright for this test.

## Step 1 — Supabase (~5 min)
1. Create a project at [supabase.com](https://supabase.com).
2. **SQL Editor** → paste `backend/supabase_schema.sql` → Run.
3. **Storage** → New bucket → name it `attachments`, keep it **Private**.
4. **Project Settings → API** → copy the **Project URL** and the **service_role** key.

## Step 2 — Anthropic key (~2 min)
[console.anthropic.com](https://console.anthropic.com) → API Keys → create one.

## Step 3 — Gmail read access (~10 min, one-time)
Use a throwaway/personal Gmail for testing.
1. [console.cloud.google.com](https://console.cloud.google.com) → create a project.
2. **APIs & Services → Library** → search **Gmail API** → Enable.
3. **OAuth consent screen** → External → fill the required names → **Add your Gmail as a Test user** → add scope `.../auth/gmail.readonly`.
4. **Credentials → Create credentials → OAuth client ID → Desktop app** → copy the **Client ID** and **Client secret**.

## Step 4 — Fill `.env` and mint the Gmail token
```bash
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
cp .env.example .env
```
Edit `backend/.env`:
- `SUPABASE_URL`, `SUPABASE_KEY` (service_role from step 1)
- `ANTHROPIC_API_KEY` (step 2)
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (step 3)
- Leave `WO_SENDER_ALLOWLIST` **empty** for testing (accepts any sender)

Mint the refresh token (opens a browser, log in as the test Gmail):
```bash
.venv/Scripts/python scripts/gmail_auth.py
```
Paste the printed `GOOGLE_REFRESH_TOKEN=...` into `.env`.

## Step 5 — Preflight
```bash
.venv/Scripts/python scripts/preflight.py
```
Every line should be ✓. Fix any ✗ before continuing.

## Step 6 — Send yourself test emails
The poller looks for likely work orders (keywords in subject/body, sent in the last 2 days).
Send these **to the test Gmail** so they match:

**A — plain work order**
> Subject: `Maintenance Request – 245 Main St Apt 2B`
> Body: `Tenant John Smith in unit 2B at 245 Main Street reports the kitchen sink is leaking underneath the cabinet. Water is pooling. Please dispatch ASAP.`

**B — emergency**
> Subject: `NO HEAT unit 5 – freezing`
> Body: `The heat is out in unit 5 at 18 Oak Avenue and it's freezing. Infant in the home. Thermostat is dead.`

**C — with a photo/PDF** — same as A but attach a phone photo or a PDF of a work order (tests the multimodal + attachment path).

**D — a normal non-work-order** (e.g. a newsletter) to confirm it gets **ignored**.

## Step 7 — Run it and watch
```bash
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000   # backend
# in another terminal:
cd ../frontend && npm run dev                                       # dashboard :3000
```
In the dashboard click **"Check email"** (or wait 2 min for the auto-poll). Emails A–C
should appear under **Needs review** with fields filled; D should land in **Ignored**.
The demo banner disappears once the backend is connected.

## What you're proving
- Real emails (incl. PDFs/photos) → correctly extracted, structured work orders
- Non-work-orders filtered out
- The review/approve/edit/copy flow on real data

That's the demo-able core. AppFolio auto-entry (Phase 4) is the only piece still needing
the client's account — see `README.md`.
