"""Daily background job: book recurring entries that have fallen due.

The container has no cron, so a lightweight asyncio task runs the generation over
**every** association: once at startup (catch-up for whatever fell due while the
app was down), then every day at a fixed local hour. The pass is idempotent (it
advances ``prochaine_echeance`` past what it books), so a startup catch-up
overlapping the daily run — or a manual trigger — never duplicates an occurrence.

Schedule is configurable, defaulting to 06:00 Europe/Paris:
* ``RECURRENCE_HOUR`` — hour of day (0–23);
* ``RECURRENCE_TZ`` — IANA timezone name (``tzdata`` ships the database).
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlmodel import Session

from database import engine
from recurrence_engine import generate_due

logger = logging.getLogger("abacus.scheduler")

DEFAULT_HOUR = 6
DEFAULT_TZ = "Europe/Paris"


def _configured_hour() -> int:
    raw = os.getenv("RECURRENCE_HOUR")
    if raw is None:
        return DEFAULT_HOUR
    try:
        hour = int(raw)
    except ValueError:
        logger.warning(
            "RECURRENCE_HOUR invalide (%r), repli sur %d h.", raw, DEFAULT_HOUR
        )
        return DEFAULT_HOUR
    if not 0 <= hour <= 23:
        logger.warning(
            "RECURRENCE_HOUR hors plage (%d), repli sur %d h.", hour, DEFAULT_HOUR
        )
        return DEFAULT_HOUR
    return hour


def _configured_tz() -> ZoneInfo:
    name = os.getenv("RECURRENCE_TZ", DEFAULT_TZ)
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("RECURRENCE_TZ inconnu (%r), repli sur %s.", name, DEFAULT_TZ)
        return ZoneInfo(DEFAULT_TZ)


def seconds_until_next_run(now: datetime, hour: int) -> float:
    """Seconds from ``now`` to the next ``hour``:00 (in ``now``'s timezone).

    If today's target time has already passed, the next run is tomorrow.
    """
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def run_generation_pass() -> int:
    """One generation pass over all associations, in its own transaction."""
    with Session(engine) as session:
        generated = generate_due(session)
        session.commit()
    return generated


async def _run_pass() -> None:
    try:
        # Offload the blocking DB work so the event loop stays responsive.
        generated = await asyncio.to_thread(run_generation_pass)
        if generated:
            logger.info("Récurrences : %d écriture(s) générée(s).", generated)
    except Exception:  # never let a transient error kill the loop
        logger.exception("Échec de la génération des récurrences.")


async def recurrences_daily_loop() -> None:
    """Catch up at startup, then run every day at the configured hour/timezone."""
    hour = _configured_hour()
    tz = _configured_tz()
    await _run_pass()  # startup catch-up (idempotent)
    while True:
        await asyncio.sleep(seconds_until_next_run(datetime.now(tz), hour))
        await _run_pass()
