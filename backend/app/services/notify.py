"""Outgoing WhatsApp messages and emails, through one outbox.

WhatsApp: Meta WhatsApp Cloud API (graph.facebook.com). Needs CC_WHATSAPP_TOKEN and
CC_WHATSAPP_PHONE_ID; business-initiated messages must use templates approved by Meta
(names in TEMPLATES, text in docs/WHATSAPP.md).
Email: Brevo transactional API (api.brevo.com). Needs CC_BREVO_API_KEY and CC_EMAIL_FROM.

When a service isn't configured, the message is stored with status "mock" and not sent, so
every feature can be developed and demonstrated before the accounts exist.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Notification

log = logging.getLogger("commutecircle")
GRAPH = "https://graph.facebook.com/v21.0"
BREVO = "https://api.brevo.com/v3/smtp/email"
TEMPLATES = {  # Meta template name -> number of {{n}} parameters
    "cc_reminder": 3,   # trip reminder 45 min before arrival
    "cc_checkin": 1,    # "Reached campus? Reply 1 = Yes, 2 = Didn't go"
    "cc_sos": 3,        # SOS to emergency contact / campus security
    "cc_proposal": 2,   # a classmate suggested a circle
}


def whatsapp_ready() -> bool:
    return bool(os.environ.get("CC_WHATSAPP_TOKEN") and os.environ.get("CC_WHATSAPP_PHONE_ID"))


def email_ready() -> bool:
    return bool(os.environ.get("CC_BREVO_API_KEY") and os.environ.get("CC_EMAIL_FROM"))


def _post(url: str, payload: dict, headers: dict) -> tuple[bool, str | None]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300, None
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode(errors='replace')[:500]}"
    except (urllib.error.URLError, TimeoutError) as e:
        return False, str(e)[:500]


def _record(db: Session, **kw) -> Notification | None:
    """Store first; a duplicate ``dedupe`` key means it was already sent."""
    n = Notification(**kw)
    db.add(n)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return None
    return n


def whatsapp(db: Session, to_phone: str, template: str, params: list[str], *, user_id: int | None = None,
             dedupe: str | None = None) -> Notification | None:
    body = f"{template}: " + " | ".join(params)
    n = _record(db, channel="whatsapp", to=to_phone, template=template, body=body, user_id=user_id, dedupe=dedupe)
    if n is None:
        return None
    if not whatsapp_ready():
        n.status = "mock"
        return n
    payload = {"messaging_product": "whatsapp", "to": to_phone.lstrip("+"), "type": "template",
               "template": {"name": template, "language": {"code": os.environ.get("CC_WHATSAPP_LANG", "en")},
                            "components": [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}]}}
    ok, err = _post(f"{GRAPH}/{os.environ['CC_WHATSAPP_PHONE_ID']}/messages", payload,
                    {"Authorization": f"Bearer {os.environ['CC_WHATSAPP_TOKEN']}"})
    n.status, n.error = ("sent", None) if ok else ("failed", err)
    if not ok:
        log.warning("WhatsApp %s to %s failed: %s", template, to_phone, err)
    return n


def whatsapp_text(db: Session, to_phone: str, text: str, *, user_id: int | None = None) -> Notification | None:
    """Free-text reply, allowed only inside the 24-hour window after the student messaged us."""
    n = _record(db, channel="whatsapp", to=to_phone, template="text", body=text, user_id=user_id)
    if n is None:
        return None
    if not whatsapp_ready():
        n.status = "mock"
        return n
    ok, err = _post(f"{GRAPH}/{os.environ['CC_WHATSAPP_PHONE_ID']}/messages",
                    {"messaging_product": "whatsapp", "to": to_phone.lstrip("+"), "type": "text", "text": {"body": text}},
                    {"Authorization": f"Bearer {os.environ['CC_WHATSAPP_TOKEN']}"})
    n.status, n.error = ("sent", None) if ok else ("failed", err)
    return n


def email(db: Session, to: str, subject: str, text: str, *, user_id: int | None = None,
          template: str = "email") -> Notification | None:
    n = _record(db, channel="email", to=to, template=template, body=f"{subject}\n\n{text}", user_id=user_id)
    if n is None:
        return None
    if not email_ready():
        n.status = "mock"
        return n
    payload = {"sender": {"name": os.environ.get("CC_EMAIL_FROM_NAME", "CommuteCircle"), "email": os.environ["CC_EMAIL_FROM"]},
               "to": [{"email": to}], "subject": subject, "textContent": text}
    ok, err = _post(BREVO, payload, {"api-key": os.environ["CC_BREVO_API_KEY"]})
    n.status, n.error = ("sent", None) if ok else ("failed", err)
    if not ok:
        log.warning("Email to %s failed: %s", to, err)
    return n
