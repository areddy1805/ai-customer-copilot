import requests
import json
from app.core.config import settings


class OllamaClient:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL

    async def generate(
        self,
        prompt: str,
        model: str,
        temperature: float = 0,
        max_tokens: int = 200,
        timeout: int = 60,
    ) -> str:

        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        response = requests.post(url, json=payload, timeout=timeout)

        if response.status_code != 200:
            raise Exception(f"Ollama error: {response.text}")

        return response.json().get("response", "").strip()

    async def stream(
        self,
        prompt: str,
        model: str,
        temperature: float = 0,
        max_tokens: int = 200,
        timeout: int = 60,
    ):
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        with requests.post(url, json=payload, stream=True, timeout=timeout) as response:

            if response.status_code != 200:
                raise Exception(f"Ollama error: {response.text}")

            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    data = json.loads(line.decode("utf-8"))
                except:
                    continue

                token = data.get("response", "")
                if token:
                    yield token

                if data.get("done"):
                    break
