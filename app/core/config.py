from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # =========================
    # APP
    # =========================
    APP_ENV: str = "local"

    # =========================
    # REDIS
    # =========================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # =========================
    # POSTGRES
    # =========================
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "copilot"
    POSTGRES_USER: str = "admin"
    POSTGRES_PASSWORD: str = "admin"

    # =========================
    # PROVIDERS
    # =========================
    LLM_PROVIDER: str = "local"
    EMBEDDING_PROVIDER: str = "local"

    # =========================
    # OLLAMA (LOCAL LLM)
    # =========================
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_TIMEOUT: int = 60

    # =========================
    # AZURE OPENAI (LLM)
    # =========================
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-12-01-preview"
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o-mini"

    # =========================
    # AZURE OPENAI (EMBEDDINGS)
    # =========================
    AZURE_EMBEDDING_API_VERSION: str = "2024-12-01-preview"
    AZURE_EMBEDDING_DEPLOYMENT: str = "text-embedding-3-small"

    # =========================
    # VALIDATION
    # =========================
    @field_validator("LLM_PROVIDER")
    def validate_llm_provider(cls, v):
        if v not in ["local", "azure"]:
            raise ValueError("LLM_PROVIDER must be 'local' or 'azure'")
        return v

    @field_validator("EMBEDDING_PROVIDER")
    def validate_embedding_provider(cls, v):
        if v not in ["local", "azure"]:
            raise ValueError("EMBEDDING_PROVIDER must be 'local' or 'azure'")
        return v


settings = Settings()
