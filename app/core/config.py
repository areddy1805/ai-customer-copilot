from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # -------- CORE --------
    app_env: str = "dev"

    # -------- REDIS --------
    redis_host: str = "localhost"
    redis_port: int = 6379

    # -------- POSTGRES --------
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = ""
    postgres_user: str = ""
    postgres_password: str = ""

    # -------- LLM --------
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout: int = 60

    llm_provider: str = "local"  # local | azure

    # -------- EMBEDDINGS --------
    embedding_provider: str = "local"

    # -------- SEARCH --------
    search_provider: str = "local"

    # -------- AZURE --------
    azure_openai_api_version: str = ""
    azure_embedding_api_version: str = ""

    # -------- SECRETS --------
    secret_provider: str = "local"
    azure_key_vault_url: str = ""

    # -------- AGENT --------
    agent_enabled: bool = True

    # -------- CONFIG --------
    model_config = SettingsConfigDict(env_file=".env", extra="forbid")


settings = Settings()
