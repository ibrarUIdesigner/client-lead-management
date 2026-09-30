from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.constraints import email_constraint, http_url_constraint, status_constraint
from app.models.enums import LeadStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.activity import Activity
    from app.models.brand_profile import BrandProfile
    from app.models.contact import Contact
    from app.models.followup import Followup
    from app.models.gmail import LeadEmail
    from app.models.mockup import Mockup
    from app.models.outreach import OutreachMessage
    from app.models.website_audit import WebsiteAudit


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        status_constraint("leads", "lead_status", LeadStatus),
        email_constraint("leads", "email"),
        http_url_constraint("leads", "website_url"),
        http_url_constraint("leads", "linkedin_url"),
        http_url_constraint("leads", "instagram_url"),
        http_url_constraint("leads", "facebook_url"),
        http_url_constraint("leads", "google_maps_url"),
        Index("ix_leads_lead_status", "lead_status"),
        Index("ix_leads_industry", "industry"),
        Index("ix_leads_city", "city"),
        Index("ix_leads_created_at", "created_at"),
        Index("ix_leads_lead_score", "lead_score"),
        Index("ix_leads_next_followup_at", "next_followup_at"),
        Index("ix_leads_website_url", "website_url"),
        Index("uq_leads_source_key", "source_key", unique=True),
    )

    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    website_url: Mapped[str | None] = mapped_column(Text)
    website_status: Mapped[str | None] = mapped_column(String(32))
    website_quality_score: Mapped[int | None] = mapped_column(Integer)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    instagram_url: Mapped[str | None] = mapped_column(Text)
    facebook_url: Mapped[str | None] = mapped_column(Text)
    google_maps_url: Mapped[str | None] = mapped_column(Text)
    lead_score: Mapped[int | None] = mapped_column(Integer)
    lead_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=LeadStatus.NEW.value,
        server_default=text("'NEW'"),
    )
    source: Mapped[str | None] = mapped_column(String(120))
    source_key: Mapped[str | None] = mapped_column(String(300))
    tags: Mapped[list[str] | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_followup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_unread: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    do_not_contact: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    email_suppressed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    suppressed_email: Mapped[str | None] = mapped_column(String(320))

    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    website_audits: Mapped[list["WebsiteAudit"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    brand_profile: Mapped["BrandProfile | None"] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    mockups: Mapped[list["Mockup"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    outreach_messages: Mapped[list["OutreachMessage"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    followups: Mapped[list["Followup"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    emails: Mapped[list["LeadEmail"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
