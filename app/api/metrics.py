from fastapi import APIRouter
from app.core.container import get_orchestrator

router = APIRouter()


@router.get("/metrics")
def get_metrics():
    orch = get_orchestrator()
    data = orch.metrics.snapshot()

    requests = data.get("requests_total", 0)
    cache_hits = data.get("cache_hit", 0)
    semantic_hits = data.get("semantic_hit", 0)

    data["cache_hit_rate"] = round(cache_hits / requests, 3) if requests else 0

    data["semantic_hit_rate"] = round(semantic_hits / requests, 3) if requests else 0

    return data


@router.post("/metrics/reset")
def reset_metrics():
    orch = get_orchestrator()
    orch.metrics.reset()
    return {"status": "reset"}
