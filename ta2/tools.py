"""Bounded local model tools and deterministic mathematical guardrails."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from game24.validator import ValidationResult, validate_expression


class ToolFailure(RuntimeError):
    def __init__(self, tool: str, message: str, attempts: int = 1):
        super().__init__(message)
        self.tool, self.attempts = tool, attempts


def check_puzzle(numbers):
    if len(numbers) != 4 or any(type(n) is not int or not 1 <= n <= 13 for n in numbers):
        raise ValueError("TA2 requires four integer cards in the range 1..13")
    return tuple(numbers)


def verify(expression, numbers):
    check_puzzle(numbers)
    if not isinstance(expression, str) or len(expression) > 256:
        return ValidationResult(False, None, "Expression must be text of at most 256 characters")
    # Restrict input before parsing; bound both nested syntax and numeric operands.
    import ast
    import re
    if not re.fullmatch(r"[0-9+*/()\s−×÷-]+", expression):
        return ValidationResult(False, None, "Disallowed expression characters")
    if any(len(n) > 3 for n in re.findall(r"\d+", expression)):
        return ValidationResult(False, None, "Oversized numeric literal")
    try:
        tree = ast.parse(expression.replace("−", "-").replace("×", "*").replace("÷", "/"), mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 32:
            return ValidationResult(False, None, "Expression exceeds AST budget")
    except (SyntaxError, RecursionError) as exc:
        return ValidationResult(False, None, str(exc))
    return validate_expression(expression.replace("−", "-"), numbers)


@dataclass
class LocalOllama:
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:3b"
    embedding_model: str = "nomic-embed-text"
    timeout: float = 180
    retries: int = 2
    prompt_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    attempts: int = 0

    def __post_init__(self):
        from urllib.parse import urlparse
        url = urlparse(self.base_url)
        if url.scheme != "http" or url.hostname not in ("localhost", "127.0.0.1", "::1") or url.username or url.password:
            raise ValueError("Ollama URL must be a local HTTP endpoint")
        if not 0 <= self.retries <= 3 or not 0 < self.timeout <= 600:
            raise ValueError("Invalid timeout or retry budget")

    def _request(self, path, payload=None):
        self.calls += 1
        body = None if payload is None else json.dumps(payload).encode()
        for attempt in range(self.retries + 1):
            self.attempts += 1
            try:
                request = urllib.request.Request(self.base_url.rstrip("/") + path, data=body,
                                                 headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ValueError("Model response exceeds size limit")
                data = json.loads(raw)
                if not isinstance(data, dict) or data.get("error"):
                    raise ValueError("Invalid/error model response")
                return data
            except urllib.error.HTTPError as exc:
                transient = exc.code == 429 or exc.code >= 500
                error = f"HTTP {exc.code} from {path}"
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                transient, error = True, f"{type(exc).__name__} calling {path}"
            except (ValueError, json.JSONDecodeError) as exc:
                transient, error = False, str(exc)
            if not transient or attempt == self.retries:
                raise ToolFailure(path, error, attempt + 1)
            time.sleep(0.2 * (2 ** attempt))

    def ready(self, require_embeddings=True):
        data = self._request("/api/tags")
        models = data.get("models")
        if not isinstance(models, list):
            raise ToolFailure("readiness", "Invalid model list")
        names = {m.get("name") for m in models if isinstance(m, dict)}
        required = [self.model] + ([self.embedding_model] if require_embeddings else [])
        missing = [m for m in required if m not in names and m + ":latest" not in names]
        if missing:
            raise ToolFailure("readiness", "Missing local models: " + ", ".join(missing))

    def generate(self, prompt, seed=42):
        data = self._request("/api/generate", {
            "model": self.model, "prompt": prompt, "format": "json", "stream": False,
            "options": {"temperature": 0, "seed": seed, "num_predict": 700},
        })
        try:
            self.prompt_tokens += int(data.get("prompt_eval_count", 0))
            self.output_tokens += int(data.get("eval_count", 0))
            result = json.loads(data["response"])
            if not isinstance(result, dict):
                raise ValueError("Expected JSON object")
            return result
        except (KeyError, TypeError, ValueError) as exc:
            raise ToolFailure("generate", "Malformed generation response") from exc

    def embed(self, texts):
        data = self._request("/api/embed", {"model": self.embedding_model, "input": texts})
        vectors = data.get("embeddings")
        import math
        if (not isinstance(vectors, list) or len(vectors) != len(texts) or not vectors
                or any(not isinstance(v, list) or not v for v in vectors)
                or len({len(v) for v in vectors}) != 1
                or any(type(x) not in (int, float) or not math.isfinite(x) for v in vectors for x in v)):
            raise ToolFailure("embed", "Malformed embedding response")
        return vectors
