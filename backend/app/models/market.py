from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class MarketCell(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One category in one city. Remembers what searching it produced so it can rotate."""

    __tablename__ = "market_cells"
    __table_args__ = (
        Index("uq_market_cells_key", "category", "country", "city", unique=True),
        Index("ix_market_cells_next_eligible", "next_eligible_at"),
    )

    category: Mapped[str] = mapped_column(String(80), nullable=False)
    country: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    searches: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    found: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    empty_streak: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    last_searched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_eligible_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class DiscoveryRejection(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A business we looked at and chose not to keep, so we never evaluate it twice."""

    __tablename__ = "discovery_rejections"
    __table_args__ = (
        Index("uq_discovery_rejections_source_key", "source_key", unique=True),
        Index("ix_discovery_rejections_created_at", "created_at"),
    )

    source_key: Mapped[str] = mapped_column(String(300), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(120))
    source: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[int | None] = mapped_column(Integer)
