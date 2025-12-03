from __future__ import annotations

import json
import os
import requests


class OpenAIClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("AI_MODEL_NAME", "gpt-4o-mini")
        self.endpoint = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")

    def available(self) -> bool:
        return bool(self.api_key)

    def score_text(self, prompt: str) -> dict:
        if not self.available():
            raise RuntimeError("OpenAI API key not configured")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        r = requests.post(self.endpoint, headers=headers, data=json.dumps(payload), timeout=30)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        return {"text": text}
