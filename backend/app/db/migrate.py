"""Bring the database schema up to date when the app starts.

The deployed app and its database can drift apart: new code reads columns that an
unapplied migration would add, and every request that touches them fails with a 500.
On Vercel there is no release step that runs migrations, so the app does it itself the
first time an instance starts. It is safe to run repeatedly and safe to run from several
instances at once.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
# Arbitrary constant. Instances that start together queue on this lock, and the ones
# that wait find nothing left to do.
LOCK_KEY = 727_274_001

SchemaState = Literal["current", "behind", "unknown"]


def _config(engine: Engine | None = None) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    if engine is not None:
        config.attributes["database_url"] = engine.url.render_as_string(hide_password=False)
    return config


def head_revision() -> str | None:
    return ScriptDirectory.from_config(_config()).get_current_head()


def schema_state(engine: Engine) -> SchemaState:
    """Whether the database has every migration this version of the app expects."""
    try:
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
        return "current" if current == head_revision() else "behind"
    except Exception:
        logger.warning("schema_state_check_failed")
        return "unknown"


def upgrade_to_head(engine: Engine) -> bool:
    """Apply pending migrations. Returns True when the schema is current afterwards.

    Never raises: a failure is logged and the app still starts, so the health route can
    report ``schema: behind`` instead of the whole service going down.
    """
    try:
        if schema_state(engine) == "current":
            return True
        with engine.connect() as lock_connection:
            with lock_connection.begin():
                # A transaction-scoped lock works through Neon's transaction pooler,
                # where session-scoped advisory locks are not reliable.
                lock_connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK_KEY})
                if schema_state(engine) == "current":  # another instance finished first
                    return True
                logger.info("migrations_applying")
                command.upgrade(_config(engine), "head")
        logger.info("migrations_applied")
        return schema_state(engine) == "current"
    except Exception:
        logger.exception("migrations_failed")
        return False
