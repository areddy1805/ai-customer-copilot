import requests
import json
from typing import Optional, Generator
from app.core.config import settings


class OllamaClient:
    def __init__(self):
        self.base_url = settings.ollama_base_url

    def generate(
        self, model: str, prompt: str, stream: bool = False, timeout: int = 60
    ) -> str:

        if not isinstance(prompt, str):
            raise ValueError(f"Prompt must be string, got {type(prompt)}")

        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {"temperature": 0.2, "num_predict": 100},
        }

        try:
            response = requests.post(url, json=payload, timeout=timeout)

            if response.status_code != 200:
                raise Exception(f"Ollama error: {response.text}")

            data = response.json()
            return data.get("response", "")

        except requests.exceptions.Timeout:
            raise Exception("LLM request timed out")

        except requests.exceptions.RequestException as e:
            raise Exception(f"LLM request failed: {str(e)}")

    def generate_stream(self, model: str, prompt: str, timeout: int = 60):

        if not isinstance(prompt, str):
            raise ValueError(f"Prompt must be string, got {type(prompt)}")

        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": 0.2, "num_predict": 100},
        }

        try:
            with requests.post(
                url, json=payload, stream=True, timeout=timeout
            ) as response:

                if response.status_code != 200:
                    raise Exception(f"Ollama error: {response.text}")

                for line in response.iter_lines():
                    if line:
                        data = json.loads(line.decode("utf-8"))

                        # Extract only the token text
                        token = data.get("response", "")
                        if token:
                            yield token

                        # Stop when done
                        if data.get("done"):
                            break

        except requests.exceptions.Timeout:
            raise Exception("LLM stream timed out")

        except requests.exceptions.RequestException as e:
            raise Exception(f"LLM stream failed: {str(e)}")
