from typing import Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class ConversationState:
    """
    Represents the state of a single user request
    """

    user_query: str

    intent: Optional[str] = None

    retrieved_context: Optional[str] = None

    tool_result: Optional[Dict[str, Any]] = None

    final_response: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)
