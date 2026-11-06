from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from .areas import AREAS
from .config import settings
from .matching.compat import DAYS, minutes
from .models import CircleStatus, Gender, MemberStatus, ReportStatus, Role

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
REPORT_REASONS = ("unsafe_driving", "harassment", "no_show", "payment", "other")


def normalise_phone(raw: str) -> str:
    """Return a Pakistani mobile number as +923XXXXXXXXX."""
    digits = re.sub(r"[\s\-()]", "", raw)
    if digits.startswith("+"):
        digits = digits[1:]
    if digits.startswith("0"):
        digits = "92" + digits[1:]
    if not re.fullmatch(r"923\d{9}", digits):
        raise ValueError("Enter a Pakistani mobile number, e.g. 0300 1234567")
    return "+" + digits


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    phone: str | None = None

    @field_validator("email")
    @classmethod
    def campus_domain(cls, v: str) -> str:
        v = v.lower()
        if settings.email_domains and v.rsplit("@", 1)[1] not in settings.email_domains:
            raise ValueError("Use your BIC student email address")
        return v

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, v: str | None) -> str | None:
        return normalise_phone(v) if v else None

    @field_validator("full_name")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = None

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, v: str | None) -> str | None:
        return normalise_phone(v) if v else None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str
    phone: str | None
    role: Role
    is_active: bool
    has_profile: bool = False


class DaySlot(BaseModel):
    arrive: str
    leave: str

    @model_validator(mode="after")
    def order(self):
        for t in (self.arrive, self.leave):
            if not _TIME.match(t):
                raise ValueError("Times must be HH:MM (24-hour)")
        if minutes(self.leave) <= minutes(self.arrive):
            raise ValueError("Leaving time must be after arrival time")
        return self


class ProfileIn(BaseModel):
    area: str
    pickup_landmark: str | None = Field(default=None, max_length=120)
    gender: Gender = Gender.undisclosed
    same_gender_only: bool = False
    has_car: bool = False
    seats: int = Field(default=0, ge=0, le=6)
    schedule: dict[str, DaySlot]
    seeking: bool = True

    @field_validator("area")
    @classmethod
    def known_area(cls, v: str) -> str:
        if v not in AREAS:
            raise ValueError("Choose an area from the list")
        return v

    @field_validator("schedule")
    @classmethod
    def days(cls, v: dict[str, DaySlot]) -> dict[str, DaySlot]:
        bad = set(v) - set(DAYS)
        if bad:
            raise ValueError(f"Unknown day(s): {', '.join(sorted(bad))}")
        if not v:
            raise ValueError("Add at least one day you come to campus")
        return v

    @model_validator(mode="after")
    def car_rules(self):
        if self.has_car and self.seats < 1:
            raise ValueError("Drivers must offer at least one seat")
        if not self.has_car:
            self.seats = 0
        if self.same_gender_only and self.gender == Gender.undisclosed:
            raise ValueError("Select your gender to use same-gender matching")
        return self


class ProfileOut(ProfileIn):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    updated_at: datetime
    warning: str | None = None


class MemberOut(BaseModel):
    user_id: int
    full_name: str
    area: str | None
    is_driver: bool
    status: MemberStatus
    # Contact details are only revealed once the circle is active.
    phone: str | None = None
    pickup_landmark: str | None = None


class RotaOut(BaseModel):
    day: date
    driver_id: int | None
    driver_name: str | None
    arrive: str


class CircleOut(BaseModel):
    id: int
    status: CircleStatus
    algorithm: str
    score: float
    created_at: datetime
    dissolved_reason: str | None
    shared_days: list[str]
    members: list[MemberOut]
    rota: list[RotaOut]
    costs: dict
    my_status: MemberStatus | None = None


class RespondIn(BaseModel):
    accept: bool


class UnavailableIn(BaseModel):
    day: date


class ReportIn(BaseModel):
    reported_id: int
    circle_id: int | None = None
    reason: str
    details: str = Field(default="", max_length=2000)

    @field_validator("reason")
    @classmethod
    def reason_ok(cls, v: str) -> str:
        if v not in REPORT_REASONS:
            raise ValueError(f"Reason must be one of: {', '.join(REPORT_REASONS)}")
        return v


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reporter_id: int
    reported_id: int
    circle_id: int | None
    reason: str
    details: str
    status: ReportStatus
    admin_note: str | None
    created_at: datetime
    reporter_name: str | None = None
    reported_name: str | None = None


class ReportUpdate(BaseModel):
    status: ReportStatus
    admin_note: str | None = Field(default=None, max_length=2000)


class MatchIn(BaseModel):
    algorithm: str = "compatibility"
    seed: int = 0


class MatchRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    algorithm: str
    pool_size: int
    circles_created: int
    students_matched: int
    metrics: dict
    created_at: datetime


class DissolveIn(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


class AdminUserUpdate(BaseModel):
    is_active: bool
