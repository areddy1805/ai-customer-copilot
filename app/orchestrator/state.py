from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class ConversationState:
    user_query: str

    intent: Optional[str] = None
    retrieved_context: Optional[str] = None
    tool_result: Optional[Dict[str, Any]] = None
    final_response: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    trace: Dict[str, Any] = field(
        default_factory=lambda: {
            "decomposer_ms": 0,
            "planner_ms": [],
            "executor_ms": [],
            "cache": {
                "semantic_hit": False,
                "cache_hit": False,
                "executed": False,
            },
            "tools": [],
        }
    )
