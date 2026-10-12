"""Vector stores. PgVectorStore uses PostgreSQL + pgvector (HNSW index, cosine). LocalStore is a portable fallback
(vectors in a JSON column, cosine in Python) so SQLite development still works.

Tenant isolation is enforced in ONE place (build_filter) and applied by both stores.
"""
import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings

log = logging.getLogger("superport.rag")
STATE = {"pgvector": False, "error": None}
COLS = "c.id, c.org_id, c.shipment_id, c.source_type, c.source_id, c.title, c.page, c.text, c.visibility, c.party_role"


@dataclass
class Scope:
    kind: str  # shipment | library | org
    org_id: int  # the viewer's organisation (library / org scopes) or the shipment owner's organisation
    shipment_id: int | None = None
    viewer: str = "owner"  # owner | partner
    party_role: str | None = None


def build_filter(scope: Scope) -> tuple[str, dict]:
    if scope.kind == "shipment":
        if scope.viewer == "owner":
            return "(c.shipment_id = :sid AND c.org_id = :org) OR (c.shipment_id IS NULL AND c.org_id = :org)", {"sid": scope.shipment_id, "org": scope.org_id}
        return "c.shipment_id = :sid AND c.org_id = :org AND (c.visibility = 'all' OR c.party_role = :role)", {"sid": scope.shipment_id, "org": scope.org_id, "role": scope.party_role or "-"}
    if scope.kind == "library":
        return "c.shipment_id IS NULL AND c.org_id = :org", {"org": scope.org_id}
    return "c.org_id = :org", {"org": scope.org_id}  # org: everything this organisation owns


def _lit(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


class VectorStore:
    name = "store"

    def add(self, db: Session, chunks: list[dict], vectors: list[list[float]], embedder: str) -> None:
        raise NotImplementedError

    def search(self, db: Session, scope: Scope, vec: list[float], embedder: str, k: int) -> list[dict]:
        raise NotImplementedError

    def delete(self, db: Session, *, shipment_id: int | None = None, source_type: str | None = None, source_id: int | None = None, org_id: int | None = None) -> int:
        clauses, params = [], {}
        if shipment_id is not None:
            clauses.append("shipment_id = :sid"), params.update(sid=shipment_id)
        if source_type:
            clauses.append("source_type = :st"), params.update(st=source_type)
        if source_id is not None:
            clauses.append("source_id = :src"), params.update(src=source_id)
        if org_id is not None:
            clauses.append("org_id = :org"), params.update(org=org_id)
        if not clauses:
            raise ValueError("Refusing to delete every chunk.")
        return db.execute(text("DELETE FROM rag_chunks WHERE " + " AND ".join(clauses)), params).rowcount  # rag_vectors rows cascade

    def count(self, db: Session, org_id: int) -> int:
        return db.execute(text("SELECT COUNT(*) FROM rag_chunks WHERE org_id = :o"), {"o": org_id}).scalar() or 0

    def _insert_chunks(self, db: Session, chunks: list[dict], embedder: str, with_vectors: list[list[float]] | None) -> list[int]:
        from app.models import RagChunk

        rows = []
        for i, c in enumerate(chunks):
            rows.append(RagChunk(org_id=c["org_id"], shipment_id=c.get("shipment_id"), source_type=c["source_type"], source_id=c.get("source_id"), title=c.get("title", "")[:300], page=c.get("page"), text=c["text"],
                                 visibility=c.get("visibility", "owner"), party_role=c.get("party_role", ""), embedder=embedder, embedding=with_vectors[i] if with_vectors else None))
        db.add_all(rows)
        db.flush()
        return [r.id for r in rows]


class LocalStore(VectorStore):
    name = "local"

    def add(self, db, chunks, vectors, embedder):
        self._insert_chunks(db, chunks, embedder, vectors)

    def search(self, db, scope, vec, embedder, k):
        where, params = build_filter(scope)
        rows = db.execute(text(f"SELECT {COLS}, c.embedding FROM rag_chunks c WHERE c.embedder = :emb AND ({where})"), {**params, "emb": embedder}).mappings().all()
        import json

        scored = []
        for r in rows:
            e = r["embedding"]
            e = json.loads(e) if isinstance(e, str) else e
            if not e or len(e) != len(vec):
                continue
            scored.append({**{c: r[c] for c in r.keys() if c != "embedding"}, "score": sum(a * b for a, b in zip(vec, e))})
        scored.sort(key=lambda h: -h["score"])
        return scored[:k]


class PgVectorStore(VectorStore):
    name = "pgvector"

    def add(self, db, chunks, vectors, embedder):
        ids = self._insert_chunks(db, chunks, embedder, None)
        db.execute(text("INSERT INTO rag_vectors (chunk_id, embedding) VALUES (:id, CAST(:v AS vector))"), [{"id": i, "v": _lit(v)} for i, v in zip(ids, vectors)])

    @staticmethod
    def search_sql(scope: Scope) -> tuple[str, dict]:
        where, params = build_filter(scope)
        return (f"SELECT {COLS}, 1 - (v.embedding <=> CAST(:q AS vector)) AS score FROM rag_vectors v JOIN rag_chunks c ON c.id = v.chunk_id "
                f"WHERE c.embedder = :emb AND ({where}) ORDER BY v.embedding <=> CAST(:q AS vector) LIMIT :k"), params

    def search(self, db, scope, vec, embedder, k):
        sql, params = self.search_sql(scope)
        rows = db.execute(text(sql), {**params, "q": _lit(vec), "emb": embedder, "k": k}).mappings().all()
        return [dict(r) for r in rows]


def setup_pgvector(engine, dim: int) -> tuple[bool, str | None]:
    if engine.dialect.name != "postgresql":
        return False, "Not PostgreSQL"
    try:
        with engine.begin() as c:
            c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            c.execute(text(f"CREATE TABLE IF NOT EXISTS rag_vectors (chunk_id integer PRIMARY KEY REFERENCES rag_chunks(id) ON DELETE CASCADE, embedding vector({int(dim)}))"))
            c.execute(text("CREATE INDEX IF NOT EXISTS rag_vectors_hnsw ON rag_vectors USING hnsw (embedding vector_cosine_ops)"))
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc).splitlines()[0][:200]


def init_vector_store(engine) -> None:
    settings = get_settings()
    if settings.vector_store == "local":
        STATE.update(pgvector=False, error=None)
        return
    ok, err = setup_pgvector(engine, settings.embedding_dim)
    STATE.update(pgvector=ok, error=err if (settings.vector_store == "pgvector" or engine.dialect.name == "postgresql") else None)
    if not ok and settings.vector_store == "pgvector":
        log.warning("pgvector unavailable, using the local store: %s", err)


def get_store() -> VectorStore:
    return PgVectorStore() if (STATE["pgvector"] and get_settings().vector_store != "local") else LocalStore()
