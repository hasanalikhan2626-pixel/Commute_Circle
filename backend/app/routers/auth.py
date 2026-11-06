from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import current_user
from ..models import Profile, Report, User, UserStatus
from ..schemas import CodeIn, DeleteAccountIn, ForgotIn, RegisterIn, ResetIn, UserUpdate
from ..security import create_token, hash_password, throttle, verify_password
from ..services import circles as svc

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(u: User) -> dict:
    p = u.profile
    return {
        "id": u.id, "email": u.email, "full_name": u.full_name, "phone": u.phone, "role": u.role.value,
        "status": u.status.value, "research_consent": u.research_consent, "email_verified": u.email_verified,
        "whatsapp_opt_in": u.whatsapp_opt_in, "emergency_name": u.emergency_name, "emergency_phone": u.emergency_phone,
        "gender": p.gender.value if p else None, "programme": p.programme if p else None,
        "year": p.year if p else None, "has_trip": bool(p and p.area and p.schedule and p.methods),
    }


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    if db.scalar(select(User).where(User.phone == body.phone)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This mobile number is already linked to another account")
    user = User(email=body.email, password_hash=hash_password(body.password), full_name=body.full_name,
                phone=body.phone, research_consent=body.research_consent, status=UserStatus.pending,
                consented_at=datetime.now(timezone.utc), consent_version=settings.consent_version)
    user.profile = Profile(gender=body.gender, programme=body.programme, year=body.year)
    db.add(user)
    db.flush()
    from ..services import codes

    codes.send(db, user, "verify")
    db.commit()
    return {"access_token": create_token(user.id), "token_type": "bearer"}


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form.username.strip().lower()
    if throttle.blocked(email):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Try again in 15 minutes.")
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(form.password, user.password_hash):
        throttle.fail(email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.can_sign_in:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"This account is {user.status.value}. Contact Student Affairs.")
    throttle.reset(email)
    return {"access_token": create_token(user.id), "token_type": "bearer"}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.patch("/me")
def update_me(body: UserUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.phone and db.scalar(select(User).where(User.phone == body.phone, User.id != user.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This mobile number is already linked to another account")
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None or k in ("emergency_name", "emergency_phone"):
            setattr(user, k, v)
    db.commit()
    return user_out(user)


@router.get("/me/export")
def export_my_data(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Everything stored about the signed-in student (right of access)."""
    from ..models import Feedback, TripMember

    p = user.profile
    return {
        "account": {"email": user.email, "full_name": user.full_name, "phone": user.phone, "role": user.role.value,
                    "status": user.status.value, "created_at": user.created_at, "consented_at": user.consented_at,
                    "consent_version": user.consent_version, "research_consent": user.research_consent},
        "profile": None if not p else {
            "gender": p.gender.value, "programme": p.programme, "year": p.year, "area": p.area,
            "women_only": p.women_only, "methods": p.methods, "has_car": p.has_car, "seats": p.seats,
            "schedule": p.schedule, "seeking": p.seeking},
        "circles": [{"circle_id": m.circle_id, "status": m.circle.status.value, "my_status": m.status.value,
                     "joined_at": m.joined_at} for m in user.memberships],
        "trips": [{"day": tm.trip.day, "status": tm.status.value, "mode": tm.trip.mode}
                  for tm in db.scalars(select(TripMember).where(TripMember.user_id == user.id))],
        "feedback_given": [{"tag": f.tag, "up": f.up, "created_at": f.created_at}
                           for f in db.scalars(select(Feedback).where(Feedback.from_id == user.id))],
        "reports_made": [{"reason": r.reason, "details": r.details, "status": r.status.value, "created_at": r.created_at}
                         for r in db.scalars(select(Report).where(Report.reporter_id == user.id))],
    }


@router.delete("/me", status_code=204)
def delete_account(body: DeleteAccountIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Permanently delete the account (right to erasure). Leaves any live circle first."""
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Password is incorrect")
    svc.remove_user_everywhere(db, user)
    db.delete(user)
    db.commit()


# --- Email verification and password reset --------------------------------------

@router.post("/verify/send")
def verify_send(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..services import codes

    if user.email_verified:
        return {"ok": True, "already": True}
    try:
        codes.send(db, user, "verify")
    except codes.CodeError as e:
        raise HTTPException(429, str(e)) from e
    db.commit()
    return {"ok": True}


@router.post("/verify")
def verify(body: CodeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..services import codes

    try:
        codes.check(db, user, "verify", body.code)
    except codes.CodeError as e:
        raise HTTPException(422, str(e)) from e
    user.email_verified = True
    db.commit()
    return user_out(user)


@router.post("/forgot")
def forgot(body: ForgotIn, db: Session = Depends(get_db)):
    """Always answers the same way, so it can't be used to find out who has an account."""
    from ..services import codes

    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user and user.can_sign_in:
        try:
            codes.send(db, user, "reset")
            db.commit()
        except codes.CodeError:
            pass
    return {"ok": True, "message": "If that email has an account, we've sent a reset code."}


@router.post("/reset")
def reset(body: ResetIn, db: Session = Depends(get_db)):
    from ..services import codes

    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user:
        raise HTTPException(422, "That code isn't right")
    try:
        codes.check(db, user, "reset", body.code)
    except codes.CodeError as e:
        raise HTTPException(422, str(e)) from e
    user.password_hash = hash_password(body.new_password)
    user.email_verified = True  # they proved they own the inbox
    throttle.reset(user.email)
    db.commit()
    return {"access_token": create_token(user.id), "token_type": "bearer"}
