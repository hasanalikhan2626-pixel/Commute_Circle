from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from datetime import datetime, timezone

from ..config import settings
from ..models import CircleMember, CircleStatus, MemberStatus, Report, User
from ..schemas import DeleteAccountIn, RegisterIn, TokenOut, UserOut, UserUpdate
from ..security import create_token, hash_password, throttle, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(u: User) -> UserOut:
    out = UserOut.model_validate(u)
    out.has_profile = u.profile is not None
    return out


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(email=body.email, password_hash=hash_password(body.password),
                full_name=body.full_name, phone=body.phone, research_consent=body.research_consent,
                consented_at=datetime.now(timezone.utc), consent_version=settings.consent_version)
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form.username.strip().lower()
    if throttle.blocked(email):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Try again in 15 minutes.")
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(form.password, user.password_hash):
        throttle.fail(email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been suspended")
    throttle.reset(email)
    return TokenOut(access_token=create_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.patch("/me", response_model=UserOut)
def update_me(body: UserUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit()
    return user_out(user)


@router.get("/me/export")
def export_my_data(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Everything stored about the signed-in student (right of access)."""
    p = user.profile
    return {
        "account": {
            "email": user.email, "full_name": user.full_name, "phone": user.phone, "role": user.role.value,
            "created_at": user.created_at, "consented_at": user.consented_at,
            "consent_version": user.consent_version, "research_consent": user.research_consent,
        },
        "profile": None if not p else {
            "area": p.area, "pickup_landmark": p.pickup_landmark, "gender": p.gender.value,
            "same_gender_only": p.same_gender_only, "has_car": p.has_car, "seats": p.seats,
            "schedule": p.schedule, "seeking": p.seeking, "updated_at": p.updated_at,
        },
        "circles": [
            {"circle_id": m.circle_id, "status": m.circle.status.value, "my_status": m.status.value,
             "is_driver": m.is_driver, "joined_at": m.joined_at}
            for m in user.memberships
        ],
        "reports_made": [
            {"id": r.id, "reason": r.reason, "details": r.details, "status": r.status.value, "created_at": r.created_at}
            for r in db.scalars(select(Report).where(Report.reporter_id == user.id))
        ],
    }


@router.delete("/me", status_code=204)
def delete_account(body: DeleteAccountIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Permanently delete the account (right to erasure). Leaves any live circle first."""
    from ..services import circles as svc

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Password is incorrect")
    for m in list(user.memberships):
        if m.status in (MemberStatus.pending, MemberStatus.accepted) and m.circle.status != CircleStatus.dissolved:
            svc.leave(db, m.circle, user.id)
    db.delete(user)
    db.commit()
