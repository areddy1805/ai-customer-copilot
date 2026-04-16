from fastapi import APIRouter
from app.core.container import get_orchestrator

orchestrator = get_orchestrator()

router = APIRouter()


@router.get("/metrics")
def get_metrics():
    return orchestrator.metrics.snapshot()
