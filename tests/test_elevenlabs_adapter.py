"""
SETT Framework — Tests: ElevenLabsTTSAdapter
======================================================
ElevenLabs is a cloud service reached via plain HTTP (no SDK), so
these tests mock `requests.post` the same way test_ollama_adapter.py
mocks `urllib.request.urlopen` — no live API key or network access
required.
"""
import pytest
from unittest.mock import patch, MagicMock

from sett.services_tts_stt.elevenlabs import ElevenLabsTTSAdapter
from sett.exceptions import SETTServiceAdapterError


def _fake_response(status_code: int = 200, content: bytes = b"fake-mp3-bytes", text: str = ""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.text = text
    return resp


class TestElevenLabsTTSAdapterBasics:

    def test_requires_api_key(self, monkeypatch):
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        with pytest.raises(SETTServiceAdapterError):
            ElevenLabsTTSAdapter()

    def test_api_key_from_env_var(self, monkeypatch):
        monkeypatch.setenv("ELEVENLABS_API_KEY", "env-key")
        adapter = ElevenLabsTTSAdapter()
        assert adapter._api_key == "env-key"

    def test_api_key_argument_overrides_env(self, monkeypatch):
        monkeypatch.setenv("ELEVENLABS_API_KEY", "env-key")
        adapter = ElevenLabsTTSAdapter(api_key="explicit-key")
        assert adapter._api_key == "explicit-key"

    def test_audio_format_is_mp3(self):
        adapter = ElevenLabsTTSAdapter(api_key="k")
        assert adapter.audio_format == "mp3"

    def test_repr_contains_voice_id(self):
        adapter = ElevenLabsTTSAdapter(api_key="k", voice_id="my-voice")
        assert "my-voice" in repr(adapter)

    def test_stability_similarity_style_clamped_to_valid_range(self):
        adapter = ElevenLabsTTSAdapter(
            api_key="k", stability=5.0, similarity_boost=-1.0, style=2.0
        )
        assert adapter._stability == 1.0
        assert adapter._similarity_boost == 0.0
        assert adapter._style == 1.0


class TestElevenLabsTTSAdapterSynthesize:

    @patch("sett.services_tts_stt.elevenlabs.requests.post")
    def test_synthesize_returns_audio_bytes(self, mock_post):
        mock_post.return_value = _fake_response(content=b"real-audio-bytes")
        adapter = ElevenLabsTTSAdapter(api_key="k")
        result = adapter.synthesize("Hola, ¿en qué puedo ayudarte?")
        assert result == b"real-audio-bytes"

    @patch("sett.services_tts_stt.elevenlabs.requests.post")
    def test_synthesize_sends_correct_url_and_headers(self, mock_post):
        mock_post.return_value = _fake_response()
        adapter = ElevenLabsTTSAdapter(api_key="secret-key", voice_id="voice-123")
        adapter.synthesize("hello")

        call = mock_post.call_args
        assert call.args[0] == "https://api.elevenlabs.io/v1/text-to-speech/voice-123"
        assert call.kwargs["headers"]["xi-api-key"] == "secret-key"
        assert call.kwargs["headers"]["accept"] == "audio/mpeg"

    @patch("sett.services_tts_stt.elevenlabs.requests.post")
    def test_synthesize_sends_correct_payload(self, mock_post):
        mock_post.return_value = _fake_response()
        adapter = ElevenLabsTTSAdapter(
            api_key="k", model_id="eleven_multilingual_v2", stability=0.4
        )
        adapter.synthesize("hello world")

        payload = mock_post.call_args.kwargs["json"]
        assert payload["text"] == "hello world"
        assert payload["model_id"] == "eleven_multilingual_v2"
        assert payload["voice_settings"]["stability"] == 0.4

    @patch("sett.services_tts_stt.elevenlabs.requests.post")
    def test_synthesize_kwargs_override_instance_defaults(self, mock_post):
        mock_post.return_value = _fake_response()
        adapter = ElevenLabsTTSAdapter(api_key="k", voice_id="default-voice")
        adapter.synthesize("hello", voice_id="override-voice")

        call = mock_post.call_args
        assert "override-voice" in call.args[0]


class TestElevenLabsTTSAdapterErrorHandling:

    @patch("sett.services_tts_stt.elevenlabs.requests.post")
    def test_non_200_status_raises_sett_service_adapter_error(self, mock_post):
        mock_post.return_value = _fake_response(
            status_code=401, text="Unauthorized"
        )
        adapter = ElevenLabsTTSAdapter(api_key="bad-key")
        with pytest.raises(SETTServiceAdapterError) as exc_info:
            adapter.synthesize("hello")
        assert "401" in str(exc_info.value)

    @patch("sett.services_tts_stt.elevenlabs.requests.post")
    def test_network_error_raises_sett_service_adapter_error(self, mock_post):
        import requests as real_requests
        mock_post.side_effect = real_requests.exceptions.ConnectionError("down")
        adapter = ElevenLabsTTSAdapter(api_key="k")
        with pytest.raises(SETTServiceAdapterError) as exc_info:
            adapter.synthesize("hello")
        assert "ElevenLabs" in str(exc_info.value)

    @patch("sett.services_tts_stt.elevenlabs.requests.post")
    def test_error_does_not_leak_raw_requests_exception_type(self, mock_post):
        """
        Callers should only ever need to catch SETTServiceAdapterError,
        consistent with the LLM adapters — not requests-specific
        exceptions, which would leak an implementation detail.
        """
        import requests as real_requests
        mock_post.side_effect = real_requests.exceptions.Timeout("timed out")
        adapter = ElevenLabsTTSAdapter(api_key="k")
        try:
            adapter.synthesize("hello")
            assert False, "should have raised"
        except SETTServiceAdapterError:
            pass
        except Exception as e:
            pytest.fail(f"Leaked non-SETT exception type: {type(e)}")
