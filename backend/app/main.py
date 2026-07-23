import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import work_orders
from app.scheduler import scheduler_instance, register_gmail_poll_job

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_instance.start()
    register_gmail_poll_job()
    yield
    scheduler_instance.shutdown(wait=False)


app = FastAPI(title="Elenos EmailAgent — Work Order Automation", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(work_orders.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/poll-now")
async def poll_now():
    """Manually trigger a Gmail poll (handy for testing without waiting for the interval)."""
    from app.services.ingest import process_new_emails
    count = await process_new_emails()
    return {"ingested": count}
