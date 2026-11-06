"""Campus dates. "Today" is the date in Karachi, not the server's time zone."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..matching.compat import DAYS

PKT = ZoneInfo("Asia/Karachi")
_override: date | None = None  # tests can pin the date


def today() -> date:
    """Today in Karachi. Outside production, CC_TODAY=YYYY-MM-DD pins the date (demos, tests)."""
    if _override:
        return _override
    import os

    from ..config import settings

    pinned = os.environ.get("CC_TODAY")
    if pinned and not settings.production:
        return date.fromisoformat(pinned)
    return datetime.now(PKT).date()


def set_today(d: date | None) -> None:
    global _override
    _override = d


def now() -> datetime:
    """Current time in Karachi. Outside production, CC_NOW=YYYY-MM-DDTHH:MM pins it (tests, demos)."""
    import os

    from ..config import settings

    pinned = os.environ.get("CC_NOW")
    if pinned and not settings.production:
        return datetime.fromisoformat(pinned).replace(tzinfo=PKT)
    if _override:
        return datetime.combine(_override, datetime.now(PKT).time(), PKT)
    return datetime.now(PKT)


def day_name(d: date) -> str | None:
    return DAYS[d.weekday()] if d.weekday() < 5 else None


def next_weekday(d: date) -> date:
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def past_weekdays(n: int, until: date | None = None) -> list[date]:
    """The ``n`` weekdays before ``until`` (default today), oldest first."""
    d, out = until or today(), []
    while len(out) < n:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            out.append(d)
    return out[::-1]
