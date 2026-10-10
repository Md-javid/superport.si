import hashlib
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core import ratelimit
from app.core.config import get_settings
from app.core.security import create_access_token, create_purpose_token, decode_purpose_token, hash_password, pw_fingerprint, verify_password
from app.db import get_db
from app.email import service as mail
from app.models import AuditEvent, Invitation, Organization, ShipmentParticipant, User, utcnow
from app.schemas import LoginIn
from app.services import notify

router = APIRouter(prefix="/auth", tags=["auth"])
DEMO_PASSWORD = "superport-demo"
DEMO_EMAIL = "demo@superport.ai"
PERSONAS = {"broker": DEMO_EMAIL, "forwarder": "forwarder@superport.ai", "importer": "importer@superport.ai"}


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "company": u.company, "org_id": u.org_id, "org_name": u.org.name if u.org else "",
            "org_type": u.org.type if u.org else "", "org_role": u.org_role, "email_verified": bool(u.email_verified)}


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check_password(password: str) -> None:
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(422, "Use at least 8 characters with a letter and a number.")


def _send_verification(db: Session, user: User) -> dict:
    token = create_purpose_token("verify", user.id, 60 * 24 * 3, {"email": user.email})
    link = f"{get_settings().app_url}/verify-email?token={token}"
    return mail.send(db, user.email, "Confirm your SuperPort email", f"Hi {user.name},\n\nConfirm your email to invite partners to shipments:\n{link}\n\nThis link works for 3 days.", link)


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.check(f"login:{_ip(request)}:{body.email.lower()}", 10)
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect.")
    return {"token": create_access_token(user.id, body.remember), "user": user_out(user)}


@router.post("/demo")
def demo_login(persona: str = "broker", db: Session = Depends(get_db)):
    if not get_settings().demo_mode:
        raise HTTPException(403, "Demo login is disabled on this server.")
    user = db.query(User).filter(User.email == PERSONAS.get(persona, DEMO_EMAIL)).first()
    if not user:
        raise HTTPException(404, "Demo user has not been seeded.")
    return {"token": create_access_token(user.id), "user": user_out(user)}


class RegisterIn(BaseModel):
    org_name: str = Field(default="", max_length=200)
    org_type: Literal["broker", "forwarder", "importer", "exporter"] = "broker"
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    invite_token: str | None = None


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.check(f"register:{_ip(request)}", 6)
    _check_password(body.password)
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    invite = None
    if body.invite_token:
        invite = db.query(Invitation).filter_by(token_hash=hashlib.sha256(body.invite_token.encode()).hexdigest()).first()
        if not invite or invite.status != "pending" or invite.expires_at.replace(tzinfo=utcnow().tzinfo) < utcnow():
            raise HTTPException(410, "This invitation is no longer valid. Ask for a new one.")
        if invite.email.lower() != email:
            raise HTTPException(403, "This invitation was sent to a different email address.")

    if invite and invite.kind == "team":
        org, role = db.get(Organization, invite.org_id), "member"
    else:
        org_type = invite.party_role if invite else body.org_type
        if len(body.org_name.strip()) < 2:
            raise HTTPException(422, "Enter your company name.")
        org, role = Organization(name=body.org_name.strip(), type=org_type), "admin"
        db.add(org)
        db.flush()
    user = User(email=email, name=body.name.strip(), role=org.type.title(), company=org.name, password_hash=hash_password(body.password), org_id=org.id, org_role=role, email_verified=bool(invite))
    db.add(user)
    db.flush()
    result = {}
    if invite:
        invite.status = "accepted"
        if invite.kind == "shipment":
            db.add(ShipmentParticipant(shipment_id=invite.shipment_id, org_id=org.id, party_role=invite.party_role, invited_by=invite.invited_by))
            db.add(AuditEvent(shipment_id=invite.shipment_id, actor=user.name, kind="human", action="participant_joined", message=f"{org.name} joined as {invite.party_role}."))
            inviter = db.get(User, invite.invited_by) if invite.invited_by else None
            if inviter:
                notify.notify(db, [inviter.id], f"{org.name} joined the shipment", f"{user.name} accepted your invitation as {invite.party_role}.", kind="participant_joined", shipment_id=invite.shipment_id, link=f"/shipments/{invite.shipment_id}/workspace")
    else:
        result = _send_verification(db, user)
    db.commit()
    return {"token": create_access_token(user.id), "user": user_out(user), "dev_link": result.get("dev_link"), "joined_shipment_id": invite.shipment_id if invite and invite.kind == "shipment" else None}


class TokenIn(BaseModel):
    token: str


@router.post("/verify-email")
def verify_email(body: TokenIn, db: Session = Depends(get_db)):
    payload = decode_purpose_token(body.token, "verify")
    user = db.get(User, int(payload["sub"])) if payload else None
    if not user or payload.get("email") != user.email:
        raise HTTPException(400, "This verification link is invalid or has expired.")
    user.email_verified = True
    db.commit()
    return user_out(user)


@router.post("/resend-verification")
def resend_verification(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.email_verified:
        return {"already_verified": True, "dev_link": None}
    result = _send_verification(db, user)
    db.commit()
    return {"already_verified": False, "dev_link": result.get("dev_link")}


class ForgotIn(BaseModel):
    email: EmailStr


@router.post("/forgot-password")
def forgot_password(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.check(f"forgot:{_ip(request)}", 5)
    user = db.query(User).filter(User.email == body.email.lower()).first()
    dev_link = None
    if user:
        token = create_purpose_token("reset", user.id, 60, {"pwf": pw_fingerprint(user.password_hash)})
        link = f"{get_settings().app_url}/reset-password?token={token}"
        dev_link = mail.send(db, user.email, "Reset your SuperPort password", f"Hi {user.name},\n\nReset your password here:\n{link}\n\nThis link works once, for 1 hour. If you did not ask for it, ignore this email.", link).get("dev_link")
        db.commit()
    return {"message": "If that email has an account, a reset link is on its way.", "dev_link": dev_link}


class ResetIn(BaseModel):
    token: str
    password: str


@router.post("/reset-password")
def reset_password(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.check(f"reset:{_ip(request)}", 10)
    _check_password(body.password)
    payload = decode_purpose_token(body.token, "reset")
    user = db.get(User, int(payload["sub"])) if payload else None
    if not user or payload.get("pwf") != pw_fingerprint(user.password_hash):
        raise HTTPException(400, "This reset link is invalid, already used, or expired.")
    user.password_hash = hash_password(body.password)
    db.commit()
    return {"message": "Password updated. You can sign in now."}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)
