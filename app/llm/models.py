from enum import Enum


class TaskType(str, Enum):
    GENERAL = "general"
    RAG = "rag"
    STRUCTURED = "structured"
    TOOL = "tool"


MODEL_MAPPING = {
    TaskType.GENERAL: "llama3.2:3b",
    TaskType.RAG: "mistral:7b-instruct",
    TaskType.STRUCTURED: "qwen2.5:3b",
    TaskType.TOOL: "phi3:mini",
}


def get_model_for_task(task: str) -> str:
    try:
        return MODEL_MAPPING[TaskType(task)]
    except Exception:
        return "phi3:mini"
