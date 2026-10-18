from datetime import datetime

from core.database import Base
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Media_outlets(Base):
    __tablename__ = "media_outlets"

    id: Mapped[int] = mapped_column(primary_key=True)
    maven_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    slogan: Mapped[str] = mapped_column(Text)
    website: Mapped[str] = mapped_column(String(512))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str] = mapped_column(String(32))
    linkedin_url: Mapped[str] = mapped_column(String(512))

    media_type: Mapped[str] = mapped_column(String(120))
    subtype: Mapped[str] = mapped_column(String(120))
    categories: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(120))
    geo_appeals: Mapped[str] = mapped_column(Text)
    start_date: Mapped[str] = mapped_column(String(32))

    direct_owner: Mapped[str] = mapped_column(String(255))
    parents: Mapped[str] = mapped_column(Text)

    diverse_target: Mapped[str] = mapped_column(Text)
    diverse_any: Mapped[str] = mapped_column(Text)
    classified: Mapped[str] = mapped_column(String(120))
    certified: Mapped[str] = mapped_column(String(120))

    personnel: Mapped[list[Personnel]] = relationship(
        back_populates="media_outlet",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Personnel(Base):
    __tablename__ = "personnel"
    __table_args__ = (
        # Named explicitly so the repo can map an IntegrityError back to a
        # duplicate email instead of guessing from the message.
        UniqueConstraint("email", name="uq_personnel_email"),
        Index("ix_personnel_media_outlet_id", "media_outlet_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    media_outlet_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_outlets.id", ondelete="CASCADE"),
        nullable=True,
    )

    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(320), index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    media_outlet: Mapped[Media_outlets | None] = relationship(back_populates="personnel")


class Students(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    age: Mapped[int]
    email: Mapped[str] = mapped_column(String(320), unique=True)