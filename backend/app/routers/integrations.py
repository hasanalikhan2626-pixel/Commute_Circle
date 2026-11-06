"""WhatsApp webhook and the scheduled-jobs endpoint."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import TripStatus, User
from ..services import clock, jobs, notify, trips
from ..services.candidates import active_circle_of

router = APIRouter(prefix="/api", tags=["integrations"])
HELP = "Reply 1 if you reached campus with your circle, 2 if you didn't go, a number for your fare share in Rs, or STOP to turn off WhatsApp messages."


@router.post("/jobs/run")
def run_jobs(x_jobs_token: str = Header(default=""), db: Session = Depends(get_db)):
    expected = os.environ.get("CC_JOBS_TOKEN", "")
    if not expected or not hmac.compare_digest(x_jobs_token, expected):
        raise HTTPException(403, "Bad jobs token")
    return jobs.run(db)


@router.get("/whatsapp/webhook", response_class=PlainTextResponse)
def verify(request: Request):
    q = request.query_params
    token = os.environ.get("CC_WHATSAPP_VERIFY_TOKEN", "")
    if q.get("hub.mode") == "subscribe" and token and hmac.compare_digest(q.get("hub.verify_token", ""), token):
        return q.get("hub.challenge", "")
    raise HTTPException(403, "Verification failed")


def _signature_ok(body: bytes, header: str) -> bool:
    secret = os.environ.get("CC_WHATSAPP_APP_SECRET", "")
    if not secret:
        return not settings.production  # never accept unsigned webhooks in production
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header or "")


def handle_message(db: Session, phone: str, text: str) -> str:
    """Act on one incoming WhatsApp message; returns the reply text."""
    user = db.scalar(select(User).where(User.phone == "+" + phone.lstrip("+")))
    if not user or not user.can_sign_in:
        return "This number isn't linked to a CommuteCircle account. Add it on your Account page."
    t_in = text.strip().lower()
    if t_in in ("stop", "unsubscribe"):
        user.whatsapp_opt_in = False
        return "WhatsApp messages are off. Turn them back on from your Account page."
    c = active_circle_of(db, user.id)
    trip = trips.ensure_trip(db, c, clock.today()) if c else None
    status = trips.status_of(trip, user.id) if trip else None
    if t_in in ("1", "yes", "y"):
        if status is None:
            return "No circle trip is planned for you today."
        if trip.confirmed_by:
            trips.set_status(trip, user.id, TripStatus.went)
            return "Thanks, you're marked as travelled today."
        trips.set_status(trip, user.id, TripStatus.planned)
        trips.confirm(trip, user.id)
        ask = trips.rate_for(trip.mode) > 0
        return "✓ Confirmed for your circle." + (" What was your share of the fare? Reply with an amount in Rs, or skip." if ask else "")
    if t_in in ("2", "no", "n"):
        if status is None:
            return "No circle trip is planned for you today."
        trips.set_status(trip, user.id, TripStatus.notgoing)
        return "Marked as not travelling today."
    if t_in == "skip" and trip and trip.confirmed_by == user.id:
        trip.fare_skipped = True
        return "No problem, fare skipped."
    m = re.fullmatch(r"(?:rs\.?\s*)?(\d{1,5})", t_in)
    if m and trip and trip.confirmed_by == user.id and trip.total is None:
        trip.payer_id = user.id
        trip.total = int(m.group(1)) * len(trips.sharers(trip))
        return f"Saved: Rs {m.group(1)} each. It's in your circle's Money tab."
    return HELP


@router.post("/whatsapp/webhook")
async def receive(request: Request, x_hub_signature_256: str = Header(default=""), db: Session = Depends(get_db)):
    body = await request.body()
    if not _signature_ok(body, x_hub_signature_256):
        raise HTTPException(403, "Bad signature")
    data = json.loads(body or b"{}")
    handled = 0
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                if msg.get("type") != "text":
                    continue
                reply = handle_message(db, msg.get("from", ""), msg.get("text", {}).get("body", ""))
                user = db.scalar(select(User).where(User.phone == "+" + msg.get("from", "").lstrip("+")))
                notify.whatsapp_text(db, "+" + msg.get("from", "").lstrip("+"), reply, user_id=user.id if user else None)
                handled += 1
    db.commit()
    return {"handled": handled}
