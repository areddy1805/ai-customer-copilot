from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class Step(BaseModel):
    step_id: int
    action: str  # "tool" | "rag" | "respond"
    tool_name: Optional[str] = None
    input: Dict[str, Any] = {}
    depends_on: List[int] = []
    on_failure: Optional[str] = "fail"  # retry | skip | fallback


class Plan(BaseModel):
    goal: str
    steps: List[Step]
