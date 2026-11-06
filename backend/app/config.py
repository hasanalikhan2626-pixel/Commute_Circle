"""Application settings, read from environment variables (prefix ``CC_``).

Every value has a development default so the app runs out of the box; set the
real values in production (see docs/DEPLOYMENT.md).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.environ.get(f"CC_{name}", default)


def _db_url(raw: str) -> str:
    # Hosting providers hand out postgres:// URLs; SQLAlchemy needs the driver named.
    for prefix in ("postgres://", "postgresql://"):
        if raw.startswith(prefix):
            return "postgresql+psycopg://" + raw[len(prefix):]
    return raw


@dataclass(frozen=True)
class Settings:
    env: str = field(default_factory=lambda: _env("ENV", "development"))
    secret_key: str = field(default_factory=lambda: _env("SECRET_KEY", "dev-only-change-me"))
    database_url: str = field(default_factory=lambda: _db_url(_env("DATABASE_URL", "sqlite:///./commutecircle.db")))
    token_minutes: int = field(default_factory=lambda: int(_env("TOKEN_MINUTES", "720")))
    # Comma-separated list of email domains allowed to register.
    email_domains: tuple[str, ...] = field(
        default_factory=lambda: tuple(d.strip().lower() for d in _env("EMAIL_DOMAINS", "bic.edu.pk").split(",") if d.strip())
    )
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(o.strip() for o in _env("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip())
    )
    # Campus: 273/1/A Main Ibrahim Hyderi Road, Korangi Creek, Karachi 75190.
    # Map pin supplied by the project team.
    campus_name: str = field(default_factory=lambda: _env("CAMPUS_NAME", "BIC Karachi, Korangi Creek"))
    campus_lat: float = field(default_factory=lambda: float(_env("CAMPUS_LAT", "24.8086702")))
    campus_lng: float = field(default_factory=lambda: float(_env("CAMPUS_LNG", "67.1217257")))
    # Cost model inputs (PKR per litre of petrol).
    fuel_price_pkr: float = field(default_factory=lambda: float(_env("FUEL_PRICE_PKR", "352.59")))
    fuel_km_per_litre: float = field(default_factory=lambda: float(_env("FUEL_KM_PER_LITRE", "12")))
    # Road distance is longer than straight-line distance; 1.3 is a common urban factor.
    road_factor: float = field(default_factory=lambda: float(_env("ROAD_FACTOR", "1.3")))
    co2_kg_per_litre: float = 2.31  # petrol combustion, IPCC default
    max_circle_size: int = 5
    schedule_window_min: int = 30  # arrival times within this window count as compatible
    min_shared_days: int = 2


    consent_version: str = "2026-11"  # bump when the privacy notice changes

    @property
    def production(self) -> bool:
        return self.env == "production"

    def check(self) -> None:
        """Refuse to start in production with unsafe settings."""
        if not self.production:
            return
        if self.secret_key == "dev-only-change-me" or len(self.secret_key) < 32:
            raise RuntimeError("Set CC_SECRET_KEY to a random string of at least 32 characters")
        if self.database_url.startswith("sqlite"):
            raise RuntimeError("Use PostgreSQL in production (set CC_DATABASE_URL)")
        if not self.email_domains:
            raise RuntimeError("Set CC_EMAIL_DOMAINS in production")


settings = Settings()
