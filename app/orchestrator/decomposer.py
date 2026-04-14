import json
import re


class Decomposer:
    def __init__(self, llm):
        self.llm = llm

    async def decompose(self, query: str):
        prompt = f"""
You are a task decomposer.

Split the query into independent tasks.

STRICT RULES:
- Output ONLY JSON array
- Max 3 tasks
- No explanation
- Each task must be atomic and executable

Each item:
{{"query": "...", "type": "tool|rag"}}

Examples:

Input: refund policy and track ORD123
Output:
[
  {{"query":"refund policy","type":"rag"}},
  {{"query":"track ORD123","type":"tool"}}
]

Input: track ORD123
Output:
[
  {{"query":"track ORD123","type":"tool"}}
]

Input: refund ORD123 and create ticket for ORD456
Output:
[
  {{"query":"refund ORD123","type":"tool"}},
  {{"query":"create ticket for ORD456","type":"tool"}}
]

Query:
{query}
"""

        try:
            response = await self.llm.generate(prompt, temperature=0, task="structured")

            print("DECOMPOSER_RAW:", response)

            response = response.strip()

            # HARD JSON extraction (safe)
            match = re.search(r"\[[\s\S]*\]", response)
            if match:
                response = match.group(0)

            data = json.loads(response)

            if not isinstance(data, list):
                return None

            cleaned = []

            for item in data:
                if (
                    isinstance(item, dict)
                    and "query" in item
                    and "type" in item
                    and item["type"] in ["tool", "rag"]
                    and isinstance(item["query"], str)
                    and item["query"].strip()
                ):
                    cleaned.append(
                        {"query": item["query"].strip(), "type": item["type"]}
                    )

            return cleaned[:3] if cleaned else None

        except Exception as e:
            print("DECOMPOSER_ERROR:", str(e))
            return None
