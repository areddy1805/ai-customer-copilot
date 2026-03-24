from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.orchestrator.orchestrator import Orchestrator

router = APIRouter()
orch = Orchestrator()


def event_stream(query: str, session_id: str):

    buffer = ""

    try:
        for token in orch.run_stream(query, session_id):
            buffer += token

            # Flush on meaningful boundaries
            if token.endswith((" ", ".", ",", "!", "?", "\n")):
                yield f"data: {buffer}\n\n"
                buffer = ""

        # Flush remaining
        if buffer:
            yield f"data: {buffer}\n\n"

    except Exception as e:
        yield f"data: Error: {str(e)}\n\n"


@router.get("/stream")
def stream_chat(query: str = Query(...), session_id: str = Query("default")):
    return StreamingResponse(
        event_stream(query, session_id), media_type="text/event-stream"
    )
