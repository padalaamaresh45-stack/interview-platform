from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5433/interview_platform"
    session_ttl_hours: int = 8
    cookie_secure: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
