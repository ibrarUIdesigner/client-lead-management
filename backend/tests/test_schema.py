from sqlalchemy import CheckConstraint, UniqueConstraint

import app.models  # noqa: F401
from app.db.base import Base
from app.models.enums import (
    AuditStatus,
    DiscoveryRunStatus,
    DiscoveryTrigger,
    FollowupStatus,
    LeadStatus,
    MockupStatus,
    OutreachStatus,
)

EXPECTED_TABLES = {
    "leads",
    "contacts",
    "website_audits",
    "brand_profiles",
    "mockups",
    "outreach_templates",
    "outreach_messages",
    "followups",
    "activities",
    "discovery_searches",
    "discovery_runs",
}


def test_schema_contains_acquisition_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_child_rows_are_removed_with_their_lead() -> None:
    lead_children = {
        "contacts": "lead_id",
        "website_audits": "lead_id",
        "brand_profiles": "lead_id",
        "mockups": "lead_id",
        "outreach_messages": "lead_id",
        "followups": "lead_id",
        "activities": "lead_id",
    }

    for table_name, column_name in lead_children.items():
        foreign_keys = Base.metadata.tables[table_name].c[column_name].foreign_keys
        assert len(foreign_keys) == 1
        foreign_key = next(iter(foreign_keys))
        assert foreign_key.column.table.name == "leads"
        assert foreign_key.ondelete == "CASCADE"

    run_keys = Base.metadata.tables["discovery_runs"].c.search_id.foreign_keys
    assert len(run_keys) == 1
    run_key = next(iter(run_keys))
    assert run_key.column.table.name == "discovery_searches"
    assert run_key.ondelete == "CASCADE"


def test_optional_links_do_not_delete_the_parent_record() -> None:
    optional_links = {
        ("mockups", "audit_id"): "website_audits",
        ("outreach_messages", "contact_id"): "contacts",
        ("outreach_messages", "template_id"): "outreach_templates",
        ("followups", "outreach_id"): "outreach_messages",
    }

    for (table_name, column_name), target in optional_links.items():
        foreign_key = next(iter(Base.metadata.tables[table_name].c[column_name].foreign_keys))
        assert foreign_key.column.table.name == target
        assert foreign_key.ondelete == "SET NULL"


def test_status_constraints_list_every_enum_value() -> None:
    expected = {
        ("leads", "ck_leads_lead_status"): LeadStatus,
        ("website_audits", "ck_website_audits_status"): AuditStatus,
        ("mockups", "ck_mockups_status"): MockupStatus,
        ("outreach_messages", "ck_outreach_messages_status"): OutreachStatus,
        ("followups", "ck_followups_status"): FollowupStatus,
        ("discovery_runs", "ck_discovery_runs_status"): DiscoveryRunStatus,
        ("discovery_runs", "ck_discovery_runs_run_trigger"): DiscoveryTrigger,
    }

    for (table_name, constraint_name), enum_cls in expected.items():
        constraint = _check(table_name, constraint_name)
        sql = str(constraint.sqltext)
        for value in enum_cls:
            assert f"'{value.value}'" in sql


def test_required_indexes_and_unique_keys_exist() -> None:
    index_names = {index.name for table in Base.metadata.tables.values() for index in table.indexes}
    assert {
        "ix_leads_lead_status",
        "ix_leads_industry",
        "ix_leads_city",
        "ix_leads_created_at",
        "ix_leads_lead_score",
        "ix_leads_next_followup_at",
        "ix_leads_website_url",
        "ix_contacts_lead_id",
        "ix_website_audits_lead_id",
        "ix_website_audits_status",
        "ix_website_audits_created_at",
        "ix_mockups_lead_id",
        "ix_mockups_status",
        "ix_mockups_created_at",
        "ix_outreach_messages_lead_id",
        "ix_outreach_messages_status",
        "ix_outreach_messages_created_at",
        "ix_followups_lead_id",
        "ix_followups_scheduled_for",
        "ix_followups_status",
        "ix_activities_lead_id_created_at",
        "uq_leads_source_key",
        "ix_discovery_runs_search_id_started_at",
    } <= index_names

    mockup_uniques = {
        constraint.name
        for constraint in Base.metadata.tables["mockups"].constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert "uq_mockups_lead_id_version" in mockup_uniques

    brand_lead = Base.metadata.tables["brand_profiles"].c.lead_id
    assert brand_lead.unique is True


def test_activity_metadata_column_keeps_the_schema_name() -> None:
    column = Base.metadata.tables["activities"].c.details
    assert column.name == "metadata"


def test_primary_keys_are_uuid_and_timestamps_are_timezone_aware() -> None:
    for table in Base.metadata.tables.values():
        primary_key = table.c.id
        assert primary_key.primary_key
        type_name = primary_key.type.__class__.__name__.lower()
        assert "uuid" in type_name or str(primary_key.type).lower() == "uuid"
        created_at = table.c.created_at
        assert created_at.nullable is False
        assert getattr(created_at.type, "timezone", False) is True


def _check(table_name: str, constraint_name: str) -> CheckConstraint:
    for constraint in Base.metadata.tables[table_name].constraints:
        if isinstance(constraint, CheckConstraint) and constraint.name == constraint_name:
            return constraint
    raise AssertionError(f"{constraint_name} was not found on {table_name}")
