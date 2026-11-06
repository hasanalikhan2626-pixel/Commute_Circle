from fastapi import APIRouter

from ..areas import AREAS
from ..config import settings
from ..matching.compat import DAYS, DRIVE_MODES, METHODS
from ..schemas import PROGRAMMES, REPORT_REASONS
from ..services.trips import NEG_TAGS, TAGS

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("")
def meta():
    return {
        "areas": {k: list(v) for k, v in sorted(AREAS.items())},
        "days": list(DAYS), "methods": list(METHODS), "drive_modes": list(DRIVE_MODES),
        "programmes": list(PROGRAMMES), "report_reasons": list(REPORT_REASONS),
        "tags": list(TAGS), "neg_tags": list(NEG_TAGS),
        "campus": {"name": settings.campus_name, "lat": settings.campus_lat, "lng": settings.campus_lng},
        "max_circle_size": settings.max_circle_size, "consent_version": settings.consent_version,
    }
