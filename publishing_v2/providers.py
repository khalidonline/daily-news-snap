"""Small provider adapters with injectable, network-free test seams."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

Transport = Callable[[str, str, dict[str, str], dict[str, Any] | None], dict[str, Any]]

_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_TIMEOUT_SECONDS = 60
_MODELS = {"openai": "gpt-6-astra", "anthropic": "claude-sonnet-5"}
_CREDENTIALS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "getty": "GETTY_API_KEY",
}


class ProviderError(RuntimeError):
    """A safe provider failure suitable for logs and evaluation reports."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _default_transport(method: str, url: str, headers: dict[str, str], payload: dict[str, Any] | None) -> dict[str, Any]:
    if urllib.parse.urlsplit(url).scheme != "https":
        raise ProviderError("unsafe_url", "Provider requests require HTTPS.")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirects())
    try:
        response = opener.open(request, timeout=_TIMEOUT_SECONDS)
    except urllib.error.HTTPError as exc:
        response = exc
    raw = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise ProviderError("response_too_large", "Provider response exceeded the size limit.")
    try:
        body = json.loads(raw) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError("malformed_response", "Provider returned malformed JSON.") from None
    return {"status_code": response.getcode(), "body": body}


def _credential(provider: str, env: Mapping[str, str]) -> str | None:
    name = _CREDENTIALS.get(provider)
    return env.get(name, "").strip() if name else None


def _response_parts(response: Any) -> tuple[int, Any]:
    if not isinstance(response, dict):
        raise ProviderError("malformed_response", "Provider returned a malformed response.")
    status = response.get("status_code", response.get("status", 200))
    body = response.get("body", response)
    if not isinstance(status, int):
        raise ProviderError("malformed_response", "Provider returned a malformed response.")
    return status, body


def _request(transport: Transport | None, method: str, url: str, headers: dict[str, str], payload: dict[str, Any] | None) -> tuple[int, Any]:
    try:
        return _response_parts((transport or _default_transport)(method, url, headers, payload))
    except ProviderError as exc:
        if transport is None:
            raise ProviderError(exc.code, str(exc)) from None
        raise ProviderError("request_failed", "Provider request failed.") from None
    except Exception:
        raise ProviderError("request_failed", "Provider request failed.") from None


def _matches_model(model_id: Any, requested: str) -> bool:
    if model_id == requested:
        return True
    if not isinstance(model_id, str) or not model_id.startswith(requested + "-"):
        return False
    suffix = model_id.removeprefix(requested + "-")
    return bool(re.fullmatch(r"(?:\d{8}|\d{4}-\d{2}-\d{2})", suffix))


def check_access(provider: str, env: Mapping[str, str], transport: Transport | None = None) -> dict[str, str]:
    provider = provider.lower()
    if provider in {"reuters", "gcp"}:
        return {"provider": provider, "status": "setup_required", "detail": "End-to-end access has not been configured."}
    if provider not in _CREDENTIALS:
        raise ValueError(f"Unsupported provider: {provider}")
    credential = _credential(provider, env)
    if not credential:
        return {"provider": provider, "status": "missing_credentials", "detail": "Required credential is not configured."}

    if provider == "openai":
        url = "https://api.openai.com/v1/models/gpt-6-astra"
        headers = {"Authorization": f"Bearer {credential}"}
    elif provider == "anthropic":
        url = "https://api.anthropic.com/v1/models/claude-sonnet-5"
        headers = {"x-api-key": credential, "anthropic-version": "2023-06-01"}
    else:
        query = urllib.parse.urlencode({"phrase": "access check", "page_size": 1})
        url = f"https://api.gettyimages.com/v3/search/images/editorial?{query}"
        headers = {"Api-Key": credential}
    try:
        status, body = _request(transport, "GET", url, headers, None)
    except ProviderError:
        return {"provider": provider, "status": "unavailable", "detail": "Provider is unreachable."}
    if 200 <= status < 300:
        valid = isinstance(body, dict) and (
            isinstance(body.get("images"), list)
            if provider == "getty"
            else _matches_model(body.get("id"), _MODELS[provider])
        )
        if not valid:
            return {"provider": provider, "status": "unavailable", "detail": "Provider returned a malformed response."}
        detail = "Discovery access confirmed; image download licensing is not established." if provider == "getty" else "Configured model is accessible."
        return {"provider": provider, "status": "available", "detail": detail}
    return {"provider": provider, "status": "unavailable", "detail": f"Provider returned HTTP {status}."}


