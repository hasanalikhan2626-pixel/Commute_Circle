from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    student = "student"
    admin = "admin"


class Gender(str, enum.Enum):
    female = "female"
    male = "male"
    undisclosed = "undisclosed"


class CircleStatus(str, enum.Enum):
    proposed = "proposed"  # waiting for every member to accept
    active = "active"
    dissolved = "dissolved"


class MemberStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    left = "left"


class ReportStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"
    dismissed = "dismissed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.student)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    profile: Mapped[Profile | None] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    memberships: Mapped[list[CircleMember]] = relationship(back_populates="user")


class Profile(Base):
    """Commute preferences. Only the student edits this; matching never writes to it."""

    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    area: Mapped[str] = mapped_column(String(60))
    pickup_landmark: Mapped[str | None] = mapped_column(String(120))  # shown to circle members only
    gender: Mapped[Gender] = mapped_column(Enum(Gender), default=Gender.undisclosed)
    same_gender_only: Mapped[bool] = mapped_column(Boolean, default=False)
    has_car: Mapped[bool] = mapped_column(Boolean, default=False)
    seats: Mapped[int] = mapped_column(Integer, default=0)  # passenger seats offered
    # {"mon": {"arrive": "08:30", "leave": "14:00"}, ...}; absent day = not on campus
    schedule: Mapped[dict] = mapped_column(JSON, default=dict)
    seeking: Mapped[bool] = mapped_column(Boolean, default=True)  # opted into matching
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="profile")


class Circle(Base):
    __tablename__ = "circles"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[CircleStatus] = mapped_column(Enum(CircleStatus), default=CircleStatus.proposed)
    algorithm: Mapped[str] = mapped_column(String(40))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    dissolved_reason: Mapped[str | None] = mapped_column(String(200))

    members: Mapped[list[CircleMember]] = relationship(back_populates="circle", cascade="all, delete-orphan")
    rota: Mapped[list[RotaEntry]] = relationship(back_populates="circle", cascade="all, delete-orphan",
                                                 order_by="RotaEntry.day")


class CircleMember(Base):
    __tablename__ = "circle_members"
    __table_args__ = (UniqueConstraint("circle_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    circle_id: Mapped[int] = mapped_column(ForeignKey("circles.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    is_driver: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[MemberStatus] = mapped_column(Enum(MemberStatus), default=MemberStatus.pending)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    circle: Mapped[Circle] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class RotaEntry(Base):
    __tablename__ = "rota_entries"
    __table_args__ = (UniqueConstraint("circle_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    circle_id: Mapped[int] = mapped_column(ForeignKey("circles.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    arrive: Mapped[str] = mapped_column(String(5))  # agreed arrival time for the group

    circle: Mapped[Circle] = relationship(back_populates="rota")


class DeclinedPair(Base):
    """Remembers that a student declined a circle containing another student, so
    the next matching run does not propose the same pairing again."""

    __tablename__ = "declined_pairs"
    __table_args__ = (UniqueConstraint("user_id", "other_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    other_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reported_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    circle_id: Mapped[int | None] = mapped_column(ForeignKey("circles.id", ondelete="SET NULL"))
    reason: Mapped[str] = mapped_column(String(60))
    details: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.open)
    admin_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MatchRun(Base):
    """Audit log of every matching run, used for the algorithm evaluation."""

    __tablename__ = "match_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    algorithm: Mapped[str] = mapped_column(String(40))
    triggered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    pool_size: Mapped[int] = mapped_column(Integer)
    circles_created: Mapped[int] = mapped_column(Integer)
    students_matched: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DriverUnavailability(Base):
    """A driver can't drive on a given day; the rota assigns someone else."""

    __tablename__ = "driver_unavailability"
    __table_args__ = (UniqueConstraint("circle_id", "user_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    circle_id: Mapped[int] = mapped_column(ForeignKey("circles.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)
