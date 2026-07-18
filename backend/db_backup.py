"""PostgreSQL backup and restore for the single-container deployment.

Two responsibilities, both derived from the app's ``DATABASE_URL``:

* **Recurring dump** (driven by :func:`main.lifespan`): every
  ``BACKUP_INTERVAL_SECONDS`` the database is dumped to ``<BACKUP_DIR>/db.sql``.
  The previous dump is rotated to ``db.bak.sql``; two generations are kept.
* **Boot-time restore** (driven by :mod:`scripts.db_boot`): when the database
  is still empty and a ``db.sql`` file is present in ``BACKUP_DIR``, it is
  restored, then renamed to ``db.bak.sql`` so it is not restored again.

Both paths shell out to the standard client tools (``pg_dump``/``psql``), which
the runtime image installs. Connection parameters are passed via libpq's ``PG*``
environment variables, so a password with special characters needs no escaping.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import make_url

from database import DATABASE_URL, engine

logger = logging.getLogger(__name__)

# Directory holding the dumps. Bind-mounted from the host in docker-compose so
# operators can drop a db.sql in and pick backups up. Relative to the workdir.
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "backup-db"))
DUMP_PATH = BACKUP_DIR / "db.sql"
BACKUP_PATH = BACKUP_DIR / "db.bak.sql"

# One dump per hour by default; set to 0 (or less) to disable the recurring dump.
BACKUP_INTERVAL_SECONDS = int(os.getenv("BACKUP_INTERVAL_SECONDS", "3600"))

# A table present in every revision of the schema: its existence tells us the
# database has already been provisioned (by alembic or by a prior restore).
_SENTINEL_TABLE = "association"


def _pg_env() -> dict[str, str]:
    """Environment for pg_dump/psql, with connection settings from DATABASE_URL.

    libpq reads these PG* variables, which sidesteps any URL-encoding concern
    with special characters in the password.
    """
    url = make_url(DATABASE_URL)
    env = os.environ.copy()
    env["PGHOST"] = url.host or "localhost"
    env["PGPORT"] = str(url.port or 5432)
    if url.username:
        env["PGUSER"] = url.username
    if url.password:
        env["PGPASSWORD"] = url.password
    if url.database:
        env["PGDATABASE"] = url.database
    return env


def database_is_empty() -> bool:
    """True when the schema has not been provisioned yet."""
    return not inspect(engine).has_table(_SENTINEL_TABLE)


def dump() -> Path:
    """Dump the database to db.sql, rotating the previous dump to db.bak.sql.

    The dump is written to a temporary file and moved into place only on
    success, so an interrupted or failed dump never corrupts db.sql. The dump
    carries ``DROP ... IF EXISTS`` (``--clean --if-exists``) so it can be
    restored into a non-empty database as well.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = DUMP_PATH.with_name(DUMP_PATH.name + ".tmp")

    cmd = [
        "pg_dump",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--file",
        str(tmp_path),
    ]
    try:
        subprocess.run(cmd, env=_pg_env(), check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"pg_dump failed: {exc.stderr.strip()}") from exc

    # Rotate: the current dump becomes the backup, the new one takes its place.
    if DUMP_PATH.exists():
        os.replace(DUMP_PATH, BACKUP_PATH)
    os.replace(tmp_path, DUMP_PATH)
    return DUMP_PATH


def restore(path: Path) -> None:
    """Restore a plain-SQL dump into the current database with psql.

    ``ON_ERROR_STOP`` makes psql abort on the first error instead of limping
    through a half-applied restore.
    """
    cmd = ["psql", "--set", "ON_ERROR_STOP=1", "--quiet", "--file", str(path)]
    try:
        subprocess.run(cmd, env=_pg_env(), check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"psql restore failed: {exc.stderr.strip()}") from exc


async def _backup_loop() -> None:
    """Dump immediately, then once per interval, until cancelled."""
    while True:
        try:
            path = await asyncio.to_thread(dump)
            logger.info("Database dumped to %s", path)
        except Exception:
            logger.warning("Scheduled database dump failed", exc_info=True)
        await asyncio.sleep(BACKUP_INTERVAL_SECONDS)


def start_backup_task() -> asyncio.Task | None:
    """Start the recurring dump as a background task, if applicable.

    Returns the task (to stop on shutdown), or ``None`` when the dump is
    disabled or the database is not PostgreSQL (e.g. SQLite in dev/tests).
    """
    if BACKUP_INTERVAL_SECONDS <= 0:
        logger.info("Recurring database dump disabled (BACKUP_INTERVAL_SECONDS <= 0).")
        return None
    if not DATABASE_URL.startswith("postgresql"):
        logger.info("Recurring database dump disabled (non-PostgreSQL database).")
        return None
    return asyncio.create_task(_backup_loop())


async def stop_backup_task(task: asyncio.Task | None) -> None:
    """Cancel the recurring dump task and wait for it to unwind."""
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
