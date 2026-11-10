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


class UserStatus(str, enum.Enum):
    pending = "pending"      # signed up, waiting for Student Affairs approval
    approved = "approved"
    rejected = "rejected"
    suspended = "suspended"


class Gender(str, enum.Enum):
    female = "female"
    male = "male"


class CircleStatus(str, enum.Enum):
    proposed = "proposed"  # waiting for every member to accept
    active = "active"
    dissolved = "dissolved"


class MemberStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    left = "left"


class TripStatus(str, enum.Enum):
    planned = "planned"
    went = "went"
    notgoing = "notgoing"
    noshow = "noshow"


class ReportStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"
    suspended = "suspended"  # resolved by suspending the member


class SeatStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.student)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_version: Mapped[str | None] = mapped_column(String(20))
    research_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    emergency_name: Mapped[str | None] = mapped_column(String(120))
    emergency_phone: Mapped[str | None] = mapped_column(String(20))

    profile: Mapped[Profile | None] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan",
                                                    lazy="joined")
    memberships: Mapped[list[CircleMember]] = relationship(back_populates="user", cascade="all, delete-orphan",
                                                           passive_deletes=True)

    @property
    def can_sign_in(self) -> bool:
        return self.status in (UserStatus.pending, UserStatus.approved)


class Profile(Base):
    """Trip details. Only the student edits this; matching never writes to it."""

    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    programme: Mapped[str] = mapped_column(String(120), default="")
    year: Mapped[int] = mapped_column(Integer, default=1)
    gender: Mapped[Gender] = mapped_column(Enum(Gender))
    area: Mapped[str] = mapped_column(String(60), default="")  # set by the trip questions
    women_only: Mapped[bool] = mapped_column(Boolean, default=False)
    methods: Mapped[list] = mapped_column(JSON, default=list)  # ways the student is happy to travel
    has_car: Mapped[bool] = mapped_column(Boolean, default=False)  # needed for "Classmate drives"
    seats: Mapped[int] = mapped_column(Integer, default=0)
    has_bike: Mapped[bool] = mapped_column(Boolean, default=False)  # needed for "Motorbike pillion"
    # {"Mon": {"in": "08:30", "out": "14:00"}, ...}; a missing day = not on campus
    schedule: Mapped[dict] = mapped_column(JSON, default=dict)
    seeking: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="profile")


class Circle(Base):
    __tablename__ = "circles"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[CircleStatus] = mapped_column(Enum(CircleStatus), default=CircleStatus.proposed)
    mode: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(40), default="student")  # "student" or an algorithm name
    fit: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    since: Mapped[date | None] = mapped_column(Date)  # day it became active
    settled_until: Mapped[date | None] = mapped_column(Date)
    dissolved_reason: Mapped[str | None] = mapped_column(String(200))

    members: Mapped[list[CircleMember]] = relationship(back_populates="circle", cascade="all, delete-orphan",
                                                       order_by="CircleMember.position", lazy="selectin")
    rota: Mapped[list[RotaEntry]] = relationship(back_populates="circle", cascade="all, delete-orphan",
                                                 order_by="RotaEntry.day")


