from app.llm.models import TaskType


class LLMConfig:
    def __init__(self, temperature: float, max_tokens: int):
        self.temperature = temperature
        self.max_tokens = max_tokens


LLM_CONFIG_MAP = {
    TaskType.CLASSIFICATION: LLMConfig(temperature=0.0, max_tokens=200),
    TaskType.RAG: LLMConfig(temperature=0.2, max_tokens=600),
    TaskType.GENERAL: LLMConfig(temperature=0.5, max_tokens=500),
    TaskType.STRUCTURED: LLMConfig(temperature=0.0, max_tokens=400),
    TaskType.TOOL_RESPONSE: LLMConfig(temperature=0.3, max_tokens=300),
}
