"""
SETT Framework — Google Cloud Sentiment Adapter
==============================
Sentiment analysis adapter backed by Google Cloud Natural Language.

Implements SentimentBase — fully interchangeable with any other
provider's adapter.

Ported from the recovered Virtual-assistant-1st-attempt prototype
(SentimentAnalyzer class, Nov. 2024) — same underlying sentiment call
(`language_v1.LanguageServiceClient().analyze_sentiment`), reduced to
just that. Two things present in the original were deliberately not
carried over:

  - Storing results in Google Cloud Storage + loading them to
    BigQuery: that was infrastructure for a solo experiment logging
    its own history, not something a sentiment adapter needs to do to
    answer "what is the sentiment of this text" — an application that
    wants to log results can do so with the SentimentResult this
    adapter already returns, without the adapter reaching into two
    more cloud services on every call.
  - `enhance_response()` (a Gemini call to generate text): that is
    text generation, not sentiment analysis — it belongs to an LLM
    adapter/PhrasingExpert, not here. Mixing it into this class was
    exactly the kind of two-responsibilities-in-one-expert pattern
    Convención #1's corollary already documents splitting.

Requires: pip install sett-framework[google-sentiment]
"""
from __future__ import annotations
import os
from typing import Any

from sett.services_sentiment.base import SentimentBase, SentimentResult, SentenceSentiment
from sett.exceptions import SETTServiceAdapterError


class GoogleSentimentAdapter(SentimentBase):
    """
    Sentiment analysis adapter for Google Cloud Natural Language.

    Usage:
        from sett.services_sentiment.google import GoogleSentimentAdapter

        sentiment = GoogleSentimentAdapter()
        result = sentiment.analyze("Estoy bastante frustrado con esto.")
        print(result.score, result.magnitude)
    """

    def __init__(self, credentials_path: str | None = None) -> None:
        """
        Args:
            credentials_path: Path to a Google Cloud service account
                JSON key. Falls back to the GOOGLE_APPLICATION_CREDENTIALS
                environment variable if not given.
        """
        try:
            from google.cloud import language_v1
            self._language_v1 = language_v1
        except ImportError:
            raise SETTServiceAdapterError(
                "The 'google-cloud-language' package is required to use "
                "GoogleSentimentAdapter. Install it with: "
                "pip install sett-framework[google-sentiment]"
            )

        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            raise SETTServiceAdapterError(
                "Google Cloud credentials not found. Pass credentials_path= "
                "or set the GOOGLE_APPLICATION_CREDENTIALS environment "
                "variable to a service account JSON key."
            )

        self._client = self._language_v1.LanguageServiceClient()

    def analyze(self, text: str, **kwargs: Any) -> SentimentResult:
        """
        Analyze the sentiment of the given text.

        Args:
            text: The text to analyze.
            **kwargs: unused; accepted for interface compatibility.

        Returns:
            A SentimentResult with document-level score/magnitude and
            a per-sentence breakdown (Google Cloud NL always returns
            sentence-level detail, so it is always populated here).
        """
        try:
            document = self._language_v1.Document(
                content=text,
                type_=self._language_v1.Document.Type.PLAIN_TEXT,
            )
            response = self._client.analyze_sentiment(
                request={"document": document}
            )
            sentences = tuple(
                SentenceSentiment(
                    text=sentence.text.content,
                    score=sentence.sentiment.score,
                )
                for sentence in response.sentences
            )
            return SentimentResult(
                score=response.document_sentiment.score,
                magnitude=response.document_sentiment.magnitude,
                sentences=sentences,
            )
        except SETTServiceAdapterError:
            raise
        except Exception as e:
            raise SETTServiceAdapterError(
                f"Google Cloud Natural Language error during analyze(): {e}"
            ) from e

    def __repr__(self) -> str:
        return "GoogleSentimentAdapter()"
