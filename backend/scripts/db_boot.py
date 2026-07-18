"""Provision the database before the app starts (invoked from the Docker CMD).

Exactly one of two paths runs:

* **Fresh database + a db.sql present** in the backup directory -> restore it,
  then rename db.sql to db.bak.sql so the next boot does not restore it again.
  The dump carries its own schema, so alembic is not run on this path.
* **Otherwise** -> ``alembic upgrade head`` (creates the schema on a fresh
  database, applies pending migrations on an existing one).

Any failure propagates and exits non-zero, so the container stops instead of
serving on a half-provisioned database.
"""

import os
import subprocess
import sys

# Make the backend package root importable when run as a standalone script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_backup import BACKUP_PATH, DUMP_PATH, database_is_empty, restore  # noqa: E402


def main() -> None:
    if database_is_empty() and DUMP_PATH.exists():
        print(f"Empty database and {DUMP_PATH} present: restoring.")
        restore(DUMP_PATH)
        os.replace(DUMP_PATH, BACKUP_PATH)
        print(f"Restore complete; {DUMP_PATH.name} rotated to {BACKUP_PATH.name}.")
    else:
        print("Running 'alembic upgrade head'.")
        # Invoke via the current interpreter so it works regardless of PATH.
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)


if __name__ == "__main__":
    main()
