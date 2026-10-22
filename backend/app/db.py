from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

settings = get_settings()

_kwargs: dict = {}
if settings.database_url.startswith("sqlite"):
    _kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    if ":memory:" in settings.database_url:
        _kwargs["poolclass"] = StaticPool

engine = create_engine(settings.database_url, pool_pre_ping=True, **_kwargs)

if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
        except Exception:
            pass
        finally:
            cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema() -> None:
    """Create new tables and add columns introduced after v1 (no Alembic yet)."""
    from sqlalchemy import inspect, text

    Base.metadata.create_all(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("shipments")}
    with engine.begin() as conn:
        if "is_demo" not in cols:
            seeded = ",".join(f"'SP-2026-{i:04d}'" for i in range(1, 8))
            conn.execute(text("ALTER TABLE shipments ADD COLUMN is_demo BOOLEAN DEFAULT FALSE"))
            conn.execute(text(f"UPDATE shipments SET is_demo = TRUE WHERE reference IN ({seeded})"))
        if "intel" not in cols:
            conn.execute(text("ALTER TABLE shipments ADD COLUMN intel JSON"))
        if "org_id" not in cols:
            conn.execute(text("ALTER TABLE shipments ADD COLUMN org_id INTEGER"))
        if "tracking" not in cols:
            conn.execute(text("ALTER TABLE shipments ADD COLUMN tracking JSON"))
        if "carriers" not in {c["name"] for c in inspect(engine).get_columns("signals")}:
            conn.execute(text("ALTER TABLE signals ADD COLUMN carriers JSON"))
        ucols = {c["name"] for c in inspect(engine).get_columns("users")}
        for name, ddl in (("org_id", "INTEGER"), ("org_role", "VARCHAR(10) DEFAULT 'admin'"), ("email_verified", "BOOLEAN DEFAULT FALSE")):
            if name not in ucols:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {ddl}"))
