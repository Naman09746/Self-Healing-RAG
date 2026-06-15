#!/usr/bin/env python3
"""Migrate data from SQLite to PostgreSQL.

Copies all tables defined in ``backend.storage.db.models`` from the
current SQLite database (``DATABASE_URL_SQLITE``) to a PostgreSQL
instance (``DATABASE_URL``).

Both connections are synchronous (SQLite natively so, and Postgres
via psycopg2) so this script runs in a single thread.

Usage:
    python scripts/migrate_sqlite_to_postgres.py

Environment variables:
    DATABASE_URL         — target PostgreSQL connection (asyncpg-style is auto-rewritten)
    DATABASE_URL_SQLITE  — source SQLite path (default: ./nexus_core.db)
"""

import os
import re
import sys

# Ensure the project root is on sys.path for model imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, MetaData, inspect
from sqlalchemy.orm import Session


def _to_sync_pg(url: str) -> str:
    """Rewrite asyncpg → psycopg2 so the sync engine works."""
    return re.sub(r"^postgresql\+asyncpg://", "postgresql+psycopg2://", url)


def get_table_order(metadata: MetaData):
    """Return table names in dependency order (parents first)."""
    ordered = []
    seen = set()

    def resolve(table):
        if table.name in seen:
            return
        for fk in table.foreign_key_constraints:
            if fk.referred_table.name not in seen:
                resolve(fk.referred_table)
        seen.add(table.name)
        ordered.append(table.name)

    for table in metadata.sorted_tables:
        resolve(table)

    return ordered


def migrate():
    pg_url = _to_sync_pg(os.environ.get("DATABASE_URL", ""))
    if not pg_url:
        print("FATAL: DATABASE_URL environment variable is not set.")
        sys.exit(1)

    sqlite_url = os.environ.get(
        "DATABASE_URL_SQLITE",
        f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'nexus_core.db')}",
    )

    print(f"Source     (SQLite): {sqlite_url}")
    print(f"Target  (Postgres): {pg_url}")

    sqlite_engine = create_engine(sqlite_url, echo=False)
    pg_engine = create_engine(pg_url, echo=False)

    # Reflect metadata from SQLite
    sqlite_meta = MetaData()
    sqlite_meta.reflect(bind=sqlite_engine)

    # Reflect target metadata to see what already exists
    pg_meta = MetaData()
    pg_meta.reflect(bind=pg_engine)

    table_order = get_table_order(sqlite_meta)
    total_rows = 0

    for table_name in table_order:
        if table_name == "alembic_version":
            continue  # skip Alembic's own table

        src_table = sqlite_meta.tables.get(table_name)
        if src_table is None:
            continue

        print(f"\n--- {table_name} ---")

        # Fetch all rows from SQLite
        with Session(sqlite_engine) as session:
            rows = session.execute(src_table.select()).mappings().all()

        if not rows:
            print(f"  → 0 rows (skip)")
            continue

        # Insert into Postgres
        with Session(pg_engine) as session:
            session.execute(pg_engine.dialect.statement_compiler(
                pg_engine.dialect,
                None
            ).__class__.__module__)
            # Convert Row mappings to dicts
            dict_rows = [dict(r) for r in rows]
            session.execute(src_table.insert(), dict_rows)
            session.commit()

        total_rows += len(rows)
        print(f"  ✔ {len(rows)} rows migrated")

    print(f"\n{'='*40}")
    print(f"Migration complete. {total_rows} total rows copied.")
    print(f"{'='*40}")


if __name__ == "__main__":
    migrate()