def generate(provider: str, prompt: str, *, env: Mapping[str, str], transport: Transport | None = None, max_output_tokens: int = 6000) -> dict[str, Any]:
    if isinstance(max_output_tokens, bool) or not isinstance(max_output_tokens, int) or not 1 <= max_output_tokens <= 6000:
        raise ValueError("max_output_tokens must be an integer from 1 through 6000")
    provider = provider.lower()
    if provider not in _MODELS:
        raise ValueError(f"Unsupported generation provider: {provider}")
    credential = _credential(provider, env)
    if not credential:
        raise ProviderError("missing_credentials", "Required credential is not configured.")

    model = _MODELS[provider]
    if provider == "openai":
        url = "https://api.openai.com/v1/responses"
        headers = {"Authorization": f"Bearer {credential}", "Content-Type": "application/json"}
        payload = {"model": model, "input": prompt, "max_output_tokens": max_output_tokens}
    else:
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": credential, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_output_tokens}

    started = time.monotonic()
    status, body = _request(transport, "POST", url, headers, payload)
    elapsed_ms = round((time.monotonic() - started) * 1000)
    if not 200 <= status < 300:
        raise ProviderError("http_error", f"Provider returned HTTP {status}.")
    if not isinstance(body, dict):
        raise ProviderError("malformed_response", "Provider returned a malformed response.")
    text = _parse_openai(body) if provider == "openai" else _parse_anthropic(body)
    response_id = body.get("id")
    usage = body.get("usage")
    if not isinstance(response_id, str) or not response_id.strip() or not _valid_usage(usage):
        raise ProviderError("malformed_response", "Provider returned a malformed response.")
    return {"model": model, "text": text, "usage": usage, "response_id": response_id, "elapsed_ms": elapsed_ms}


def _parse_openai(body: dict[str, Any]) -> str:
    if body.get("status") != "completed" or not isinstance(body.get("output"), list):
        raise ProviderError("incomplete_response", "Provider did not return a complete response.")
    texts = []
    for item in body["output"]:
        if not isinstance(item, dict) or not isinstance(item.get("type"), str):
            raise ProviderError("malformed_response", "Provider returned a malformed response.")
        if item["type"] == "reasoning":
            continue
        if item["type"] != "message" or not isinstance(item.get("content"), list):
            raise ProviderError("malformed_response", "Provider returned a malformed response.")
        if "status" in item and item["status"] != "completed":
            raise ProviderError("incomplete_response", "Provider did not return a complete response.")
        for part in item["content"]:
            if not isinstance(part, dict):
                raise ProviderError("malformed_response", "Provider returned a malformed response.")
            if part.get("type") == "refusal":
                raise ProviderError("refused", "Provider refused the generation request.")
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
            elif part.get("type") != "refusal":
                raise ProviderError("malformed_response", "Provider returned a malformed response.")
    if not texts or not "".join(texts).strip():
        raise ProviderError("malformed_response", "Provider response contained no text.")
    return "".join(texts)


def _parse_anthropic(body: dict[str, Any]) -> str:
    if body.get("stop_reason") != "end_turn" or not isinstance(body.get("content"), list):
        raise ProviderError("incomplete_response", "Provider did not return a complete response.")
    texts = []
    for part in body["content"]:
        if not isinstance(part, dict) or not isinstance(part.get("type"), str):
            raise ProviderError("malformed_response", "Provider returned a malformed response.")
        if part["type"] == "refusal":
            raise ProviderError("refused", "Provider refused the generation request.")
        # The canonical answer is in text blocks; reasoning is not answer text.
        if part["type"] == "thinking" and isinstance(part.get("thinking"), str) and isinstance(part.get("signature"), str):
            continue
        if part["type"] == "redacted_thinking" and isinstance(part.get("data"), str):
            continue
        if part["type"] != "text" or not isinstance(part.get("text"), str):
            raise ProviderError("malformed_response", "Provider returned a malformed response.")
        texts.append(part["text"])
    if not texts or not "".join(texts).strip():
        raise ProviderError("malformed_response", "Provider response contained no text.")
    return "".join(texts)


def _valid_usage(usage: Any) -> bool:
    if not isinstance(usage, dict):
        return False
    return all(
        isinstance(usage.get(name), int)
        and not isinstance(usage[name], bool)
        and usage[name] >= 0
        for name in ("input_tokens", "output_tokens")
    )


def search_getty(query: str, *, env: Mapping[str, str], transport: Transport | None = None, limit: int = 5) -> list[dict[str, Any]]:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    credential = _credential("getty", env)
    if not credential:
        raise ProviderError("missing_credentials", "Required credential is not configured.")
    page_size = min(limit, 10)
    params = urllib.parse.urlencode({
        "phrase": query,
        "page_size": page_size,
        "fields": "id,title,caption,date_created",
    })
    status, body = _request(transport, "GET", f"https://api.gettyimages.com/v3/search/images/editorial?{params}", {"Api-Key": credential}, None)
    if not 200 <= status < 300:
        raise ProviderError("http_error", f"Provider returned HTTP {status}.")
    if not isinstance(body, dict) or not isinstance(body.get("images"), list):
        raise ProviderError("malformed_response", "Provider returned a malformed response.")
    results = []
    for image in body["images"]:
        if not isinstance(image, dict) or not isinstance(image.get("id"), (str, int)):
            raise ProviderError("malformed_response", "Provider returned a malformed response.")
        results.append({
            "asset_id": str(image["id"]),
            "caption": image.get("caption"),
            "title": image.get("title"),
            "date_created": image.get("date_created"),
            "download_available": None,
            "licensing_verified": False,
        })
    return results
