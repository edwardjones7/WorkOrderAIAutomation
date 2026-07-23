"""Set dummy env before app.config is imported so unit tests can import modules
without a real .env. Real keys (if present in the environment) are left untouched."""

import os

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
