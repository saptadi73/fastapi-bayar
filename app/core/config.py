from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Payment Portal"
    environment: str = "development"
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")
    api_prefix: str = "/api/v1"
    public_base_url: str = "http://localhost:8000"
    log_level: str = "INFO"
    timezone: str = "UTC"
    database_url: str = "postgresql+asyncpg://openpg:openpgpwd@127.0.0.1:5432/bayar"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_echo: bool = False
    auto_create_tables: bool = False
    auth_enabled: bool = True
    admin_enabled: bool = False
    admin_session_ttl_seconds: int = Field(default=28800, ge=300, le=86400)
    admin_idle_ttl_seconds: int = Field(default=1800, ge=60, le=86400)
    admin_login_limit: int = Field(default=10, ge=1, le=100)
    admin_login_window_seconds: int = Field(default=300, ge=60, le=3600)
    jwt_secret: str = ""
    jwt_issuer: str = "payment-portal"
    jwt_audience: str = "payment-client-api"
    access_token_ttl_seconds: int = Field(default=600, ge=60, le=900)
    checkout_ttl_seconds: int = Field(default=1800, ge=60, le=86400)
    hmac_clock_skew_seconds: int = 300
    nonce_ttl_seconds: int = 600
    idempotency_ttl_hours: int = 48
    client_api_secret: str = "change-me-local-only"
    doku_enabled: bool = False
    doku_environment: str = "SANDBOX"
    doku_sandbox_base_url: str = "https://api-sandbox.doku.com"
    doku_production_base_url: str = "https://api.doku.com"
    doku_client_id: str = ""
    doku_secret_key: str = ""
    doku_public_key: str = ""
    midtrans_enabled: bool = False
    midtrans_environment: str = "SANDBOX"
    midtrans_sandbox_base_url: str = "https://app.sandbox.midtrans.com"
    midtrans_production_base_url: str = "https://app.midtrans.com"
    midtrans_server_key: str = ""
    midtrans_client_key: str = ""
    midtrans_core_sandbox_base_url: str = "https://api.sandbox.midtrans.com"
    midtrans_core_production_base_url: str = "https://api.midtrans.com"
    gateway_timeout_seconds: int = Field(default=15, gt=0, le=60)
    callback_timeout_seconds: int = 10
    callback_max_attempts: int = 7
    worker_callback_interval_seconds: float = Field(default=5, ge=1, le=3600)
    worker_cleanup_interval_seconds: float = Field(default=300, ge=1, le=86400)
    worker_callback_batch_size: int = Field(default=20, ge=1, le=100)
    worker_cleanup_batch_size: int = Field(default=500, ge=1, le=10000)
    worker_reconciliation_interval_seconds: float = Field(default=60, ge=1, le=3600)
    worker_reconciliation_batch_size: int = Field(default=10, ge=1, le=100)
    worker_refund_interval_seconds: float = Field(default=30, ge=1, le=3600)
    worker_refund_batch_size: int = Field(default=10, ge=1, le=100)
    redis_url: str = "redis://127.0.0.1:6379/2"
    sentry_dsn: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

    @field_validator("api_prefix")
    @classmethod
    def normalize_prefix(cls, value: str) -> str:
        return "/" + value.strip("/")

    def validate_production(self) -> None:
        if self.hmac_clock_skew_seconds <= 0 or self.nonce_ttl_seconds < 2 * self.hmac_clock_skew_seconds:
            raise ValueError("NONCE_TTL_SECONDS harus minimal dua kali HMAC_CLOCK_SKEW_SECONDS positif")
        if self.environment.lower() == "production":
            if self.admin_enabled:
                raise ValueError("Admin masih development-only sampai MFA/security review selesai")
            if len(self.jwt_secret) < 48 or self.jwt_secret.startswith("REPLACE"):
                raise ValueError("JWT_SECRET production wajib secret acak minimal 48 karakter")
            if not self.auth_enabled:
                raise ValueError("AUTH_ENABLED wajib true pada production")
            if self.auto_create_tables or self.debug or self.db_echo:
                raise ValueError("Production wajib menonaktifkan AUTO_CREATE_TABLES, APP_DEBUG, dan DB_ECHO")
            if not self.public_base_url.startswith("https://"):
                raise ValueError("PUBLIC_BASE_URL production wajib HTTPS")
        if self.environment.lower() == "production" and self.client_api_secret == "change-me-local-only":
            raise ValueError("CLIENT_API_SECRET wajib diganti pada production")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings
