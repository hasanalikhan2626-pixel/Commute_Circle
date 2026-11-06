from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Profile, User
from ..schemas import ProfileIn, ProfileOut
from ..services.circles import refresh_after_profile_change

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def get_profile(user: User = Depends(current_user)):
    if not user.profile:
        raise HTTPException(404, "Profile not set up yet")
    return ProfileOut.model_validate(user.profile)


@router.put("", response_model=ProfileOut)
def put_profile(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = body.model_dump()
    data["schedule"] = {d: s for d, s in data["schedule"].items()}
    if user.profile:
        for k, v in data.items():
            setattr(user.profile, k, v)
    else:
        user.profile = Profile(**data)
    db.flush()
    warning = refresh_after_profile_change(db, user.id)
    db.commit()
    out = ProfileOut.model_validate(user.profile)
    out.warning = warning
    return out
