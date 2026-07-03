"""Daily background job: book recurring entries that have fallen due.

The container has no cron, so a lightweight asyncio task runs a generation pass
at startup and then every 24 h, over **every** association. The pass is
idempotent (it advances ``prochaine_echeance`` past what it books), so it never
duplicates an occurrence even if it overlaps a manual "generate now" trigger.
"""

import asyncio
import logging

from sqlmodel import Session

from database import engine
from recurrence_engine import generate_due

logger = logging.getLogger("abacus.scheduler")

_DAY_SECONDS = 24 * 60 * 60


def run_generation_pass() -> int:
    """One generation pass over all associations, in its own transaction."""
    with Session(engine) as session:
        generated = generate_due(session)
        session.commit()
    return generated


async def recurrences_daily_loop(interval_seconds: int = _DAY_SECONDS) -> None:
    """Run a generation pass now, then once per ``interval_seconds``, forever."""
    while True:
        try:
            # Offload the blocking DB work so the event loop stays responsive.
            generated = await asyncio.to_thread(run_generation_pass)
            if generated:
                logger.info("Récurrences : %d écriture(s) générée(s).", generated)
        except Exception:  # never let a transient error kill the loop
            logger.exception("Échec de la génération des récurrences.")
        await asyncio.sleep(interval_seconds)
