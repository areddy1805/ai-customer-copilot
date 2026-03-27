import time
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.container import orchestrator as orch

router = APIRouter()


# -------- STREAMING --------
def event_stream(query: str, session_id: str):
    try:
        for chunk in orch.run_stream(query, session_id):
            yield f"data: {chunk}\n\n"
            time.sleep(0.05)  # simulate streaming
    except Exception as e:
        yield f"data: Error: {str(e)}\n\n"


@router.get("/stream")
def stream_chat(query: str = Query(...), session_id: str = Query("default")):
    return StreamingResponse(
        event_stream(query, session_id), media_type="text/event-stream"
    )


# -------- NORMAL CHAT (WITH DEBUG) --------
@router.get("/chat")
def chat(
    query: str = Query(...),
    session_id: str = Query("default"),
    debug: bool = Query(False),
):
    state = orch.run(query, session_id)

    if not debug:
        return {"response": state.final_response}

    return {
        "response": state.final_response,
        "intent": state.intent,
        "route": state.metadata.get("route"),
        "plans": state.metadata.get("plans"),
        "trace_id": state.metadata.get("trace_id"),
    }


# -------- METRICS --------
@router.get("/metrics")
def metrics():
    return orch.metrics.snapshot()
