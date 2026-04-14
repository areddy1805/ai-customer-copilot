from fastapi import APIRouter
from app.core.container import get_orchestrator

router = APIRouter()


@router.get("/metrics")
def get_metrics():
    orch = get_orchestrator()
    return orch.metrics.snapshot()


@router.post("/metrics/reset")
def reset_metrics():
    orch = get_orchestrator()
    orch.metrics.reset()
    return {"status": "reset"}
