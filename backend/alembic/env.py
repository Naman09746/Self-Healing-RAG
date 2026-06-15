"""Alembic environment configuration for Self-Healing RAG Pipeline.

This module configures Alembic to work with our SQLAlchemy models.
It handles the async-to-sync URL conversion: the application uses
``postgresql+asyncpg://`` at runtime, but Alembic runs synchronously
with ``psycopg2``. The ``DATABASE_URL`` environment variable is rewritten
automatically when present.

Usage:
    alembic upgrade head
    alembic downgrade -1
    alembic revision --autogenerate -m "description"
"""

import os
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config object, which provides access to values in alembic.ini
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so Alembic can detect them via Base.metadata
from backend.storage.db.models import Base  # noqa: E402

target_metadata = Base.metadata


def _rewrite_async_url(url: str) -> str:
    """Convert ``postgresql+asyncpg://`` → ``postgresql+psycopg2://``.

    Alembic runs synchronously; the application uses asyncpg at runtime.
    This function rewrites the driver when ``DATABASE_URL`` is set in the
    environment so that developers don't need two separate connection
    strings.
    """
    return re.sub(
        r"^postgresql\+asyncpg://",
        "postgresql+psycopg2://",
        url,
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine, though an
    Engine is acceptable here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to ``context.execute()`` emit the given SQL string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        url = _rewrite_async_url(env_url)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an Engine from the config and associates a connection with
    the context. If ``DATABASE_URL`` is set in the environment it takes
    precedence over the value in ``alembic.ini``, with automatic async
    → sync driver rewriting.
    """
    cfg = config.get_section(config.config_ini_section, {})

    env_url = os.getenv("DATABASE_URL")
    if env_url:
        cfg["sqlalchemy.url"] = _rewrite_async_url(env_url)

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()