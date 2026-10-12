from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import WorkspaceCtx, current_user, get_workspace
from app.copilot import coordinator, drafts
from app.copilot.core import CopilotContext
from app.core import ratelimit
from app.db import get_db
from app.intelligence.errors import IntelligenceError
from app.models import CopilotMessage, RagDocument, Shipment, User
from app.rag import indexer
from app.rag.store import Scope
from app.services import access

router = APIRouter(tags=["copilot"])


def _ctx(w: WorkspaceCtx, db: Session) -> CopilotContext:
    return CopilotContext(db, w.user, w.shipment, w.access, w.party_role)


def _owner(w: WorkspaceCtx) -> None:
    if w.access != "owner":
        raise HTTPException(403, "Only the organisation that owns the shipment can do this.")


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@router.post("/shipments/{shipment_id}/copilot/ask")
def ask(body: AskIn, w: WorkspaceCtx = Depends(get_workspace), db: Session = Depends(get_db)):
    ratelimit.check(f"ask:{w.user.id}", 20)
    try:
        return coordinator.ask(_ctx(w, db), body.question.strip())
    except IntelligenceError as exc:
        raise HTTPException(502, str(exc))


@router.get("/shipments/{shipment_id}/copilot/history")
def history(w: WorkspaceCtx = Depends(get_workspace), db: Session = Depends(get_db)):
    rows = db.query(CopilotMessage).filter_by(shipment_id=w.shipment.id, user_id=w.user.id).order_by(CopilotMessage.id.desc()).limit(10).all()
    return [{"id": r.id, "question": r.question, "answer": r.answer, "evidence": r.evidence or [], "agents": r.agents or [], "engine": r.engine, "grounded": r.grounded, "created_at": r.created_at.isoformat()} for r in reversed(rows)]


@router.post("/shipments/{shipment_id}/copilot/reindex")
def reindex(w: WorkspaceCtx = Depends(get_workspace), db: Session = Depends(get_db)):
    _owner(w)
    try:
        return indexer.ensure_indexed(db, w.shipment, force=True)
    except IntelligenceError as exc:
        raise HTTPException(502, str(exc))


class DraftIn(BaseModel):
    audience: str


@router.post("/shipments/{shipment_id}/copilot/draft-update")
def draft_update(body: DraftIn, w: WorkspaceCtx = Depends(get_workspace), db: Session = Depends(get_db)):
    _owner(w)
    ratelimit.check(f"draft:{w.user.id}", 10)
    try:
        return drafts.draft(_ctx(w, db), body.audience)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


class SendIn(BaseModel):
    to_roles: list[str] = Field(min_length=1)
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=10, max_length=3000)


@router.post("/shipments/{shipment_id}/updates/send")
def send_update(body: SendIn, w: WorkspaceCtx = Depends(get_workspace), db: Session = Depends(get_db)):
    _owner(w)
    if not w.user.email_verified:
        raise HTTPException(403, "Confirm your email address before sending updates.")
    ratelimit.check(f"send:{w.shipment.id}", 10, 3600)
    bad = [r for r in body.to_roles if r not in access.PARTY_ROLES]
    if bad:
        raise HTTPException(422, "Choose broker, forwarder, importer or exporter.")
    try:
        return {"sent_to": drafts.send(_ctx(w, db), body.to_roles, body.subject.strip(), body.body.strip())}
    except LookupError as exc:
        raise HTTPException(409, str(exc))


@router.get("/copilot/status")
def copilot_status(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return indexer.status(db, user.org_id)


# ------------------------------------------------------------------ library
def _doc_out(d: RagDocument, current: dict) -> dict:
    return {"id": d.id, "title": d.title, "filename": d.filename, "tags": d.tags, "size_bytes": d.size_bytes, "chunk_count": d.chunk_count, "created_by": d.created_by, "created_at": d.created_at.isoformat(),
            "stale": d.embedder != current["embedder"] or d.store != current["vector_store"]}


@router.get("/knowledge")
def library(db: Session = Depends(get_db), user: User = Depends(current_user)):
    st = indexer.status(db, user.org_id)
    return {"status": st, "documents": [_doc_out(d, st) for d in db.query(RagDocument).filter_by(org_id=user.org_id).order_by(RagDocument.id.desc())]}


@router.post("/knowledge", status_code=201)
async def upload(file: UploadFile = File(...), title: str = Form(""), tags: str = Form(""), db: Session = Depends(get_db), user: User = Depends(current_user)):
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "File is larger than 10 MB.")
    try:
        doc = indexer.add_library_doc(db, user.org_id, title or (file.filename or "Document"), file.filename or "document", data, tags, user.name)
    except indexer.UnreadableFile as exc:
        raise HTTPException(422, str(exc))
    except IntelligenceError as exc:
        db.rollback()
        raise HTTPException(502, f"Could not index the document: {exc}")
    return _doc_out(doc, indexer.status(db, user.org_id))


@router.delete("/knowledge/{doc_id}")
def remove(doc_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = db.get(RagDocument, doc_id)
    if not doc or doc.org_id != user.org_id:
        raise HTTPException(404, "Document not found.")
    indexer.delete_library_doc(db, doc)
    return {"ok": True}


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    scope: str = "library"  # library | org
    k: int = Field(default=6, ge=1, le=12)


@router.post("/knowledge/search")
def search(body: SearchIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    ratelimit.check(f"search:{user.id}", 30)
    try:
        hits = indexer.search(db, Scope("org" if body.scope == "org" else "library", user.org_id), body.query, body.k)
    except IntelligenceError as exc:
        raise HTTPException(502, str(exc))
    refs = {s.id: s.reference for s in db.query(Shipment).filter(Shipment.id.in_([h["shipment_id"] for h in hits if h["shipment_id"]] or [0]))}
    return [{"title": h["title"], "text": h["text"][:500], "page": h["page"], "score": round(float(h["score"]), 3), "source_type": h["source_type"], "shipment_reference": refs.get(h["shipment_id"])} for h in hits]


@router.post("/knowledge/reindex")
def reindex_library(db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        return {"chunks": indexer.reindex_library(db, user.org_id)}
    except IntelligenceError as exc:
        db.rollback()
        raise HTTPException(502, str(exc))


@router.post("/knowledge/index-shipments")
def index_shipments(db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        n = sum(indexer.ensure_indexed(db, s)["chunks"] for s in access.owned_shipments(db, user))
    except IntelligenceError as exc:
        db.rollback()
        raise HTTPException(502, str(exc))
    return {"chunks": n}
