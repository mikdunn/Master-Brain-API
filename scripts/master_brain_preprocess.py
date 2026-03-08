<<<<<<< HEAD
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

DEFAULT_BRIDGE_URL = "http://127.0.0.1:8787"
DEFAULT_ENDPOINT = "/v1/copilot-context"
DEFAULT_API_KEY = "master-brain-bridge-local"


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_question(args: argparse.Namespace) -> str:
    if args.question:
        return str(args.question).strip()
    if args.stdin or not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return ""


def _build_payload(args: argparse.Namespace, question: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "question": question,
        "k": args.k,
    }
    if args.project_root:
        payload["project_root"] = args.project_root
    if args.index_path:
        payload["index_path"] = args.index_path
    if args.cloud_rerank:
        payload["cloud_rerank"] = True
    return payload


def _post_json(url: str, payload: dict[str, Any], api_key: str, timeout: int) -> dict[str, Any]:
    req = urllib_request.Request(
        url=url,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
        },
        data=json.dumps(payload).encode("utf-8"),
    )

    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Bridge HTTP {exc.code}: {detail}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Bridge connection error: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Bridge returned non-JSON response: {raw[:500]}") from exc


def _render_output(endpoint: str, response: dict[str, Any], original_question: str) -> str:
    normalized_endpoint = endpoint.rstrip("/")

    if normalized_endpoint.endswith("/v1/copilot-context"):
        prompt = str(response.get("prompt", "")).strip()
        if prompt:
            return prompt

    if normalized_endpoint.endswith("/v1/query"):
        answer = str(response.get("answer", "")).strip()
        context_items = response.get("context") or []
        context_blob = "\n\n".join(str(item) for item in context_items if str(item).strip())
        if context_blob:
            return f"{answer}\n\nGrounded context:\n{context_blob}".strip()
        return answer

    if normalized_endpoint.endswith("/v1/synthesize"):
        answer = str(response.get("answer", "")).strip()
        citations = response.get("citations") or []
        if citations:
            rendered = []
            for i, c in enumerate(citations, start=1):
                src = c.get("source", "unknown")
                page = c.get("page", "n/a")
                score = c.get("score", "n/a")
                rendered.append(f"[{i}] {src} (page={page}, score={score})")
            return f"{answer}\n\nCitations:\n" + "\n".join(rendered)
        return answer

    return json.dumps(response, indent=2)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Master Brain local preprocessor: calls Bridge API, then emits a chat-ready grounded prompt."
        )
    )
    parser.add_argument("--question", "-q", help="Question to ground.")
    parser.add_argument("--stdin", action="store_true", help="Read question from stdin.")
    parser.add_argument("--bridge-url", default=os.getenv("MASTER_BRAIN_BRIDGE_URL", DEFAULT_BRIDGE_URL))
    parser.add_argument(
        "--endpoint",
        default=os.getenv("MASTER_BRAIN_BRIDGE_ENDPOINT", DEFAULT_ENDPOINT),
        help="Bridge endpoint path or full URL (e.g., /v1/copilot-context).",
    )
    parser.add_argument("--api-key", default=os.getenv("BRIDGE_API_KEY", DEFAULT_API_KEY))
    parser.add_argument("--project-root", default=os.getenv("MASTER_BRAIN_PROJECT_ROOT", str(Path.cwd())))
    parser.add_argument("--index-path", default=os.getenv("MASTER_BRAIN_INDEX_PATH"))
    parser.add_argument("--k", type=int, default=int(os.getenv("MASTER_BRAIN_K", "6")))
    parser.add_argument("--cloud-rerank", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=int(os.getenv("MASTER_BRAIN_TIMEOUT_SECONDS", "30")))
    parser.add_argument(
        "--output",
        choices=["prompt", "json"],
        default="prompt",
        help="Output rendered prompt text or raw JSON.",
    )
    parser.add_argument(
        "--append-original-question",
        action="store_true",
        default=_truthy(os.getenv("MASTER_BRAIN_APPEND_ORIGINAL_QUESTION")),
        help="Append original question after generated prompt (optional).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    question = _read_question(args)
    if not question:
        print("No question provided. Use --question or --stdin.", file=sys.stderr)
        return 2

    endpoint = args.endpoint.strip()
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        url = endpoint
    else:
        base = args.bridge_url.rstrip("/")
        path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        url = base + path

    payload = _build_payload(args, question)

    try:
        response = _post_json(
            url=url,
            payload=payload,
            api_key=args.api_key,
            timeout=args.timeout_seconds,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.output == "json":
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0

    rendered = _render_output(endpoint=url, response=response, original_question=question)
    if args.append_original_question:
        rendered = f"{rendered}\n\nUser question:\n{question}".strip()

    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
=======
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

DEFAULT_BRIDGE_URL = "http://127.0.0.1:8787"
DEFAULT_ENDPOINT = "/v1/copilot-context"
DEFAULT_API_KEY = "master-brain-bridge-local"


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_question(args: argparse.Namespace) -> str:
    if args.question:
        return str(args.question).strip()
    if args.stdin or not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return ""


def _build_payload(args: argparse.Namespace, question: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "question": question,
        "k": args.k,
    }
    if args.project_root:
        payload["project_root"] = args.project_root
    if args.index_path:
        payload["index_path"] = args.index_path
    if args.cloud_rerank:
        payload["cloud_rerank"] = True
    return payload


def _post_json(url: str, payload: dict[str, Any], api_key: str, timeout: int) -> dict[str, Any]:
    req = urllib_request.Request(
        url=url,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
        },
        data=json.dumps(payload).encode("utf-8"),
    )

    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Bridge HTTP {exc.code}: {detail}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Bridge connection error: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Bridge returned non-JSON response: {raw[:500]}") from exc


def _render_output(endpoint: str, response: dict[str, Any], original_question: str) -> str:
    normalized_endpoint = endpoint.rstrip("/")

    if normalized_endpoint.endswith("/v1/copilot-context"):
        prompt = str(response.get("prompt", "")).strip()
        if prompt:
            return prompt

    if normalized_endpoint.endswith("/v1/query"):
        answer = str(response.get("answer", "")).strip()
        context_items = response.get("context") or []
        context_blob = "\n\n".join(str(item) for item in context_items if str(item).strip())
        if context_blob:
            return f"{answer}\n\nGrounded context:\n{context_blob}".strip()
        return answer

    if normalized_endpoint.endswith("/v1/synthesize"):
        answer = str(response.get("answer", "")).strip()
        citations = response.get("citations") or []
        if citations:
            rendered = []
            for i, c in enumerate(citations, start=1):
                src = c.get("source", "unknown")
                page = c.get("page", "n/a")
                score = c.get("score", "n/a")
                rendered.append(f"[{i}] {src} (page={page}, score={score})")
            return f"{answer}\n\nCitations:\n" + "\n".join(rendered)
        return answer

    # Unknown endpoint fallback: preserve full JSON for safety.
    return json.dumps(response, indent=2)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Master Brain local preprocessor: calls Bridge API, then emits a chat-ready grounded prompt."
        )
    )
    parser.add_argument("--question", "-q", help="Question to ground.")
    parser.add_argument("--stdin", action="store_true", help="Read question from stdin.")
    parser.add_argument("--bridge-url", default=os.getenv("MASTER_BRAIN_BRIDGE_URL", DEFAULT_BRIDGE_URL))
    parser.add_argument(
        "--endpoint",
        default=os.getenv("MASTER_BRAIN_BRIDGE_ENDPOINT", DEFAULT_ENDPOINT),
        help="Bridge endpoint path or full URL (e.g., /v1/copilot-context).",
    )
    parser.add_argument("--api-key", default=os.getenv("BRIDGE_API_KEY", DEFAULT_API_KEY))
    parser.add_argument("--project-root", default=os.getenv("MASTER_BRAIN_PROJECT_ROOT", str(Path.cwd())))
    parser.add_argument("--index-path", default=os.getenv("MASTER_BRAIN_INDEX_PATH"))
    parser.add_argument("--k", type=int, default=int(os.getenv("MASTER_BRAIN_K", "6")))
    parser.add_argument("--cloud-rerank", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=int(os.getenv("MASTER_BRAIN_TIMEOUT_SECONDS", "30")))
    parser.add_argument(
        "--output",
        choices=["prompt", "json"],
        default="prompt",
        help="Output rendered prompt text or raw JSON.",
    )
    parser.add_argument(
        "--append-original-question",
        action="store_true",
        default=_truthy(os.getenv("MASTER_BRAIN_APPEND_ORIGINAL_QUESTION")),
        help="Append original question after generated prompt (optional).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    question = _read_question(args)
    if not question:
        print("No question provided. Use --question or --stdin.", file=sys.stderr)
        return 2

    endpoint = args.endpoint.strip()
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        url = endpoint
    else:
        base = args.bridge_url.rstrip("/")
        path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        url = base + path

    payload = _build_payload(args, question)

    try:
        response = _post_json(
            url=url,
            payload=payload,
            api_key=args.api_key,
            timeout=args.timeout_seconds,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.output == "json":
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0

    rendered = _render_output(endpoint=url, response=response, original_question=question)
    if args.append_original_question:
        rendered = f"{rendered}\n\nUser question:\n{question}".strip()

    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
>>>>>>> a4d0660f0cf3ab765b38228594d0bdca1aa13246
