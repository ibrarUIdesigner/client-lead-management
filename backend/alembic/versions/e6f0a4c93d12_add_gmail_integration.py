"""Add Gmail integration tables and lead email tracking fields.

Revision ID: e6f0a4c93d12
Revises: d5e9f3b82c01
Create Date: 2026-10-01

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e6f0a4c93d12"
down_revision: str | Sequence[str] | None = "d5e9f3b82c01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEAD_STATUSES = (
    "NEW",
    "QUALIFIED",
    "AUDIT_PENDING",
    "AUDIT_COMPLETE",
    "MOCKUP_PENDING",
    "MOCKUP_READY",
    "CONTACTED",
    "FOLLOW_UP",
    "REPLIED",
    "MEETING",
    "PROPOSAL",
    "WON",
    "LOST",
    "NOT_INTERESTED",
    "DO_NOT_CONTACT",
)


def upgrade() -> None:
    # The baseline migration creates the current models, including these tables.
    # Skip when they are already present so a fresh database can still migrate.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    lead_columns: set[str] = set()
    if "leads" in tables:
        lead_columns = {column["name"] for column in inspector.get_columns("leads")}
    if {
        "gmail_accounts",
        "gmail_oauth_states",
        "lead_emails",
    } <= tables and {
        "last_replied_at",
        "email_unread",
        "do_not_contact",
        "email_suppressed",
        "suppressed_email",
    } <= lead_columns:
        return

    op.create_table(
        "gmail_accounts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("encrypted_access_token", sa.Text(), nullable=True),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("history_id", sa.String(length=64), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sync_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'NEEDS_REAUTH', 'DISCONNECTED')",
            name="ck_gmail_accounts_status",
        ),
        sa.CheckConstraint(
            "email ~ '^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$'",
            name="ck_gmail_accounts_email_email",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_gmail_accounts_email_active"),
    )
    op.create_index("ix_gmail_accounts_status", "gmail_accounts", ["status"])

    op.create_table(
        "gmail_oauth_states",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("state", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state"),
    )
    op.create_index("ix_gmail_oauth_states_expires_at", "gmail_oauth_states", ["expires_at"])

    op.create_table(
        "lead_emails",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        sa.Column("gmail_account_id", sa.Uuid(), nullable=False),
        sa.Column("outreach_message_id", sa.Uuid(), nullable=True),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column(
            "classification",
            sa.String(length=32),
            server_default=sa.text("'OTHER'"),
            nullable=False,
        ),
        sa.Column("recipient_email", sa.String(length=320), nullable=True),
        sa.Column("sender_email", sa.String(length=320), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("gmail_message_id", sa.String(length=128), nullable=False),
        sa.Column("gmail_thread_id", sa.String(length=128), nullable=False),
        sa.Column("rfc_message_id", sa.String(length=512), nullable=True),
        sa.Column("in_reply_to", sa.Text(), nullable=True),
        sa.Column("references_header", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_unread", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("needs_review", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "direction IN ('OUTBOUND', 'INBOUND')",
            name="ck_lead_emails_direction",
        ),
        sa.CheckConstraint(
            "classification IN ('OUTGOING', 'HUMAN_REPLY', 'OUT_OF_OFFICE', 'BOUNCE', "
            "'OPT_OUT', 'AMBIGUOUS', 'OTHER')",
            name="ck_lead_emails_classification",
        ),
        sa.CheckConstraint(
            "recipient_email IS NULL OR recipient_email ~ "
            "'^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$'",
            name="ck_lead_emails_recipient_email_email",
        ),
        sa.CheckConstraint(
            "sender_email IS NULL OR sender_email ~ "
            "'^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$'",
            name="ck_lead_emails_sender_email_email",
        ),
        sa.ForeignKeyConstraint(["gmail_account_id"], ["gmail_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["outreach_message_id"], ["outreach_messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "gmail_account_id",
            "gmail_message_id",
            name="uq_lead_emails_account_gmail_message",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_lead_emails_idempotency_key"),
    )
    op.create_index("ix_lead_emails_lead_id", "lead_emails", ["lead_id"])
    op.create_index("ix_lead_emails_gmail_thread_id", "lead_emails", ["gmail_thread_id"])
    op.create_index("ix_lead_emails_rfc_message_id", "lead_emails", ["rfc_message_id"])
    op.create_index("ix_lead_emails_occurred_at", "lead_emails", ["occurred_at"])
    op.create_index("ix_lead_emails_needs_review", "lead_emails", ["needs_review"])

    op.add_column("leads", sa.Column("last_replied_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "leads",
        sa.Column("email_unread", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "leads",
        sa.Column("do_not_contact", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "leads",
        sa.Column(
            "email_suppressed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column("leads", sa.Column("suppressed_email", sa.String(length=320), nullable=True))

    op.drop_constraint("ck_leads_lead_status", "leads", type_="check")
    listed = ", ".join(f"'{value}'" for value in _LEAD_STATUSES)
    op.create_check_constraint("ck_leads_lead_status", "leads", f"lead_status IN ({listed})")


def downgrade() -> None:
    op.drop_constraint("ck_leads_lead_status", "leads", type_="check")
    old = (
        "NEW",
        "QUALIFIED",
        "AUDIT_PENDING",
        "AUDIT_COMPLETE",
        "MOCKUP_PENDING",
        "MOCKUP_READY",
        "CONTACTED",
        "FOLLOW_UP",
        "REPLIED",
        "MEETING",
        "PROPOSAL",
        "WON",
        "LOST",
        "NOT_INTERESTED",
    )
    listed = ", ".join(f"'{value}'" for value in old)
    op.create_check_constraint("ck_leads_lead_status", "leads", f"lead_status IN ({listed})")

    op.drop_column("leads", "suppressed_email")
    op.drop_column("leads", "email_suppressed")
    op.drop_column("leads", "do_not_contact")
    op.drop_column("leads", "email_unread")
    op.drop_column("leads", "last_replied_at")

    op.drop_index("ix_lead_emails_needs_review", table_name="lead_emails")
    op.drop_index("ix_lead_emails_occurred_at", table_name="lead_emails")
    op.drop_index("ix_lead_emails_rfc_message_id", table_name="lead_emails")
    op.drop_index("ix_lead_emails_gmail_thread_id", table_name="lead_emails")
    op.drop_index("ix_lead_emails_lead_id", table_name="lead_emails")
    op.drop_table("lead_emails")
    op.drop_index("ix_gmail_oauth_states_expires_at", table_name="gmail_oauth_states")
    op.drop_table("gmail_oauth_states")
    op.drop_index("ix_gmail_accounts_status", table_name="gmail_accounts")
    op.drop_table("gmail_accounts")
