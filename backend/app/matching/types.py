from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Candidate:
    """Everything the matcher needs about a student, decoupled from the ORM so the
    algorithms are pure functions and can be tested and benchmarked in isolation."""

    user_id: int
    location: tuple[float, float]
    gender: str
    same_gender_only: bool
    has_car: bool
    seats: int
    schedule: dict[str, dict[str, str]]  # day -> {"arrive": "HH:MM", "leave": "HH:MM"}


@dataclass
class ProposedCircle:
    member_ids: list[int]
    driver_ids: list[int]
    score: float = 0.0


@dataclass
class MatchResult:
    algorithm: str
    circles: list[ProposedCircle] = field(default_factory=list)
    unmatched: list[int] = field(default_factory=list)
    runtime_ms: float = 0.0
