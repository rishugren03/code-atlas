from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ─── App ────────────────────────────────────────────────
    APP_NAME: str = "CodeAtlas"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # ─── Database (PostgreSQL) ──────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://codeatlas:codeatlas_secret@localhost:5433/codeatlas"
    DATABASE_URL_SYNC: str = "postgresql://codeatlas:codeatlas_secret@localhost:5433/codeatlas"

    # ─── Redis ──────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ─── Neo4j ──────────────────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "codeatlas_secret"

    # ─── CORS ───────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000"

    # ─── GitHub ─────────────────────────────────────────────
    GITHUB_TOKEN: str = ""

    # ─── Repository Processing ──────────────────────────────
    CLONE_DIR: str = "cloned_repos"
    MAX_REPO_SIZE_MB: int = 2048  # 2GB limit
    MAX_COMMITS: int = 500_000

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


settings = Settings()
