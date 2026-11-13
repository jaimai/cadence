"""Scheduler: `python -m app.worker`, or inside the API when EMBED_WORKER is on."""

import asyncio
import logging

from app.config import get_settings
from app.db import SessionLocal
from app.services.publisher import run_once

log = logging.getLogger("cadence.worker")


async def run_forever() -> None:
    poll = get_settings().worker_poll_seconds
    log.info("worker started, polling every %ss", poll)
    while True:
        try:
            done = await run_once(SessionLocal)
            if done:
                log.info("attempted %d publication(s)", done)
                continue  # drain the queue before sleeping
        except Exception:
            log.exception("worker tick failed")
        await asyncio.sleep(poll)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    asyncio.run(run_forever())
