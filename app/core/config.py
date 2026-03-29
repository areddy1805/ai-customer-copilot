from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")  # ← CRITICAL FIX

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
    # PROVIDER SWITCH
    # =========================
    LLM_PROVIDER: str = "local"

    # =========================
    # OLLAMA
    # =========================
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_TIMEOUT: int = 60

    # =========================
    # AZURE OPENAI
    # =========================
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o-mini"


settings = Settings()
