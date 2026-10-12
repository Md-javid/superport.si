"""Index shipment sources and library documents, and search them."""
import hashlib
import io
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.catalog import DOC_LABELS
from app.core.config import get_settings
from app.models import ChecklistItem, Comment, Document, RagDocument, RagIndexState, Shipment, utcnow
from app.rag.chunker import chunk_pages, chunk_text
from app.rag.embedders import get_embedder
from app.rag.store import Scope, get_store

ROLE_FOR_DOC = {"commercial_invoice": "exporter", "packing_list": "exporter", "bill_of_lading": "forwarder"}


class UnreadableFile(ValueError):
    pass


def extract_pages(filename: str, data: bytes) -> list[str]:
    name = filename.lower()
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader

            pages = [(p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages]
        except Exception as exc:  # noqa: BLE001
            raise UnreadableFile("This PDF could not be read.") from exc
        if not any(p.strip() for p in pages):
            raise UnreadableFile("This PDF has no readable text (it may be a scan). Upload a text-based PDF.")
        return pages
    if name.endswith((".txt", ".md", ".csv")):
        text = data.decode("utf-8", errors="ignore")
        if not text.strip():
            raise UnreadableFile("The file is empty.")
        return [text]
    raise UnreadableFile("Upload a PDF, TXT, MD or CSV file.")


def _chunk(pages: list[str]) -> list[dict]:
    s = get_settings()
    return chunk_pages(pages, max_chars=s.rag_chunk_chars, overlap=s.rag_overlap_chars)


def shipment_sources(db: Session, shipment: Shipment) -> list[dict]:
    roles = {i.doc_type: i.party_role for i in db.query(ChecklistItem).filter_by(shipment_id=shipment.id) if i.doc_type}
    out: list[dict] = []
    for d in db.query(Document).filter_by(shipment_id=shipment.id, status="ready"):
        label, role = DOC_LABELS.get(d.doc_type, d.doc_type), roles.get(d.doc_type) or ROLE_FOR_DOC.get(d.doc_type, "")
        facts = "\n".join(f"- {f['label']}: {f['value']}" for f in (d.fields or []) if f.get("value"))
        if facts:
            out.append({"source_type": "field", "source_id": d.id, "title": f"{label}: extracted fields", "pages": [f"{label} ({d.filename}) extracted fields:\n{facts}"], "visibility": "owner", "party_role": role})
        if d.storage_path and Path(d.storage_path).exists():
            try:
                out.append({"source_type": "text", "source_id": d.id, "title": f"{label}: {d.filename}", "pages": extract_pages(d.filename, Path(d.storage_path).read_bytes()), "visibility": "owner", "party_role": role})
            except UnreadableFile:
                pass
    for i in db.query(ChecklistItem).filter_by(shipment_id=shipment.id, status="uploaded"):
        if not i.doc_type and i.storage_path and Path(i.storage_path).exists():
            try:
                out.append({"source_type": "text", "source_id": 100000 + i.id, "title": f"{i.label}: {i.filename}", "pages": extract_pages(i.filename, Path(i.storage_path).read_bytes()), "visibility": "owner", "party_role": i.party_role})
            except UnreadableFile:
                pass
    for c in db.query(Comment).filter_by(shipment_id=shipment.id).order_by(Comment.id):
        out.append({"source_type": "comment", "source_id": c.id, "title": f"Comment by {c.author}", "pages": [f"{c.author} ({c.org_name}, {c.party_role}): {c.body}"], "visibility": "all", "party_role": ""})
    return out


def _fingerprint(sources: list[dict], embedder: str, store: str) -> str:
    blob = json.dumps([[s["source_type"], s["source_id"], s["visibility"], s["party_role"], hashlib.sha1("\n".join(s["pages"]).encode()).hexdigest()] for s in sources] + [embedder, store])
    return hashlib.sha256(blob.encode()).hexdigest()


def ensure_indexed(db: Session, shipment: Shipment, *, force: bool = False) -> dict:
    """Re-index only when the shipment's sources (or the embedder / store) changed."""
    embedder, store = get_embedder(), get_store()
    sources = shipment_sources(db, shipment)
    fp = _fingerprint(sources, embedder.name, store.name)
    state = db.get(RagIndexState, shipment.id)
    if state and state.fingerprint == fp and not force:
        return {"chunks": state.chunk_count, "reindexed": False}
    chunks: list[dict] = []
    for s in sources:
        for c in _chunk(s["pages"]):
            chunks.append({"org_id": shipment.org_id, "shipment_id": shipment.id, "source_type": s["source_type"], "source_id": s["source_id"], "title": s["title"], "page": c["page"], "text": c["text"], "visibility": s["visibility"], "party_role": s["party_role"]})
    vectors = embedder.embed_documents([c["text"] for c in chunks]) if chunks else []  # embed first: a failure leaves the old index intact
    store.delete(db, shipment_id=shipment.id)
    if chunks:
        store.add(db, chunks, vectors, embedder.name)
    if state:
        state.fingerprint, state.embedder, state.store, state.chunk_count, state.indexed_at = fp, embedder.name, store.name, len(chunks), utcnow()
    else:
        db.add(RagIndexState(shipment_id=shipment.id, fingerprint=fp, embedder=embedder.name, store=store.name, chunk_count=len(chunks)))
    db.commit()
    return {"chunks": len(chunks), "reindexed": True}


def index_library_doc(db: Session, doc: RagDocument) -> int:
    embedder, store = get_embedder(), get_store()
    chunks = [{"org_id": doc.org_id, "shipment_id": None, "source_type": "knowledge", "source_id": doc.id, "title": doc.title, "page": c["page"], "text": c["text"], "visibility": "owner"} for c in _chunk([doc.text])]
    vectors = embedder.embed_documents([c["text"] for c in chunks]) if chunks else []
    store.delete(db, source_type="knowledge", source_id=doc.id, org_id=doc.org_id)
    if chunks:
        store.add(db, chunks, vectors, embedder.name)
    doc.chunk_count, doc.embedder, doc.store = len(chunks), embedder.name, store.name
    return len(chunks)


def add_library_doc(db: Session, org_id: int, title: str, filename: str, data: bytes, tags: str, user_name: str) -> RagDocument:
    pages = extract_pages(filename, data)
    doc = RagDocument(org_id=org_id, title=title.strip()[:300] or filename, filename=filename, tags=tags[:300], text="\n\n".join(pages), size_bytes=len(data), created_by=user_name)
    db.add(doc)
    db.flush()
    index_library_doc(db, doc)
    db.commit()
    return doc


def delete_library_doc(db: Session, doc: RagDocument) -> None:
    get_store().delete(db, source_type="knowledge", source_id=doc.id, org_id=doc.org_id)
    db.delete(doc)
    db.commit()


def reindex_library(db: Session, org_id: int) -> int:
    n = 0
    for doc in db.query(RagDocument).filter_by(org_id=org_id):
        n += index_library_doc(db, doc)
    db.commit()
    return n


def search(db: Session, scope: Scope, query: str, k: int | None = None) -> list[dict]:
    """Return the most relevant passages. Weak matches are dropped so the copilot says 'not found' honestly."""
    embedder, store = get_embedder(), get_store()
    k = k or get_settings().rag_top_k
    hits = store.search(db, scope, embedder.embed_query(query), embedder.name, k * 2)
    if not hits:
        return []
    floor = max(0.05 if not embedder.semantic else 0.25, hits[0]["score"] * 0.5)
    return [h for h in hits if h["score"] >= floor][:k]


def status(db: Session, org_id: int) -> dict:
    from app.rag.store import STATE

    embedder, store = get_embedder(), get_store()
    docs = db.query(RagDocument).filter_by(org_id=org_id).all()
    return {"vector_store": store.name, "pgvector_error": STATE["error"], "embedder": embedder.name, "semantic": embedder.semantic, "dim": embedder.dim, "chunks": store.count(db, org_id),
            "library_docs": len(docs), "library_stale": sum(1 for d in docs if d.embedder != embedder.name or d.store != store.name)}
