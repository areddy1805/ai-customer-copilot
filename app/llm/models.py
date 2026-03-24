from enum import Enum


class TaskType(str, Enum):
    CLASSIFICATION = "classification"
    GENERAL = "general"
    RAG = "rag"
    STRUCTURED = "structured"
    TOOL_RESPONSE = "tool_response"


MODEL_MAPPING = {
    TaskType.GENERAL: "llama3.2:3b",
    TaskType.RAG: "mistral:7b-instruct",
    TaskType.STRUCTURED: "qwen2.5:3b",
    TaskType.TOOL_RESPONSE: "phi3:mini",
}


def get_model_for_task(task: TaskType) -> str:
    """
    Returns the appropriate model for a given task
    """
    return MODEL_MAPPING.get(task, "phi3:mini")
