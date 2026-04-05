from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.core.config import settings


app = FastAPI()


@app.on_event("startup")
async def startup_checks():
    # =========================
    # CONFIG VISIBILITY
    # =========================
    print(f"[CONFIG] LLM_PROVIDER={settings.LLM_PROVIDER}")
    print(f"[CONFIG] EMBEDDING_PROVIDER={settings.EMBEDDING_PROVIDER}")

    # =========================
    # AZURE VALIDATION (FAIL FAST)
    # =========================
    if settings.LLM_PROVIDER == "azure":
        assert settings.AZURE_OPENAI_API_KEY, "Missing AZURE_OPENAI_API_KEY"
        assert settings.AZURE_OPENAI_ENDPOINT, "Missing AZURE_OPENAI_ENDPOINT"
        assert settings.AZURE_OPENAI_DEPLOYMENT, "Missing AZURE_OPENAI_DEPLOYMENT"

    if settings.EMBEDDING_PROVIDER == "azure":
        assert settings.AZURE_OPENAI_API_KEY, "Missing AZURE_OPENAI_API_KEY"
        assert settings.AZURE_OPENAI_ENDPOINT, "Missing AZURE_OPENAI_ENDPOINT"
        assert settings.AZURE_EMBEDDING_DEPLOYMENT, "Missing AZURE_EMBEDDING_DEPLOYMENT"

    # =========================
    # MODE VISIBILITY
    # =========================
    if settings.LLM_PROVIDER == "local" and settings.EMBEDDING_PROVIDER == "azure":
        print("[INFO] Hybrid mode: Local LLM + Azure Embeddings")

    elif settings.LLM_PROVIDER == "azure" and settings.EMBEDDING_PROVIDER == "local":
        print("[INFO] Hybrid mode: Azure LLM + Local Embeddings")

    elif settings.LLM_PROVIDER == "azure" and settings.EMBEDDING_PROVIDER == "azure":
        print("[INFO] Full Azure mode")

    else:
        print("[INFO] Full Local mode")

    # =========================
    # FINAL CONFIRMATION
    # =========================
    print("[SYSTEM] Providers initialized successfully")


# =========================
# ROUTES
# =========================
app.include_router(chat_router, prefix="/api")
app.include_router(health_router, prefix="/api")


# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
