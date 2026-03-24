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

    elif task == TaskType.RAG:
        return f"""
                You are a customer support assistant for an e-commerce company.

                STRICT RULES:
                - Use ONLY the provided context
                - DO NOT add any information not present in the context
                - DO NOT infer, generalize, or explain beyond the context
                - DO NOT add advice or suggestions unless explicitly present in the context
                - DO NOT mention contacting support unless explicitly stated in the context
                - If the answer is not fully contained in the context, respond exactly with:
                "I don't have that information."

                Context:
                {context}

                User Query:
                {query}

                Answer:
                """.strip()

    elif task == TaskType.TOOL_RESPONSE:
        return f"""
                You are a customer support assistant for an e-commerce platform.

                You are given structured tool output. Your job is to convert it into a clear, user-friendly response.

                STRICT RULES:
                - Use ONLY the information present in Tool Output
                - DO NOT add, infer, or assume any information
                - DO NOT modify, reformat, or reinterpret any values (IDs, dates, amounts)
                - DO NOT include explanations, suggestions, or extra sentences
                - Output must be a direct, minimal natural-language rendering of the Tool Output
                - Maximum 2 sentences

                User Query:
                {query}

                Tool Output:
                {context}

                Answer:
                """.strip()

    else:
        raise ValueError(f"Unsupported task type: {task}")
