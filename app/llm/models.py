from enum import Enum


class TaskType(str, Enum):
    CLASSIFICATION = "classification"
    GENERAL = "general"
    RAG = "rag"
    STRUCTURED = "structured"


MODEL_MAPPING = {
    TaskType.CLASSIFICATION: "phi3:mini",
    TaskType.GENERAL: "llama3.2:3b",
    TaskType.RAG: "mistral:7b-instruct",
    TaskType.STRUCTURED: "qwen2.5:3b",
}


def get_model_for_task(task: TaskType) -> str:
    """
    Returns the appropriate model for a given task
    """
    if task not in MODEL_MAPPING:
        raise ValueError(f"No medel defined for task: {task}")

    return MODEL_MAPPING[task]
