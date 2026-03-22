from app.llm.models import TaskType


def build_prompt(task: TaskType, query: str, context: str = "") -> str:
    """
    Returns a fully constructed prompt based on task type
    """

    if task == TaskType.GENERAL:
        return f"""
You are a customer support assistant for an e-commerce company.

Rules:
- Be concise and clear
- Do not invent policies
- Answer only based on general knowledge

User Query:
{query}

Answer:
""".strip()

    elif task == TaskType.CLASSIFICATION:
        return f"""
Classify the following user query into one of these categories:

- order_status
- refund_request
- cancellation
- delivery_issue
- account_update
- general

Return ONLY the category name.

Query:
{query}

Category:
""".strip()

    elif task == TaskType.RAG:
        return f"""
You are a customer support assistant for an e-commerce company.

Strict rules:
- Use ONLY the provided context
- Do NOT make up information
- If answer is not in context, say: "I don't have that information."

Context:
{context}

User Query:
{query}

Answer:
""".strip()

    else:
        raise ValueError(f"Unsupported task type: {task}")
