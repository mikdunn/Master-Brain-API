from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


@dataclass(frozen=True, slots=True)
class PerplexityError(Exception):
    message: str
    status_code: int | None = None
    body_excerpt: str | None = None

    def __str__(self) -> str:  # pragma: no cover
        extra = []
        if self.status_code is not None:
            extra.append(f"status={self.status_code}")
        if self.body_excerpt:
            extra.append(f"body={self.body_excerpt}")
        suffix = f" ({', '.join(extra)})" if extra else ""
        return f"{self.message}{suffix}"


def perplexity_chat_completions(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout_seconds: int = 30,
) -> str:
    """Call the Perplexity API chat completions endpoint.

    This uses a common OpenAI-compatible schema (`/chat/completions`).
    """

    if not api_key or not api_key.strip():
        raise PerplexityError("PERPLEXITY_API_KEY is not set")

    url = (base_url.rstrip("/") + "/chat/completions").strip()

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if temperature is not None:
        payload["temperature"] = float(temperature)
    if max_tokens is not None:
        payload["max_tokens"] = int(max_tokens)

    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib_request.urlopen(req, timeout=timeout_seconds) as resp:
            status = int(getattr(resp, "status", 200))
            body_text = resp.read().decode("utf-8", errors="replace")
    except urllib_error.HTTPError as exc:
        status = int(exc.code)
        body_text = exc.read().decode("utf-8", errors="replace")
        raise PerplexityError(
            "Perplexity API returned an error",
            status_code=status,
            body_excerpt=body_text[:600],
        ) from exc
    except urllib_error.URLError as exc:
        raise PerplexityError(
            f"Perplexity API request failed: {type(exc).__name__}",
        ) from exc

    if status < 200 or status >= 300:
        raise PerplexityError(
            "Perplexity API returned a non-2xx response",
            status_code=status,
            body_excerpt=body_text[:600],
        )

    try:
        data_json: Any = json.loads(body_text)
    except Exception as exc:
        raise PerplexityError(
            "Perplexity API response was not valid JSON",
            status_code=status,
            body_excerpt=body_text[:600],
        ) from exc

    # OpenAI-style: { choices: [ { message: { content: "..." } } ] }
    try:
        choices = data_json.get("choices") or []
        if choices:
            msg = (choices[0] or {}).get("message") or {}
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    except Exception:
        pass

    # Fallback: return a readable excerpt.
    return json.dumps(data_json, ensure_ascii=False)[:4000]
