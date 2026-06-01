"""LLM client — Ollama, OpenAI, Anthropic, or mock behind one interface."""

import json
import re
from typing import Any

import httpx

from config import get_settings
from models.classifier_models import Category, Priority, SuggestedAction


class ProviderUnavailableError(Exception):
    """Raised when the configured LLM provider cannot be reached."""


class OllamaUnavailableError(ProviderUnavailableError):
    """Raised when Ollama cannot be reached."""


class LLMError(Exception):
    """Raised when the LLM returns an unexpected response."""


_ORDER_ID_PATTERN = re.compile(
    r"\b(?:PUKOID|POV|MOC)[A-Z0-9]*\b|\b[A-Z]{2,}\d{6,}\b",
    re.IGNORECASE,
)
_INSTANCE_PATTERN = re.compile(r"<instance\d*>|<instance>", re.IGNORECASE)


def call_llm(system_prompt: str, user_prompt: str) -> str:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()
    if provider == "ollama":
        return _call_ollama(system_prompt, user_prompt)
    if provider == "openai":
        return _call_openai(system_prompt, user_prompt)
    if provider == "anthropic":
        return _call_anthropic(system_prompt, user_prompt)
    if provider == "mock":
        return _call_mock(system_prompt, user_prompt)
    raise NotImplementedError(
        f"LLM provider '{settings.llm_provider}' is not implemented. "
        "Use ollama, openai, anthropic, or mock."
    )


def _timeout() -> float:
    return get_settings().ollama_timeout_seconds


def _map_connectivity_error(exc: Exception, provider: str) -> ProviderUnavailableError:
    settings = get_settings()
    if provider == "ollama":
        if isinstance(exc, httpx.ConnectError):
            return OllamaUnavailableError(
                "Cannot reach Ollama. Is it running? Start with: ollama serve"
            )
        return OllamaUnavailableError(
            f"Ollama request timed out after {settings.ollama_timeout_seconds}s"
        )
    if isinstance(exc, httpx.ConnectError):
        return ProviderUnavailableError(f"Cannot reach {provider} API: {exc}")
    return ProviderUnavailableError(
        f"{provider} request timed out after {settings.ollama_timeout_seconds}s"
    )


def _post_json(url: str, *, headers: dict[str, str], payload: dict[str, Any], provider: str) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=_timeout()) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise _map_connectivity_error(exc, provider) from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"{provider} HTTP error: {exc}") from exc

    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise LLMError(f"{provider} returned non-JSON body") from exc


def _call_ollama(system_prompt: str, user_prompt: str) -> str:
    settings = get_settings()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "format": "json",
    }
    data = _post_json(url, headers={}, payload=payload, provider="ollama")
    message = data.get("message") or {}
    content = message.get("content")
    if not content:
        raise LLMError(f"Ollama returned no content: {data}")
    return content


def _call_openai(system_prompt: str, user_prompt: str) -> str:
    settings = get_settings()
    if not settings.llm_api_key:
        raise LLMError("LLM_API_KEY is required when LLM_PROVIDER=openai")

    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    data = _post_json(url, headers=headers, payload=payload, provider="openai")
    choices = data.get("choices") or []
    if not choices:
        raise LLMError(f"OpenAI returned no choices: {data}")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        raise LLMError(f"OpenAI returned no content: {data}")
    return content


def _call_anthropic(system_prompt: str, user_prompt: str) -> str:
    settings = get_settings()
    if not settings.llm_api_key:
        raise LLMError("LLM_API_KEY is required when LLM_PROVIDER=anthropic")

    url = f"{settings.anthropic_base_url.rstrip('/')}/v1/messages"
    payload = {
        "model": settings.llm_model,
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    headers = {
        "x-api-key": settings.llm_api_key,
        "anthropic-version": settings.anthropic_version,
        "Content-Type": "application/json",
    }
    data = _post_json(url, headers=headers, payload=payload, provider="anthropic")
    content_blocks = data.get("content") or []
    text_parts = [
        block.get("text", "")
        for block in content_blocks
        if block.get("type") == "text"
    ]
    content = "".join(text_parts).strip()
    if not content:
        raise LLMError(f"Anthropic returned no text content: {data}")
    return content


def _call_mock(system_prompt: str, user_prompt: str) -> str:
    del system_prompt
    text = user_prompt.lower()

    if any(k in text for k in ("unsubscribe", "lottery", "viagra", "noreply marketing")):
        category = Category.SPAM
        priority = Priority.IGNORE
        suggested_action = SuggestedAction.IGNORE
        reason = "Mock: promotional or spam-like content detected."
    elif any(
        k in text
        for k in ("invited", "charity", "dart", "social event", "you are invited")
    ):
        category = Category.EVENT
        priority = Priority.NON_URGENT_ACTION
        suggested_action = SuggestedAction.ARCHIVE
        reason = "Mock: social or event invitation; no production support needed."
    elif "health check" in text or "sod health" in text:
        category = Category.MACHINE_GENERATED
        if re.search(r"\bFAIL\b|\btimeout\b", user_prompt, re.IGNORECASE):
            priority = Priority.URGENT_ACTION
            suggested_action = SuggestedAction.ESCALATE
            reason = "Mock: automated health check reports a failure."
        else:
            priority = Priority.IGNORE
            suggested_action = SuggestedAction.IGNORE
            reason = "Mock: automated health check passed; no action required."
    elif re.search(r"\bFAIL\b|\btimeout\b", user_prompt, re.IGNORECASE):
        category = Category.MACHINE_GENERATED
        priority = Priority.URGENT_ACTION
        suggested_action = SuggestedAction.ESCALATE
        reason = "Mock: automated alert with failure keywords."
    elif any(
        k in text
        for k in ("stop trading", "pov order", "pukoid", "before market close")
    ):
        category = Category.HUMAN
        priority = Priority.URGENT_ACTION
        suggested_action = SuggestedAction.ACKNOWLEDGE
        reason = "Mock: human sender reports urgent trading or order impact."
    elif "admincmd" in text or "stats check" in text:
        category = Category.HUMAN
        priority = Priority.NON_URGENT_ACTION
        suggested_action = SuggestedAction.ASK_HUMAN
        reason = "Mock: human request for operational help without incident signals."
    else:
        category = Category.HUMAN
        priority = Priority.NON_URGENT_ACTION
        suggested_action = SuggestedAction.ACKNOWLEDGE
        reason = "Mock: default human triage for unmatched keywords."

    combined = user_prompt
    order_ids = list(dict.fromkeys(_ORDER_ID_PATTERN.findall(combined)))
    instances = list(dict.fromkeys(_INSTANCE_PATTERN.findall(combined)))
    detected_keywords: list[str] = []
    for term in ("FAIL", "Timeout", "ERROR", "admincmd", "health check"):
        if term.lower() in text:
            detected_keywords.append(term)

    payload = {
        "category": category.value,
        "priority": priority.value,
        "suggested_action": suggested_action.value,
        "reason": reason,
        "extracted_fields": {
            "order_ids": order_ids,
            "instance_names": instances,
            "error_summary": detected_keywords[0] if detected_keywords else None,
            "sender_name": None,
            "detected_keywords": detected_keywords,
        },
    }
    return json.dumps(payload)
