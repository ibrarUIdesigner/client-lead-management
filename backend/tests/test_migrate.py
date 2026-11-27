import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.db.migrate import head_revision, schema_state, upgrade_to_head


@pytest.fixture
def scratch_engine():
    """An empty throwaway database, so the whole migration chain runs from nothing."""
    base = make_url(get_settings().database_url)
    name = f"mig_{uuid.uuid4().hex[:10]}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
    except Exception:
        admin.dispose()
        pytest.skip("Needs a local Postgres where this user may create a database.")
    engine = create_engine(base.set(database=name))
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def test_an_empty_database_is_brought_all_the_way_to_head(scratch_engine) -> None:
    assert schema_state(scratch_engine) == "behind"
    assert upgrade_to_head(scratch_engine) is True
    assert schema_state(scratch_engine) == "current"
    with scratch_engine.connect() as connection:
        columns = {
            row[0]
            for row in connection.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = 'mockups'")
            )
        }
        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            )
        }
    assert "public_token" in columns
    assert {"pipeline_jobs", "outreach_attempts", "market_cells", "app_settings"} <= tables


def test_running_it_twice_changes_nothing(scratch_engine) -> None:
    assert upgrade_to_head(scratch_engine) is True
    assert upgrade_to_head(scratch_engine) is True
    assert schema_state(scratch_engine) == "current"


def _roll_back_to_before_this_work(engine) -> None:
    """Make a database look like production did before these migrations: older tables and
    columns only, with existing rows."""
    with engine.begin() as connection:
        for table in (
            "pipeline_jobs", "app_settings", "automation_runs", "outreach_attempts",
            "lead_exclusions", "market_cells", "discovery_rejections",
        ):
            connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        connection.execute(text("ALTER TABLE mockups DROP COLUMN IF EXISTS public_token"))
        connection.execute(text("ALTER TABLE outreach_messages DROP COLUMN IF EXISTS variant"))
        for column in ("pipeline_paused", "pipeline_checked_at", "deal_value"):
            connection.execute(text(f"ALTER TABLE leads DROP COLUMN IF EXISTS {column}"))
        connection.execute(text("UPDATE alembic_version SET version_num = 'g9d2e4f63b55'"))


def test_a_database_that_is_behind_is_caught_up_and_keeps_its_data(scratch_engine) -> None:
    from alembic import command

    from app.db.migrate import _config

    command.upgrade(_config(scratch_engine), "head")
    _roll_back_to_before_this_work(scratch_engine)
    with scratch_engine.begin() as connection:
        lead_id = connection.execute(
            text("INSERT INTO leads (business_name, lead_status) VALUES ('Old Lead', 'NEW') RETURNING id")
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO mockups (lead_id, version, status) VALUES (:lead, 1, 'READY')"
            ),
            {"lead": lead_id},
        )
    assert schema_state(scratch_engine) == "behind"

    assert upgrade_to_head(scratch_engine) is True

    assert schema_state(scratch_engine) == "current"
    with scratch_engine.connect() as connection:
        token = connection.execute(text("SELECT public_token FROM mockups")).scalar_one()
        name = connection.execute(text("SELECT business_name FROM leads")).scalar_one()
        step_check = connection.execute(
            text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'ck_pipeline_jobs_step'")
        ).scalar_one()
    assert token and len(token) >= 20  # existing mockups get a link token
    assert name == "Old Lead"
    assert "'send'" in step_check


def test_a_broken_database_does_not_crash_the_app() -> None:
    dead = create_engine("postgresql+psycopg://app:app@127.0.0.1:1/none", connect_args={"connect_timeout": 1})
    assert upgrade_to_head(dead) is False
    assert schema_state(dead) == "unknown"


def test_head_revision_matches_the_newest_migration() -> None:
    assert head_revision() == "n6e9f1a30c22"
