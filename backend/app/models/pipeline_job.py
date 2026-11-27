import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.constraints import status_constraint
from app.models.enums import PipelineJobStatus, PipelineStep
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PipelineJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One automation step for one lead. Claimed by the tick worker."""

    __tablename__ = "pipeline_jobs"
    __table_args__ = (
        status_constraint("pipeline_jobs", "status", PipelineJobStatus),
        status_constraint("pipeline_jobs", "step", PipelineStep),
        Index("ix_pipeline_jobs_lead_id", "lead_id"),
        Index("ix_pipeline_jobs_status_run_after", "status", "run_after"),
        # At most one open job per lead and step.
        Index(
            "uq_pipeline_jobs_open",
            "lead_id",
            "step",
            unique=True,
            postgresql_where=text("status IN ('QUEUED', 'RUNNING')"),
        ),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    step: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=PipelineJobStatus.QUEUED.value,
        server_default=text("'QUEUED'"),
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default=text("3"))
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
