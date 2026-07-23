"""APScheduler setup — polls Gmail for new work orders on an interval."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings

logger = logging.getLogger(__name__)

scheduler_instance = AsyncIOScheduler()


def register_gmail_poll_job() -> None:
    scheduler_instance.add_job(
        _poll_gmail,
        trigger="interval",
        seconds=settings.gmail_poll_seconds,
        id="gmail_poll",
        replace_existing=True,
        misfire_grace_time=60,
        max_instances=1,  # never overlap polls
    )
    logger.info(f"Registered Gmail poll job (every {settings.gmail_poll_seconds}s)")


async def _poll_gmail() -> None:
    from app.services.ingest import process_new_emails
    try:
        await process_new_emails()
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Gmail poll job errored: {e}")
