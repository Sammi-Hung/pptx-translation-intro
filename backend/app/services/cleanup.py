import asyncio
import logging

from app.core.config import Settings
from app.services.job_store import JobStore

logger = logging.getLogger(__name__)


async def cleanup_loop(settings: Settings, store: JobStore) -> None:
    while True:
        await asyncio.sleep(settings.cleanup_interval_seconds)
        try:
            removed = store.cleanup_expired()
            if removed:
                logger.info("Removed %s expired job folders", removed)
        except Exception:
            logger.exception("Expired job cleanup failed")

