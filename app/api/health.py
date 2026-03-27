from fastapi import APIRouter
from app.core.container import orchestrator

router = APIRouter()


@router.get("/metrics")
def get_metrics():
    return orchestrator.metrics.snapshot()
