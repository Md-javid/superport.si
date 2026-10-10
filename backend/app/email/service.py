"""Email sending. Resend when configured, otherwise a console provider that stores the message in an outbox.

In demo mode the console provider returns the link so the UI can show it (no inbox needed).
"""
import logging

import httpx

from app.core.config import get_settings
from app.models import EmailOutbox

log = logging.getLogger("superport.email")
_transport: httpx.BaseTransport | None = None


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = transport


def send(db, to: str, subject: str, body: str, link: str = "") -> dict:
    s = get_settings()
    if s.resend_api_key and s.email_from:
        try:
            with httpx.Client(transport=_transport, timeout=15) as client:
                r = client.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {s.resend_api_key}"}, json={"from": s.email_from, "to": [to], "subject": subject, "text": body})
            ok = r.status_code < 300
        except httpx.HTTPError:
            ok = False
        db.add(EmailOutbox(to_email=to, subject=subject, body=body, link=link, provider="resend", status="sent" if ok else "failed"))
        if not ok:
            log.warning("email to %s failed", to)
        return {"provider": "resend", "sent": ok, "dev_link": None}
    db.add(EmailOutbox(to_email=to, subject=subject, body=body, link=link, provider="console", status="logged"))
    log.info("EMAIL to %s: %s %s", to, subject, link)
    return {"provider": "console", "sent": False, "dev_link": link if (link and s.demo_mode) else None}
