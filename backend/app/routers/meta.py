from fastapi import APIRouter

from ..areas import AREAS
from ..config import settings
from ..matching.compat import DAYS
from ..schemas import REPORT_REASONS

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("")
def meta():
    return {
        "areas": sorted(AREAS),
        "days": list(DAYS),
        "campus": {"name": settings.campus_name, "lat": settings.campus_lat, "lng": settings.campus_lng},
        "report_reasons": list(REPORT_REASONS),
        "max_circle_size": settings.max_circle_size,
        "schedule_window_min": settings.schedule_window_min,
    }
