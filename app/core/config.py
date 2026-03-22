from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str

    redis_host: str
    redis_port: int

    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str

    ollama_base_url: str

    class Config:
        env_file = ".env"


settings = Settings()