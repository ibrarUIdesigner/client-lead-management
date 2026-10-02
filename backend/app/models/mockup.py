import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.constraints import status_constraint
from app.models.enums import MockupStatus
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.design_guide import DesignGuide
    from app.models.lead import Lead
    from app.models.website_audit import WebsiteAudit


class Mockup(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "mockups"
    __table_args__ = (
        status_constraint("mockups", "status", MockupStatus),
        UniqueConstraint("lead_id", "version", name="uq_mockups_lead_id_version"),
        Index("ix_mockups_lead_id", "lead_id"),
        Index("ix_mockups_status", "status"),
        Index("ix_mockups_created_at", "created_at"),
        Index("ix_mockups_design_guide_id", "design_guide_id"),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    audit_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("website_audits.id", ondelete="SET NULL"),
    )
    title: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=MockupStatus.PENDING.value,
        server_default=text("'PENDING'"),
    )
    prompt: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(64))
    model_name: Mapped[str | None] = mapped_column(String(64))
    goal: Mapped[str | None] = mapped_column(String(32))
    html_content: Mapped[str | None] = mapped_column(Text)
    asset_refs: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    source_mockup_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("mockups.id", ondelete="SET NULL"),
    )
    screenshot_status: Mapped[str | None] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))
    image_url: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    desktop_image_url: Mapped[str | None] = mapped_column(Text)
    mobile_image_url: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    design_guide_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("design_guides.id", ondelete="SET NULL"),
    )
    design_guide_name: Mapped[str | None] = mapped_column(String(120))
    design_guide_snapshot: Mapped[str | None] = mapped_column(Text)

    lead: Mapped["Lead"] = relationship(back_populates="mockups")
    audit: Mapped["WebsiteAudit | None"] = relationship(back_populates="mockups")
    design_guide: Mapped["DesignGuide | None"] = relationship()
