import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lead import Lead


class BrandProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "brand_profiles"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    logo_url: Mapped[str | None] = mapped_column(Text)
    primary_color: Mapped[str | None] = mapped_column(String(32))
    secondary_color: Mapped[str | None] = mapped_column(String(32))
    accent_color: Mapped[str | None] = mapped_column(String(32))
    font_primary: Mapped[str | None] = mapped_column(String(120))
    font_secondary: Mapped[str | None] = mapped_column(String(120))
    brand_description: Mapped[str | None] = mapped_column(Text)
    extracted_images: Mapped[list[object] | None] = mapped_column(JSONB)
    extracted_content: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    lead: Mapped["Lead"] = relationship(back_populates="brand_profile")
