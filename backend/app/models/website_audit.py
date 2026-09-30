import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.constraints import http_url_constraint, status_constraint
from app.models.enums import AuditStatus
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.mockup import Mockup


class WebsiteAudit(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "website_audits"
    __table_args__ = (
        status_constraint("website_audits", "status", AuditStatus),
        http_url_constraint("website_audits", "url"),
        Index("ix_website_audits_lead_id", "lead_id"),
        Index("ix_website_audits_status", "status"),
        Index("ix_website_audits_created_at", "created_at"),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AuditStatus.PENDING.value,
        server_default=text("'PENDING'"),
    )
    desktop_screenshot_url: Mapped[str | None] = mapped_column(Text)
    mobile_screenshot_url: Mapped[str | None] = mapped_column(Text)
    performance_score: Mapped[int | None] = mapped_column(Integer)
    design_score: Mapped[int | None] = mapped_column(Integer)
    mobile_score: Mapped[int | None] = mapped_column(Integer)
    ux_score: Mapped[int | None] = mapped_column(Integer)
    seo_score: Mapped[int | None] = mapped_column(Integer)
    overall_score: Mapped[int | None] = mapped_column(Integer)
    has_ssl: Mapped[bool | None] = mapped_column(Boolean)
    is_mobile_responsive: Mapped[bool | None] = mapped_column(Boolean)
    has_clear_cta: Mapped[bool | None] = mapped_column(Boolean)
    has_contact_form: Mapped[bool | None] = mapped_column(Boolean)
    has_social_proof: Mapped[bool | None] = mapped_column(Boolean)
    has_modern_navigation: Mapped[bool | None] = mapped_column(Boolean)
    issues: Mapped[list[object] | None] = mapped_column(JSONB)
    recommendations: Mapped[list[object] | None] = mapped_column(JSONB)
    raw_analysis: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lead: Mapped["Lead"] = relationship(back_populates="website_audits")
    mockups: Mapped[list["Mockup"]] = relationship(back_populates="audit")
