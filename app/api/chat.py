import time
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.container import get_orchestrator

router = APIRouter()
orch = get_orchestrator()


# -------- STREAMING --------
async def event_stream(query: str, session_id: str):
    try:
        async for chunk in orch.run_stream(query, session_id):
            yield f"data: {chunk}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        yield f"data: Error: {str(e)}\n\n"
        yield "data: [DONE]\n\n"


@router.get("/stream")
async def stream_chat(query: str = Query(...), session_id: str = Query("default")):
    return StreamingResponse(
        event_stream(query, session_id),
        media_type="text/event-stream",
    )


# -------- NORMAL CHAT (TRACE ALWAYS EXPOSED) --------
@router.post("/chat")
async def chat(payload: dict):
    query = payload.get("query")
    session_id = payload.get("session_id", "default")

    state = await orch.run(query, session_id)

    return {
        "response": state.final_response,
        "details": state.metadata.get("details"),
        "intent": state.intent,
        "route": state.metadata.get("route"),
        "plans": state.metadata.get("plans"),
        "trace_id": state.metadata.get("trace_id"),
        "trace": state.metadata.get("trace", {}),
        "metrics": state.metadata.get("metrics", {}),
    }


# -------- METRICS --------
@router.get("/metrics")
def metrics():
    return orch.metrics.snapshot()
