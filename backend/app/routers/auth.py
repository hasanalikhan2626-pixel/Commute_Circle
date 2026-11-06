from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..schemas import RegisterIn, TokenOut, UserOut, UserUpdate
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
                full_name=body.full_name, phone=body.phone)
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
