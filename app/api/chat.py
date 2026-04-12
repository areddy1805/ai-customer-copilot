import time
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from app.cache.response_cache import ResponseCache

from app.core.container import orchestrator as orch

router = APIRouter()
response_cache = ResponseCache()


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
    # -------- CACHE HIT (ONLY FOR NON-DEBUG) --------
    if not debug:
        cached = response_cache.get(query)
        if cached:
            return {"response": cached}

    # -------- NORMAL FLOW --------
    state = orch.run(query, session_id)

    final_response = state.final_response

    # -------- CACHE STORE --------
    if not debug:
        response_cache.set(query, final_response)

    if not debug:
        return {"response": final_response}

    return {
        "response": final_response,
        "intent": state.intent,
        "route": state.metadata.get("route"),
        "plans": state.metadata.get("plans"),
        "trace_id": state.metadata.get("trace_id"),
    }


# -------- METRICS --------
@router.get("/metrics")
def metrics():
    return orch.metrics.snapshot()
