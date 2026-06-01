"""Unit tests for provider-flexible LLM client (no live network)."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from config import Settings, get_settings
from models.classifier_models import Category, Priority, SuggestedAction
from services.classifier import parse_llm_response, validate_analysis
from services.llm_client import (
    LLMError,
    OllamaUnavailableError,
    ProviderUnavailableError,
    call_llm,
)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _settings(**overrides: object) -> Settings:
    return Settings(**overrides)


class TestOpenAIProvider:
    def test_request_shape_and_response_parsing(self, monkeypatch):
        monkeypatch.setattr(
            "services.llm_client.get_settings",
            lambda: _settings(
                llm_provider="openai",
                llm_api_key="sk-test",
                llm_model="gpt-4o-mini",
                openai_base_url="https://api.openai.com/v1",
            ),
        )
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"category": "human"}'}}],
        }
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("services.llm_client.httpx.Client", return_value=mock_client):
            result = call_llm("sys", "user")

        assert result == '{"category": "human"}'
        mock_client.post.assert_called_once()
        url, kwargs = mock_client.post.call_args[0][0], mock_client.post.call_args[1]
        assert url == "https://api.openai.com/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer sk-test"
        payload = kwargs["json"]
        assert payload["model"] == "gpt-4o-mini"
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["messages"] == [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "user"},
        ]

    def test_connect_error_maps_to_provider_unavailable(self, monkeypatch):
        monkeypatch.setattr(
            "services.llm_client.get_settings",
            lambda: _settings(
                llm_provider="openai",
                llm_api_key="sk-test",
                llm_model="gpt-4o-mini",
            ),
        )
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ConnectError("connection refused")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("services.llm_client.httpx.Client", return_value=mock_client):
            with pytest.raises(ProviderUnavailableError) as exc_info:
                call_llm("sys", "user")
        assert "openai" in str(exc_info.value).lower()

    def test_http_error_maps_to_llm_error(self, monkeypatch):
        monkeypatch.setattr(
            "services.llm_client.get_settings",
            lambda: _settings(
                llm_provider="openai",
                llm_api_key="sk-test",
                llm_model="gpt-4o-mini",
            ),
        )
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "bad request",
            request=MagicMock(),
            response=MagicMock(status_code=400),
        )
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("services.llm_client.httpx.Client", return_value=mock_client):
            with pytest.raises(LLMError):
                call_llm("sys", "user")

    def test_missing_api_key_raises_llm_error(self, monkeypatch):
        monkeypatch.setattr(
            "services.llm_client.get_settings",
            lambda: _settings(llm_provider="openai", llm_api_key=""),
        )
        with pytest.raises(LLMError, match="LLM_API_KEY"):
            call_llm("sys", "user")


class TestAnthropicProvider:
    def test_request_shape_and_response_parsing(self, monkeypatch):
        monkeypatch.setattr(
            "services.llm_client.get_settings",
            lambda: _settings(
                llm_provider="anthropic",
                llm_api_key="ant-test",
                llm_model="claude-3-5-sonnet-20241022",
                anthropic_base_url="https://api.anthropic.com",
                anthropic_version="2023-06-01",
            ),
        )
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": '{"category": "event"}'}],
        }
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("services.llm_client.httpx.Client", return_value=mock_client):
            result = call_llm("system rules", "email body")

        assert result == '{"category": "event"}'
        url, kwargs = mock_client.post.call_args[0][0], mock_client.post.call_args[1]
        assert url == "https://api.anthropic.com/v1/messages"
        assert kwargs["headers"]["x-api-key"] == "ant-test"
        assert kwargs["headers"]["anthropic-version"] == "2023-06-01"
        payload = kwargs["json"]
        assert payload["model"] == "claude-3-5-sonnet-20241022"
        assert payload["system"] == "system rules"
        assert payload["messages"] == [{"role": "user", "content": "email body"}]

    def test_timeout_maps_to_provider_unavailable(self, monkeypatch):
        monkeypatch.setattr(
            "services.llm_client.get_settings",
            lambda: _settings(
                llm_provider="anthropic",
                llm_api_key="ant-test",
                llm_model="claude-3-5-sonnet-20241022",
            ),
        )
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ReadTimeout("timed out")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("services.llm_client.httpx.Client", return_value=mock_client):
            with pytest.raises(ProviderUnavailableError):
                call_llm("sys", "user")


class TestOllamaProvider:
    def test_connect_error_still_raises_ollama_unavailable(self, monkeypatch):
        monkeypatch.setattr(
            "services.llm_client.get_settings",
            lambda: _settings(llm_provider="ollama"),
        )
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ConnectError("down")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("services.llm_client.httpx.Client", return_value=mock_client):
            with pytest.raises(OllamaUnavailableError) as exc_info:
                call_llm("sys", "user")
        assert isinstance(exc_info.value, ProviderUnavailableError)


class TestMockProvider:
    def test_urgent_trading_email(self, monkeypatch):
        monkeypatch.setattr(
            "services.llm_client.get_settings",
            lambda: _settings(llm_provider="mock"),
        )
        prompt = (
            "Subject: VOD.L stock stopped trading\n\n"
            "Body:\nPOV order PUKOID3234234234 stopped before market close"
        )
        raw = call_llm("ignored", prompt)
        data = parse_llm_response(raw)
        out = validate_analysis(data)
        assert out.category == Category.HUMAN
        assert out.priority == Priority.URGENT_ACTION
        assert out.suggested_action == SuggestedAction.ACKNOWLEDGE
        assert "PUKOID3234234234" in out.extracted_fields.order_ids

    def test_health_check_failure(self, monkeypatch):
        monkeypatch.setattr(
            "services.llm_client.get_settings",
            lambda: _settings(llm_provider="mock"),
        )
        prompt = "Subject: SOD Health Checks\n\n| inst | FAIL | Timeout after 30s |"
        raw = call_llm("", prompt)
        data = parse_llm_response(raw)
        out = validate_analysis(data)
        assert out.category == Category.MACHINE_GENERATED
        assert out.priority == Priority.URGENT_ACTION
        assert out.suggested_action == SuggestedAction.ESCALATE

    def test_event_invitation(self, monkeypatch):
        monkeypatch.setattr(
            "services.llm_client.get_settings",
            lambda: _settings(llm_provider="mock"),
        )
        raw = call_llm("", "You are invited for charity darts event")
        data = json.loads(raw)
        assert data["category"] == "event"
        assert data["suggested_action"] == "archive"

    def test_no_network(self, monkeypatch):
        monkeypatch.setattr(
            "services.llm_client.get_settings",
            lambda: _settings(llm_provider="mock"),
        )
        with patch("services.llm_client.httpx.Client") as client_cls:
            call_llm("s", "admincmd on <instance>")
            client_cls.assert_not_called()
