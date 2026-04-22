"""Alembic async migration environment.

Scaffolded via ``alembic init -t async alembic``, then edited to:
1. Import the project ``Base.metadata`` from ``flyer_generator.api.models``.
2. Pull the DB URL from ``AppSettings`` at runtime (env var override works).
3. Use ``pool.NullPool`` — migrations are one-off connections.
4. Respect SQLite batch mode for ALTER via ``render_as_batch=True`` (Pitfall 11).
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from flyer_generator.api.config import AppSettings
from flyer_generator.api.models import Base

# Alembic Config object, providing access to values within alembic.ini
config = context.config

# Interpret logging config if present
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Runtime DB URL override — always wins over alembic.ini.
settings = AppSettings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL without a live connection."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite-safe ALTER
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite-safe ALTER (Pitfall 11)
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode with an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
