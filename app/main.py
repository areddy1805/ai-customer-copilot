from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.include_router(chat_router, prefix="/api")
app.include_router(health_router, prefix="/api")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
