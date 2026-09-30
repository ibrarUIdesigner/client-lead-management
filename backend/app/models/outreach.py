import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.constraints import status_constraint
from app.models.enums import OutreachStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.followup import Followup
    from app.models.lead import Lead


class OutreachTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outreach_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(32))
    subject: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    template_type: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    messages: Mapped[list["OutreachMessage"]] = relationship(back_populates="template")


class OutreachMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outreach_messages"
    __table_args__ = (
        status_constraint("outreach_messages", "status", OutreachStatus),
        Index("ix_outreach_messages_lead_id", "lead_id"),
        Index("ix_outreach_messages_status", "status"),
        Index("ix_outreach_messages_created_at", "created_at"),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
    )
    channel: Mapped[str | None] = mapped_column(String(32))
    subject: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("outreach_templates.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OutreachStatus.DRAFT.value,
        server_default=text("'DRAFT'"),
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lead: Mapped["Lead"] = relationship(back_populates="outreach_messages")
    contact: Mapped["Contact | None"] = relationship(back_populates="outreach_messages")
    template: Mapped[OutreachTemplate | None] = relationship(back_populates="messages")
    followups: Mapped[list["Followup"]] = relationship(back_populates="outreach")
