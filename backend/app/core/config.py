from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret_key: str = "development-secret-change-before-production"
    database_url: str = "postgresql+psycopg://crm:crm@localhost:5432/crm_fidelizacion"
    initial_admin_email: str | None = None
    initial_admin_password: str | None = None
    cors_origins: str = "http://localhost:5173"
    access_token_minutes: int = 60
    reset_token_minutes: int = 30
    import_max_file_size: int = 5 * 1024 * 1024
    import_max_rows: int = 1000
    alert_active_window_days: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
