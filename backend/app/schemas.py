"""Request bodies (validated). Responses are plain dicts built in the routers."""
from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from .areas import AREAS
from .config import settings
from .matching.compat import DAYS, METHODS, minutes
from .models import Gender, ReportStatus

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
REPORT_REASONS = ("Repeatedly no-show", "Inappropriate behaviour", "Made me feel unsafe", "Other")
PROGRAMMES = (
    "BSc Artificial Intelligence (Essex)", "BBA (Essex)", "BSc Accounting & Finance (Essex)", "LLB (Essex)",
    "HND Business (Pearson)", "HND Art & Design (Pearson)", "Other",
)


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


def _time(v: str) -> str:
    if not _TIME.match(v):
        raise ValueError("Times must be HH:MM (24-hour)")
    return v


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    phone: str
    gender: Gender
    programme: str = Field(min_length=2, max_length=120)
    year: int = Field(ge=1, le=5)
    consent: bool = Field(default=False, validate_default=True)
    research_consent: bool = False

    @field_validator("consent")
    @classmethod
    def must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must accept the Terms, Privacy Notice and Code of Conduct")
        return v

    @field_validator("email")
    @classmethod
    def campus_domain(cls, v: str) -> str:
        v = v.lower()
        if settings.email_domains and v.rsplit("@", 1)[1] not in settings.email_domains:
            raise ValueError("Use your BIC student email address (@bic.edu.pk)")
        return v

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, v: str) -> str:
        return normalise_phone(v)

    @field_validator("full_name")
    @classmethod
    def strip(cls, v: str) -> str:
        if len(v.strip().split()) < 2:
            raise ValueError("Enter your first and last name")
        return v.strip()


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = None
    research_consent: bool | None = None
    whatsapp_opt_in: bool | None = None
    emergency_name: str | None = Field(default=None, max_length=120)
    emergency_phone: str | None = None

    @field_validator("phone", "emergency_phone")
    @classmethod
    def phone_ok(cls, v: str | None) -> str | None:
        return normalise_phone(v) if v else None


class DeleteAccountIn(BaseModel):
    password: str


class TripIn(BaseModel):
    """The three questions in "Find my circle"."""

    area: str
    days: list[str] = Field(min_length=1)
    arrive: str
    leave: str
    women_only: bool = False
    methods: list[str] = Field(min_length=1)
    has_car: bool = False
    seats: int = Field(default=0, ge=0, le=6)
    has_bike: bool = False
    # Optional per-day exceptions, e.g. {"Tue": {"in": "10:00", "out": "16:00"}}
    exceptions: dict[str, dict[str, str]] = {}

    @field_validator("area")
    @classmethod
    def known_area(cls, v: str) -> str:
        if v not in AREAS:
            raise ValueError("Choose your area from the list")
        return v

    @field_validator("days")
    @classmethod
    def weekdays(cls, v: list[str]) -> list[str]:
        if set(v) - set(DAYS):
            raise ValueError("Days must be Mon to Fri")
        return [d for d in DAYS if d in v]

    @field_validator("methods")
    @classmethod
    def methods_ok(cls, v: list[str]) -> list[str]:
        if set(v) - set(METHODS):
            raise ValueError("Unknown way of travelling")
        return [m for m in METHODS if m in v]

    @model_validator(mode="after")
    def check(self):
        _time(self.arrive), _time(self.leave)
        if minutes(self.leave) <= minutes(self.arrive):
            raise ValueError("Leaving time must be after arrival time")
        for d, t in self.exceptions.items():
            if d not in self.days:
                raise ValueError(f"{d} is not one of your campus days")
            _time(t.get("in", "")), _time(t.get("out", ""))
            if minutes(t["out"]) <= minutes(t["in"]):
                raise ValueError(f"{d}: leaving time must be after arrival time")
        if "Classmate drives" in self.methods and self.has_car and self.seats < 1:
            raise ValueError("Offer at least one seat if you drive")
        if not self.has_car:
            self.seats = 0
        if "Motorbike pillion" not in self.methods:
            self.has_bike = False
        return self

    def schedule(self) -> dict:
        return {d: dict(self.exceptions.get(d) or {"in": self.arrive, "out": self.leave}) for d in self.days}


class AcceptIn(BaseModel):
    member_ids: list[int] = Field(min_length=2, max_length=4)


class RespondIn(BaseModel):
    accept: bool


class ModeIn(BaseModel):
    mode: str

    @field_validator("mode")
    @classmethod
    def ok(cls, v: str) -> str:
        if v not in METHODS:
            raise ValueError("Unknown way of travelling")
        return v


class DayIn(BaseModel):
    day: date


class FareIn(BaseModel):
    share: int | None = Field(default=None, ge=1, le=20000)  # your share; total = share x travellers
    payer_id: int | None = None
    skip: bool = False

    @model_validator(mode="after")
    def check(self):
        if not self.skip and self.share is None:
            raise ValueError("Enter an amount in Rs, or skip")
        return self


class GoingIn(BaseModel):
    going: bool


class FeedbackIn(BaseModel):
    to_id: int
    up: bool
    tag: str = Field(min_length=2, max_length=40)


class ReportIn(BaseModel):
    reported_id: int
    reason: str
    details: str = Field(default="", max_length=2000)
    leave: bool = True

    @field_validator("reason")
    @classmethod
    def reason_ok(cls, v: str) -> str:
        if v not in REPORT_REASONS:
            raise ValueError("Choose a reason from the list")
        return v


class SeatIn(BaseModel):
    circle_id: int


class SettleIn(BaseModel):
    from_id: int
    to_id: int
    amount: int = Field(ge=1)


class MatchIn(BaseModel):
    algorithm: str = "compatibility"
    seed: int = 0


class DissolveIn(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


class ReportUpdate(BaseModel):
    status: ReportStatus
    admin_note: str | None = Field(default=None, max_length=2000)


class ApprovalIn(BaseModel):
    approve: bool


class SosIn(BaseModel):
    message: str = Field(default="", max_length=500)


class RatingItem(BaseModel):
    user_id: int
    stars: int = Field(ge=1, le=5)


class RateIn(BaseModel):
    ratings: list[RatingItem] = Field(min_length=1, max_length=4)


class SosUpdate(BaseModel):
    handled: bool = True
    note: str | None = Field(default=None, max_length=2000)


class SurveyIn(BaseModel):
    answers: list[int] = Field(default=[], max_length=10)
    amount_pkr: int | None = Field(default=None, ge=0, le=500_000)  # spending surveys
