"""Application settings, read from environment variables (prefix ``CC_``).

Every value has a development default so the app runs out of the box; set the
real values in production (see docs/DEPLOYMENT.md).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.environ.get(f"CC_{name}", default)


@dataclass(frozen=True)
class Settings:
    secret_key: str = field(default_factory=lambda: _env("SECRET_KEY", "dev-only-change-me"))
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", "sqlite:///./commutecircle.db"))
    token_minutes: int = field(default_factory=lambda: int(_env("TOKEN_MINUTES", "720")))
    # Comma-separated list of email domains allowed to register, e.g. "bic.edu.pk".
    # Empty means any domain (development only).
    email_domains: tuple[str, ...] = field(
        default_factory=lambda: tuple(d.strip().lower() for d in _env("EMAIL_DOMAINS", "").split(",") if d.strip())
    )
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(o.strip() for o in _env("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip())
    )
    # Campus location. Placeholder: verify the exact BIC Karachi coordinates.
    campus_name: str = field(default_factory=lambda: _env("CAMPUS_NAME", "BIC Karachi Campus"))
    campus_lat: float = field(default_factory=lambda: float(_env("CAMPUS_LAT", "24.8607")))
    campus_lng: float = field(default_factory=lambda: float(_env("CAMPUS_LNG", "67.0700")))
    # Cost model inputs (PKR). Update fuel price to the current OGRA rate.
    fuel_price_pkr: float = field(default_factory=lambda: float(_env("FUEL_PRICE_PKR", "265")))
    fuel_km_per_litre: float = field(default_factory=lambda: float(_env("FUEL_KM_PER_LITRE", "12")))
    # Road distance is longer than straight-line distance; 1.3 is a common urban factor.
    road_factor: float = field(default_factory=lambda: float(_env("ROAD_FACTOR", "1.3")))
    co2_kg_per_litre: float = 2.31  # petrol combustion, IPCC default
    max_circle_size: int = 5
    schedule_window_min: int = 30  # arrival times within this window count as compatible
    min_shared_days: int = 2


settings = Settings()
