from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SuperPort API"
    environment: str = "development"  # production refuses to boot with unsafe defaults
    app_url: str = "http://localhost:3000"  # used in email links
    resend_api_key: str | None = None
    email_from: str | None = None  # for example SuperPort <no-reply@yourdomain.com>
    database_url: str = "sqlite:///./superport.db"
    secret_key: str = "dev-only-change-me-use-a-long-random-secret"
    access_token_minutes: int = 60 * 12
    demo_mode: bool = True
    seed_demo_data: bool = True

    # AI layer: "demo" = deterministic mock AI, "live" = use configured providers
    ai_mode: str = "demo"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5-5"

    # --- v2 intelligence layer (Gemini + SerpApi) ---
    # off = v1 behaviour, fixtures = sample SerpApi data (no keys), live = real APIs
    intelligence_mode: str = "off"
    gemini_api_key: str | None = None
    gemini_model_fast: str | None = None  # empty = auto-detect from your key
    gemini_model_pro: str | None = None
    serpapi_api_key: str | None = None
    serpapi_budget_per_shipment: int = 20
    serpapi_daily_cap: int = 80  # hard wallet guard across the whole app
    gemini_budget_per_shipment: int = 20
    cache_ttl_hours: int = 72
    allow_synthetic_extraction: bool | None = None  # None = auto (off in live mode)
    collect_feedback: bool = True
    # --- RAG / vector search / copilot ---
    embedding_dim: int = 768  # changing it later requires dropping the rag_vectors table
    gemini_embedding_model: str | None = None  # empty = auto-detect from your key
    vector_store: str = "auto"  # auto | local | pgvector
    rag_chunk_chars: int = 900
    rag_overlap_chars: int = 150
    rag_top_k: int = 6
    copilot_model_kind: str = "fast"  # fast | pro
    tracking_provider: str = "sample"  # sample | none (add real providers in app/tracking/providers.py)
    # --- Trade Signal Radar ---
    radar_interval_minutes: int = 0  # 0 = scan only when someone clicks Scan now
    radar_max_queries: int = 8
    radar_window: str = "w"  # Google news recency: h hour, d day, w week, m month

    upload_dir: str = "./uploads"
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
