from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # =========================
    # APP
    # =========================
    APP_ENV: str = "local"

    # =========================
    # PROVIDERS
    # =========================
    LLM_PROVIDER: str = "local"
    EMBEDDING_PROVIDER: str = "local"
    SEARCH_PROVIDER: str = "local"

    # =========================
    # SECRET PROVIDER SWITCH
    # =========================
    SECRET_PROVIDER: str = "env"  # env | keyvault

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
    # OLLAMA (LOCAL LLM)
    # =========================
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_TIMEOUT: int = 60

    # =========================
    # AZURE NON-SECRET CONFIG
    # =========================
    AZURE_OPENAI_API_VERSION: str = "2024-12-01-preview"
    AZURE_EMBEDDING_API_VERSION: str = "2024-12-01-preview"

    # =========================
    # KEY VAULT (NON-SECRET)
    # =========================
    AZURE_KEY_VAULT_URL: str = ""

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

    @field_validator("SEARCH_PROVIDER")
    def validate_search_provider(cls, v):
        if v not in ["local", "azure"]:
            raise ValueError("SEARCH_PROVIDER must be 'local' or 'azure'")
        return v

    @field_validator("SECRET_PROVIDER")
    def validate_secret_provider(cls, v):
        if v not in ["env", "keyvault"]:
            raise ValueError("SECRET_PROVIDER must be 'env' or 'keyvault'")
        return v


settings = Settings()
