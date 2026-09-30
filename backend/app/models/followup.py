import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.constraints import status_constraint
from app.models.enums import FollowupStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.outreach import OutreachMessage


class Followup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "followups"
    __table_args__ = (
        status_constraint("followups", "status", FollowupStatus),
        Index("ix_followups_lead_id", "lead_id"),
        Index("ix_followups_scheduled_for", "scheduled_for"),
        Index("ix_followups_status", "status"),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    outreach_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("outreach_messages.id", ondelete="SET NULL"),
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    type: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=FollowupStatus.SCHEDULED.value,
        server_default=text("'SCHEDULED'"),
    )
    notes: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lead: Mapped["Lead"] = relationship(back_populates="followups")
    outreach: Mapped["OutreachMessage | None"] = relationship(back_populates="followups")
