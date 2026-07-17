"""
SETT Framework — Tests: OllamaAdapter
======================================================
Since Ollama itself is an external local service (not something we can
assume is installed/running in a test environment), these tests mock
the HTTP layer rather than requiring a live Ollama server. Real
end-to-end verification against an actual running Ollama instance
should be done manually — see templates/README.md-style guidance in
services_llm/ollama.py's docstring for setup steps.
"""
import json
import urllib.error
import pytest
from unittest.mock import patch, MagicMock

from sett.services_llm.ollama import OllamaAdapter
from sett.exceptions import SETTLLMAdapterError


def _fake_response(payload: dict) -> MagicMock:
    """Build a mock object that behaves like the result of urlopen()."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


class TestOllamaAdapterBasics:

    def test_default_model_name(self):
        adapter = OllamaAdapter()
        assert adapter.model_name == "qwen3:1.7b"

    def test_custom_model_name(self):
        adapter = OllamaAdapter(model="phi4-mini")
        assert adapter.model_name == "phi4-mini"

    def test_repr_contains_model_and_url(self):
        adapter = OllamaAdapter(model="phi4-mini", base_url="http://localhost:11434")
        r = repr(adapter)
        assert "phi4-mini" in r
        assert "11434" in r

    def test_base_url_trailing_slash_is_stripped(self):
        adapter = OllamaAdapter(base_url="http://localhost:11434/")
        assert adapter._base_url == "http://localhost:11434"

    def test_temperature_clamped_to_valid_range(self):
        assert OllamaAdapter(temperature=5.0)._temperature == 1.0
        assert OllamaAdapter(temperature=-1.0)._temperature == 0.0


class TestOllamaAdapterComplete:

    @patch("urllib.request.urlopen")
    def test_complete_returns_response_text(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"response": "Hello, I am AIDA."})
        adapter = OllamaAdapter()
        result = adapter.complete("Say good morning")
        assert result == "Hello, I am AIDA."

    @patch("urllib.request.urlopen")
    def test_complete_sends_correct_endpoint_and_model(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"response": "ok"})
        adapter = OllamaAdapter(model="qwen3:1.7b")
        adapter.complete("hello")

        sent_request = mock_urlopen.call_args[0][0]
        assert sent_request.full_url == "http://localhost:11434/api/generate"

        sent_body = json.loads(sent_request.data.decode("utf-8"))
        assert sent_body["model"] == "qwen3:1.7b"
        assert sent_body["prompt"] == "hello"
        assert sent_body["stream"] is False

    @patch("urllib.request.urlopen")
    def test_complete_includes_system_prompt_when_given(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"response": "ok"})
        adapter = OllamaAdapter()
        adapter.complete("hello", system="You are AIDA, a warm assistant.")

        sent_body = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert sent_body["system"] == "You are AIDA, a warm assistant."

    @patch("urllib.request.urlopen")
    def test_complete_omits_system_key_when_not_given(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"response": "ok"})
        adapter = OllamaAdapter()
        adapter.complete("hello")

        sent_body = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert "system" not in sent_body

    @patch("urllib.request.urlopen")
    def test_complete_missing_response_key_returns_empty_string(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({})
        adapter = OllamaAdapter()
        assert adapter.complete("hello") == ""


class TestOllamaAdapterChat:

    @patch("urllib.request.urlopen")
    def test_chat_returns_message_content(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response(
            {"message": {"role": "assistant", "content": "Good morning, Dan."}}
        )
        adapter = OllamaAdapter()
        result = adapter.chat([{"role": "user", "content": "good morning"}])
        assert result == "Good morning, Dan."

    @patch("urllib.request.urlopen")
    def test_chat_sends_correct_endpoint(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"message": {"content": "ok"}})
        adapter = OllamaAdapter()
        adapter.chat([{"role": "user", "content": "hello"}])

        sent_request = mock_urlopen.call_args[0][0]
        assert sent_request.full_url == "http://localhost:11434/api/chat"

    @patch("urllib.request.urlopen")
    def test_chat_prepends_system_message(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"message": {"content": "ok"}})
        adapter = OllamaAdapter()
        adapter.chat(
            [{"role": "user", "content": "hello"}],
            system="Sos AIDA.",
        )

        sent_body = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert sent_body["messages"][0] == {"role": "system", "content": "Sos AIDA."}
        assert sent_body["messages"][1] == {"role": "user", "content": "hello"}

    @patch("urllib.request.urlopen")
    def test_chat_without_system_does_not_prepend(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"message": {"content": "ok"}})
        adapter = OllamaAdapter()
        adapter.chat([{"role": "user", "content": "hello"}])

        sent_body = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert len(sent_body["messages"]) == 1
        assert sent_body["messages"][0]["role"] == "user"


class TestOllamaAdapterErrorHandling:

    @patch("urllib.request.urlopen")
    def test_connection_error_raises_sett_llm_adapter_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        adapter = OllamaAdapter()
        with pytest.raises(SETTLLMAdapterError) as exc_info:
            adapter.complete("hello")
        assert "Ollama" in str(exc_info.value)

    @patch("urllib.request.urlopen")
    def test_malformed_json_raises_sett_llm_adapter_error(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not valid json{{{"
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        mock_urlopen.return_value = mock_resp

        adapter = OllamaAdapter()
        with pytest.raises(SETTLLMAdapterError):
            adapter.complete("hello")

    def test_error_does_not_leak_raw_urllib_exception_type(self):
        """
        Callers should only ever need to catch SETTLLMAdapterError,
        consistent with the other adapters — not urllib-specific
        exceptions, which would leak an implementation detail.
        """
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("down")
            adapter = OllamaAdapter()
            try:
                adapter.complete("hello")
                assert False, "should have raised"
            except SETTLLMAdapterError:
                pass
            except Exception as e:
                pytest.fail(f"Leaked non-SETT exception type: {type(e)}")