class CircleMember(Base):
    __tablename__ = "circle_members"
    __table_args__ = (UniqueConstraint("circle_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    circle_id: Mapped[int] = mapped_column(ForeignKey("circles.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)  # 0 = the student who found the circle
    status: Mapped[MemberStatus] = mapped_column(Enum(MemberStatus), default=MemberStatus.pending)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    circle: Mapped[Circle] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships", lazy="joined")


class RotaEntry(Base):
    """Who drives / drops on a day, for the driving modes."""

    __tablename__ = "rota_entries"
    __table_args__ = (UniqueConstraint("circle_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    circle_id: Mapped[int] = mapped_column(ForeignKey("circles.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    manual: Mapped[bool] = mapped_column(Boolean, default=False)  # someone took or swapped this day

    circle: Mapped[Circle] = relationship(back_populates="rota")


class RotaUnavailable(Base):
    __tablename__ = "rota_unavailable"
    __table_args__ = (UniqueConstraint("circle_id", "user_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    circle_id: Mapped[int] = mapped_column(ForeignKey("circles.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)


class Trip(Base):
    """One circle's trip to campus on one day."""

    __tablename__ = "trips"
    __table_args__ = (UniqueConstraint("circle_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    circle_id: Mapped[int] = mapped_column(ForeignKey("circles.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    mode: Mapped[str] = mapped_column(String(40))
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    total: Mapped[int | None] = mapped_column(Integer)  # fare for everyone who went, in Rs
    fare_skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    payer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    members: Mapped[list[TripMember]] = relationship(back_populates="trip", cascade="all, delete-orphan",
                                                     lazy="selectin")


class TripMember(Base):
    __tablename__ = "trip_members"
    __table_args__ = (UniqueConstraint("trip_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[TripStatus] = mapped_column(Enum(TripStatus), default=TripStatus.planned)
    guest: Mapped[bool] = mapped_column(Boolean, default=False)  # one-day seat from another circle

    trip: Mapped[Trip] = relationship(back_populates="members")


class Absence(Base):
    """'Not going tomorrow': overrides the weekly plan for one day."""

    __tablename__ = "absences"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[int] = mapped_column(primary_key=True)
    circle_id: Mapped[int] = mapped_column(ForeignKey("circles.id", ondelete="CASCADE"), index=True)
    from_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Feedback(Base):
    """Private feedback. Positive tags add up to badges; negatives are seen only by Student Affairs."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    to_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    circle_id: Mapped[int | None] = mapped_column(ForeignKey("circles.id", ondelete="SET NULL"))
    up: Mapped[bool] = mapped_column(Boolean)
    tag: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SeatRequest(Base):
    """A one-day seat in another circle."""

    __tablename__ = "seat_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    circle_id: Mapped[int] = mapped_column(ForeignKey("circles.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)
    status: Mapped[SeatStatus] = mapped_column(Enum(SeatStatus), default=SeatStatus.pending)
    answered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeclinedPair(Base):
    """A student declined a circle with another student: never propose them together again."""

    __tablename__ = "declined_pairs"
    __table_args__ = (UniqueConstraint("user_id", "other_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    other_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    # SET NULL: safety records outlive a deleted account without identifying it.
    reporter_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reported_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    circle_id: Mapped[int | None] = mapped_column(ForeignKey("circles.id", ondelete="SET NULL"))
    reason: Mapped[str] = mapped_column(String(60))
    details: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.open)
    admin_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MatchRun(Base):
    """Audit log of admin matching runs (research component)."""

    __tablename__ = "match_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    algorithm: Mapped[str] = mapped_column(String(40))
    triggered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    pool_size: Mapped[int] = mapped_column(Integer)
    circles_created: Mapped[int] = mapped_column(Integer)
    students_matched: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SosAlert(Base):
    """SOS pressed by a student (proposal Appendix D)."""

    __tablename__ = "sos_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    circle_id: Mapped[int | None] = mapped_column(ForeignKey("circles.id", ondelete="SET NULL"))
    message: Mapped[str] = mapped_column(Text, default="")
    route: Mapped[str] = mapped_column(String(300), default="")  # circle's pickup areas -> campus
    handled: Mapped[bool] = mapped_column(Boolean, default=False)
    handled_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TripRating(Base):
    """1-5 stars one member gives another after a confirmed trip (feeds the trust score)."""

    __tablename__ = "trip_ratings"
    __table_args__ = (UniqueConstraint("trip_id", "rater_id", "ratee_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))
    rater_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    ratee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    stars: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    """Outbox of every WhatsApp message and email (status "mock" when the service isn't configured)."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String(20))  # whatsapp | email
    to: Mapped[str] = mapped_column(String(254))
    template: Mapped[str] = mapped_column(String(60))
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="queued")  # sent | mock | failed
    error: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    dedupe: Mapped[str | None] = mapped_column(String(120), unique=True)  # stops repeat reminders
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SurveyResponse(Base):
    """Evaluation surveys (proposal 14.8): SUS usability, safety perception, monthly spending."""

    __tablename__ = "survey_responses"
    __table_args__ = (UniqueConstraint("user_id", "kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # sus | safety | spend_before | spend_after
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EmailCode(Base):
    """One-time 6-digit codes for email verification and password reset (stored hashed)."""

    __tablename__ = "email_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(10))  # verify | reset
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
