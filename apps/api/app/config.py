from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://cadence:cadence@localhost:5432/cadence"
    secret_key: str = "dev-secret-change-me"
    # Fernet key for OAuth tokens at rest. Empty = derived from secret_key.
    encryption_key: str = ""

    api_base_url: str = "http://localhost:8000"
    web_base_url: str = "http://localhost:5173"
    cookie_domain: str = ""
    cookie_secure: bool = False
    # "lax" in production. "none" (with cookie_secure) when the app runs inside an iframe.
    cookie_samesite: str = "lax"
    allow_signup: bool = True

    # "local" writes to disk (dev only: platforms cannot fetch localhost URLs).
    storage_backend: str = "local"
    local_media_dir: str = "./.media"
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_public_base_url: str = ""
    max_image_bytes: int = 30 * 1024 * 1024
    max_video_bytes: int = 1024 * 1024 * 1024

    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_graph_version: str = "v24.0"
    # Instagram uses its own app id/secret ("API setup with Instagram login").
    instagram_app_id: str = ""
    instagram_app_secret: str = ""

    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    # Until the TikTok app passes its audit, only SELF_ONLY is accepted.
    tiktok_privacy_level: str = "SELF_ONLY"

    worker_poll_seconds: float = 10.0
    publish_max_attempts: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
