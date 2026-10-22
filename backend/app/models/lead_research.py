import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import ResearchStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lead import Lead


class LeadResearch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_researches"
    __table_args__ = (
        Index("ix_lead_researches_lead_id", "lead_id"),
        Index("ix_lead_researches_status", "status"),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ResearchStatus.PENDING.value,
        server_default=text("'PENDING'"),
    )
    query_used: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    research_data: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    sources: Mapped[list[object] | None] = mapped_column(JSONB)
    raw_tavily: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    raw_exa: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lead: Mapped["Lead"] = relationship(back_populates="research")
