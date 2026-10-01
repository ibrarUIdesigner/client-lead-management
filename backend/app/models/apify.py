import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.constraints import status_constraint
from app.models.enums import ApifyRunStatus
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ApifyConnector(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "apify_connectors"
    __table_args__ = (Index("uq_apify_connectors_actor_id", "actor_id", unique=True),)

    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    input_schema: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    pricing: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    runs: Mapped[list["ApifyRun"]] = relationship(
        back_populates="connector",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ApifyRun(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "apify_runs"
    __table_args__ = (
        status_constraint("apify_runs", "status", ApifyRunStatus),
        Index("ix_apify_runs_connector_id_started_at", "connector_id", "started_at"),
        Index("ix_apify_runs_status", "status"),
        Index("uq_apify_runs_apify_run_id", "apify_run_id", unique=True),
        Index("uq_apify_runs_connector_request", "connector_id", "client_request_id", unique=True),
    )

    connector_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("apify_connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    apify_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    client_request_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    status_message: Mapped[str | None] = mapped_column(Text)
    run_input: Mapped[dict[str, object]] = mapped_column(
        "input",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    max_items: Mapped[int | None] = mapped_column(Integer)
    max_total_charge_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_count: Mapped[int | None] = mapped_column(Integer)
    usage_total_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    default_dataset_id: Mapped[str | None] = mapped_column(String(128))

    connector: Mapped[ApifyConnector] = relationship(back_populates="runs")
    items: Mapped[list["ApifyDatasetItem"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ApifyDatasetItem(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "apify_dataset_items"
    __table_args__ = (
        Index("uq_apify_dataset_items_run_item", "run_id", "item_key", unique=True),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("apify_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_key: Mapped[str] = mapped_column(String(300), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    run: Mapped[ApifyRun] = relationship(back_populates="items")


class ApifyDismissedActor(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Actors removed in this app stay hidden when the account list is refreshed."""

    __tablename__ = "apify_dismissed_actors"
    __table_args__ = (Index("uq_apify_dismissed_actors_actor_id", "actor_id", unique=True),)

    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)


class ApifyImport(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "apify_imports"
    __table_args__ = (
        Index("uq_apify_imports_source_key", "source_key", unique=True),
        Index("uq_apify_imports_lead_id", "lead_id", unique=True),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("apify_runs.id", ondelete="SET NULL"),
    )
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    apify_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_key: Mapped[str] = mapped_column(String(300), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
