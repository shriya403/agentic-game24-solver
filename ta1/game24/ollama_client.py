from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResponse:
    text: str
    wall_time_sec: float
    prompt_tokens: int
    output_tokens: int
    total_duration_sec: float


class OllamaUnavailable(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, model: str = "qwen2.5:3b", base_url: str = "http://localhost:11434", timeout: int = 180):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    def generate(self, prompt: str, seed: int = 42, num_predict: int = 700) -> LLMResponse:
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0, "seed": seed, "num_predict": num_predict},
        }).encode()
        request = urllib.request.Request(
            f"{self.base_url}/api/generate", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OllamaUnavailable(f"Cannot reach Ollama at {self.base_url}: {exc}") from exc
        return LLMResponse(
            text=data.get("response", ""),
            wall_time_sec=time.perf_counter() - started,
            prompt_tokens=int(data.get("prompt_eval_count", 0)),
            output_tokens=int(data.get("eval_count", 0)),
            total_duration_sec=float(data.get("total_duration", 0)) / 1e9,
        )

