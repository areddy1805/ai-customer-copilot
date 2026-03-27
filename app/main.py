from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.health import router as health_router

app = FastAPI()

app.include_router(chat_router, prefix="/api")
app.include_router(health_router, prefix="/api")
