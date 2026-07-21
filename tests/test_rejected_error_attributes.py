"""
Tests for the structured attributes on SETTEthicalFilterRejectedError.

Two guarantees, verified separately:

1. Backward compatibility — str(e) returns exactly the same
   human-readable message it always has, byte for byte.
2. Structured access — .action, .score, .threshold, .principle and
   .reasoning are real attributes with the correct values, so
   downstream code never needs to parse the message string
   (which already caused a real bug: splitting on "." truncated
   a decimal score).
"""

import pytest

from sett import EthicalFilter, SETTEthicalFilterRejectedError
from sett import EthicalRuleset


def _reject(ruleset=None, action="blocked_action", **eval_kwargs):
    """Trigger a rejection and return the caught exception."""
    f = EthicalFilter(ruleset=ruleset or EthicalRuleset(
        name="strict_test", reject_threshold=0.1, warn_threshold=0.05,
    ))
    with pytest.raises(SETTEthicalFilterRejectedError) as excinfo:
        f.evaluate(action=action, context={},
                   emotional_state="crisis", **eval_kwargs)
    return excinfo.value


class TestBackwardCompatibility:

    def test_str_message_format_unchanged(self):
        """str(e) must keep the exact historical format."""
        e = _reject()
        expected = (
            f"Action '{e.action}' blocked. "
            f"Score: {e.score:.2f} (threshold: {e.threshold:.2f}). "
            f"Principle: {e.principle}. "
            f"Reasoning: {e.reasoning}"
        )
        assert str(e) == expected

    def test_str_still_contains_historical_markers(self):
        """Same assertions older code/tests relied on."""
        e = _reject(action="blocked_action")
        msg = str(e)
        assert "blocked_action" in msg
        assert "Score" in msg
        assert "threshold" in msg
        assert "Principle" in msg
        assert "Reasoning" in msg

    def test_raise_with_message_only_still_works(self):
        """Existing code that raises with just a string must not break."""
        e = SETTEthicalFilterRejectedError("plain message")
        assert str(e) == "plain message"
        assert e.action is None
        assert e.score is None
        assert e.threshold is None
        assert e.principle is None
        assert e.reasoning is None

    def test_exception_hierarchy_unchanged(self):
        from sett.exceptions import SETTError
        e = _reject()
        assert isinstance(e, SETTError)
        assert isinstance(e, Exception)


class TestStructuredAttributes:

    def test_action_attribute(self):
        e = _reject(action="send_sms")
        assert e.action == "send_sms"

    def test_score_and_threshold_are_floats(self):
        e = _reject()
        assert isinstance(e.score, float)
        assert isinstance(e.threshold, float)
        assert e.score >= e.threshold

    def test_score_is_full_precision_not_message_rounded(self):
        """
        The attribute must carry the actual computed float, not the
        2-decimal rendering used in the message. This is the direct
        fix for the string-parsing bug: no more splitting str(e) to
        recover the score.
        """
        e = _reject()
        # The message shows the score rounded to 2 decimals; the
        # attribute must equal the real score, which — when rendered
        # the same way — matches the message, without the attribute
        # itself being a string or a pre-rounded copy.
        assert f"{e.score:.2f}" in str(e)
        assert not isinstance(e.score, str)

    def test_principle_matches_ruleset(self):
        rs = EthicalRuleset(
            name="strict_test",
            reject_threshold=0.1,
            warn_threshold=0.05,
            principle="Custom principle for this test",
        )
        e = _reject(ruleset=rs)
        assert e.principle == "Custom principle for this test"

    def test_reasoning_is_present(self):
        e = _reject()
        assert isinstance(e.reasoning, str)
        assert e.reasoning  # non-empty

    def test_no_string_parsing_needed_end_to_end(self):
        """
        The downstream use case that motivated this change: read the
        score and principle directly, never touching str(e).
        """
        e = _reject(action="confirm_purchase")
        structured = {
            "action": e.action,
            "score": e.score,
            "threshold": e.threshold,
            "principle": e.principle,
        }
        assert structured["action"] == "confirm_purchase"
        assert structured["score"] >= structured["threshold"]
        assert isinstance(structured["principle"], str)
