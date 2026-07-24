"""
SETT Framework — Tests: GoogleSentimentAdapter
======================================================
google-cloud-language is an optional dependency (pip install
sett-framework[google-sentiment]) — not installed in this test
environment, same situation as the TTS/STT Google adapters. See
test_google_tts_stt_adapters.py's module docstring for why sys.modules
injection (not mocking an installed SDK) is the testing strategy here,
and why a plain MagicMock parent module is not enough on its own.
"""
import sys
import pytest
from unittest.mock import MagicMock, patch

from sett.exceptions import SETTServiceAdapterError
from sett.services_sentiment.base import SentimentResult, SentenceSentiment


def _fake_google_cloud_sys_modules(submodule_name: str, submodule_mock: MagicMock) -> dict:
    """Same construction as test_google_tts_stt_adapters.py — see that
    file for why the parent attribute must be set explicitly."""
    google_cloud_mock = MagicMock(name="google.cloud")
    setattr(google_cloud_mock, submodule_name, submodule_mock)
    google_mock = MagicMock(name="google")
    google_mock.cloud = google_cloud_mock
    return {
        "google": google_mock,
        "google.cloud": google_cloud_mock,
        f"google.cloud.{submodule_name}": submodule_mock,
    }


def _fake_language_v1_module():
    fake = MagicMock(name="language_v1")
    fake.Document.Type.PLAIN_TEXT = "PLAIN_TEXT"

    client_instance = MagicMock(name="LanguageServiceClient_instance")
    fake.LanguageServiceClient.return_value = client_instance
    return fake, client_instance


def _fake_sentiment_response(score: float, magnitude: float, sentences: list[tuple[str, float]]):
    """Build a fake response shaped like Google NL's AnalyzeSentimentResponse."""
    response = MagicMock()
    response.document_sentiment.score = score
    response.document_sentiment.magnitude = magnitude

    sentence_mocks = []
    for text, sentence_score in sentences:
        s = MagicMock()
        s.text.content = text
        s.sentiment.score = sentence_score
        sentence_mocks.append(s)
    response.sentences = sentence_mocks
    return response


@pytest.fixture
def fake_google_credentials(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/fake/path/creds.json")


class TestMissingDependency:

    def test_missing_package_raises_sett_service_adapter_error(self):
        with patch.dict(sys.modules, {"google.cloud.language_v1": None,
                                       "google.cloud": None}):
            from sett.services_sentiment.google import GoogleSentimentAdapter
            with pytest.raises(SETTServiceAdapterError) as exc_info:
                GoogleSentimentAdapter()
            assert "google-cloud-language" in str(exc_info.value)


class TestGoogleSentimentAdapterAnalyze:

    def test_analyze_returns_score_and_magnitude(self, fake_google_credentials):
        fake_module, client = _fake_language_v1_module()
        client.analyze_sentiment.return_value = _fake_sentiment_response(
            score=-0.6, magnitude=1.2, sentences=[]
        )
        with patch.dict(sys.modules, _fake_google_cloud_sys_modules("language_v1", fake_module)):
            from sett.services_sentiment.google import GoogleSentimentAdapter
            adapter = GoogleSentimentAdapter()
            result = adapter.analyze("Estoy bastante frustrado con esto.")

            assert isinstance(result, SentimentResult)
            assert result.score == -0.6
            assert result.magnitude == 1.2

    def test_analyze_returns_per_sentence_breakdown(self, fake_google_credentials):
        fake_module, client = _fake_language_v1_module()
        client.analyze_sentiment.return_value = _fake_sentiment_response(
            score=0.1,
            magnitude=0.9,
            sentences=[
                ("Que buena tu ayuda.", -0.5),
                ("Como siempre.", -0.4),
            ],
        )
        with patch.dict(sys.modules, _fake_google_cloud_sys_modules("language_v1", fake_module)):
            from sett.services_sentiment.google import GoogleSentimentAdapter
            adapter = GoogleSentimentAdapter()
            result = adapter.analyze("Que buena tu ayuda. Como siempre.")

            assert len(result.sentences) == 2
            assert result.sentences[0] == SentenceSentiment(
                text="Que buena tu ayuda.", score=-0.5
            )
            assert result.sentences[1] == SentenceSentiment(
                text="Como siempre.", score=-0.4
            )

    def test_analyze_sends_text_as_plain_text_document(self, fake_google_credentials):
        fake_module, client = _fake_language_v1_module()
        client.analyze_sentiment.return_value = _fake_sentiment_response(
            score=0.0, magnitude=0.0, sentences=[]
        )
        with patch.dict(sys.modules, _fake_google_cloud_sys_modules("language_v1", fake_module)):
            from sett.services_sentiment.google import GoogleSentimentAdapter
            adapter = GoogleSentimentAdapter()
            adapter.analyze("hola")

            fake_module.Document.assert_called_with(
                content="hola", type_="PLAIN_TEXT"
            )

    def test_missing_credentials_raises_sett_service_adapter_error(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        fake_module, _ = _fake_language_v1_module()
        with patch.dict(sys.modules, _fake_google_cloud_sys_modules("language_v1", fake_module)):
            from sett.services_sentiment.google import GoogleSentimentAdapter
            with pytest.raises(SETTServiceAdapterError):
                GoogleSentimentAdapter()

    def test_credentials_path_argument_sets_env_var(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        fake_module, _ = _fake_language_v1_module()
        with patch.dict(sys.modules, _fake_google_cloud_sys_modules("language_v1", fake_module)):
            from sett.services_sentiment.google import GoogleSentimentAdapter
            GoogleSentimentAdapter(credentials_path="/explicit/creds.json")
            import os
            assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == "/explicit/creds.json"

    def test_analyze_wraps_client_error(self, fake_google_credentials):
        fake_module, client = _fake_language_v1_module()
        client.analyze_sentiment.side_effect = RuntimeError("quota exceeded")
        with patch.dict(sys.modules, _fake_google_cloud_sys_modules("language_v1", fake_module)):
            from sett.services_sentiment.google import GoogleSentimentAdapter
            adapter = GoogleSentimentAdapter()
            with pytest.raises(SETTServiceAdapterError) as exc_info:
                adapter.analyze("hola")
            assert "quota exceeded" in str(exc_info.value)


class TestSentimentResultAndSentenceSentiment:

    def test_sentiment_result_defaults_to_empty_sentences(self):
        result = SentimentResult(score=0.5, magnitude=0.5)
        assert result.sentences == ()

    def test_sentiment_result_is_frozen(self):
        result = SentimentResult(score=0.5, magnitude=0.5)
        with pytest.raises(Exception):
            result.score = 0.9

    def test_sentence_sentiment_is_frozen(self):
        s = SentenceSentiment(text="hola", score=0.1)
        with pytest.raises(Exception):
            s.score = 0.9
