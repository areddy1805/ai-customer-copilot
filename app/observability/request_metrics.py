from dataclasses import dataclass, field
from typing import Dict, List, Any
import time


@dataclass
class RequestMetrics:
    # -------- IDENTIFICATION --------
    request_id: str
    query: str

    # -------- TIMINGS --------
    start_time: float = field(default_factory=time.time)
    total_time_ms: float = 0.0

    decomposer_ms: float = 0.0
    planner_ms: List[float] = field(default_factory=list)
    executor_ms: List[float] = field(default_factory=list)
    rag_ms: float = 0.0
    llm_ms: float = 0.0

    # -------- COUNTERS --------
    tool_calls: int = 0
    rag_calls: int = 0
    llm_calls: int = 0

    # -------- CACHE --------
    semantic_cache_hit: bool = False
    response_cache_hit: bool = False

    # -------- PROVIDERS --------
    llm_provider: str = ""
    embedding_provider: str = ""
    search_provider: str = ""

    # -------- STATUS --------
    success: bool = True
    error: str = ""

    # -------- FAILURE / RESILIENCE --------
    llm_cb_triggered: bool = False
    rag_cb_triggered: bool = False
    fallback_triggered: bool = False
    retry_count: int = 0

    # -------- TRACE --------
    tools_used: List[str] = field(default_factory=list)

    def finalize(self):
        self.total_time_ms = (time.time() - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "query": self.query,
            "total_time_ms": round(self.total_time_ms, 2),
            "decomposer_ms": self.decomposer_ms,
            "planner_ms": self.planner_ms,
            "executor_ms": self.executor_ms,
            "rag_ms": self.rag_ms,
            "llm_ms": self.llm_ms,
            "tool_calls": self.tool_calls,
            "rag_calls": self.rag_calls,
            "llm_calls": self.llm_calls,
            "semantic_cache_hit": self.semantic_cache_hit,
            "response_cache_hit": self.response_cache_hit,
            "llm_provider": self.llm_provider,
            "embedding_provider": self.embedding_provider,
            "search_provider": self.search_provider,
            "success": self.success,
            "error": self.error,
            "tools_used": self.tools_used,
            "llm_cb_triggered": self.llm_cb_triggered,
            "rag_cb_triggered": self.rag_cb_triggered,
            "fallback_triggered": self.fallback_triggered,
            "retry_count": self.retry_count,
        }
