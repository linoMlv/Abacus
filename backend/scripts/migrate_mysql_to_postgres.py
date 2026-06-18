"""One-off data migration: MySQL -> PostgreSQL.

Copies every row of every table from the legacy MySQL database into a fresh
PostgreSQL database, then validates the result by comparing row counts and
monetary totals on both sides.

The PostgreSQL schema must already exist and be empty: run
`alembic upgrade head` against the target before this script.

Usage:
    SOURCE_DATABASE_URL="mysql+pymysql://user:pass@host:3306/abacus" \
    DATABASE_URL="postgresql+psycopg://user:pass@host:5432/abacus" \
    python scripts/migrate_mysql_to_postgres.py [--dry-run]

The migration runs inside a single transaction on the target: if validation
fails, nothing is committed. Re-running against a non-empty target is refused.

This script needs both drivers; install requirements-migration.txt.
"""

import argparse
import os
import sys
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, create_engine, select

# Ensure the backend package root is importable when run as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ApiKey, Association, Balance, LogEntry, Operation  # noqa: E402

# Insertion order respects foreign keys (parents before children).
MODELS = [Association, Balance, Operation, ApiKey, LogEntry]

# Tables that carry monetary totals worth checksumming.
SUM_CHECKS = [
    (Balance, Balance.initialAmount),
    (Operation, Operation.amount),
]


def _require_url(name: str) -> str:
    url = os.getenv(name)
    if not url:
        sys.exit(f"Environment variable {name} is required.")
    return url


def _count(session: Session, model) -> int:
    return session.exec(select(func.count()).select_from(model)).one()


def _sum(session: Session, model, column) -> Decimal:
    total = session.exec(select(func.coalesce(func.sum(column), 0))).one()
    return Decimal(str(total))


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate MySQL data to PostgreSQL.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Copy and validate, then roll back instead of committing.",
    )
    args = parser.parse_args()

    source_engine = create_engine(_require_url("SOURCE_DATABASE_URL"))
    target_engine = create_engine(_require_url("DATABASE_URL"))

    with Session(source_engine) as source, Session(target_engine) as target:
        # Refuse to run against a target that already holds data.
        existing = {m.__name__: _count(target, m) for m in MODELS}
        if any(existing.values()):
            sys.exit(
                "Target database is not empty: "
                + ", ".join(f"{k}={v}" for k, v in existing.items() if v)
            )

        # Copy every table, parents first.
        for model in MODELS:
            rows = source.exec(select(model)).all()
            for row in rows:
                target.add(model(**row.model_dump()))
            target.flush()
            print(f"  copied {len(rows):>6} rows into {model.__tablename__}")

        # Validate row counts and monetary totals before committing.
        print("\nValidation:")
        ok = True

        def report(kind: str, name: str, src, dst) -> bool:
            match = src == dst
            flag = "OK" if match else "MISMATCH"
            print(f"  {kind:<5} {name:<12} source={src:<10} target={dst:<10} {flag}")
            return match

        for model in MODELS:
            src, dst = _count(source, model), _count(target, model)
            ok = report("count", model.__tablename__, src, dst) and ok

        for model, column in SUM_CHECKS:
            src, dst = _sum(source, model, column), _sum(target, model, column)
            ok = report("sum", model.__tablename__, src, dst) and ok

        if not ok:
            target.rollback()
            sys.exit("\nValidation failed: target rolled back, nothing committed.")

        if args.dry_run:
            target.rollback()
            print("\nDry run: validation passed, target rolled back.")
            return

        target.commit()
        print("\nMigration committed successfully.")


if __name__ == "__main__":
    main()
