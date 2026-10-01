from sqlalchemy import Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DesignGuide(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A reusable Markdown design guide owned by this local workspace."""

    __tablename__ = "design_guides"
    __table_args__ = (Index("ix_design_guides_updated_at", "updated_at"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
