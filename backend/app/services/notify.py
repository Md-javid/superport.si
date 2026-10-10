from sqlalchemy.orm import Session

from app.models import Notification


def notify(db: Session, user_ids, title: str, body: str = "", *, kind: str, shipment_id: int | None = None, link: str = "") -> None:
    for uid in set(user_ids):
        db.add(Notification(user_id=uid, shipment_id=shipment_id, kind=kind, title=title[:200], body=body[:500], link=link))
