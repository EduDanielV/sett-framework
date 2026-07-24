"""
SETT Framework — Tests: biometric_ruler (BiometricReading)
======================================================
Covers the extraction from ContextAnalyzer._detect_human_at_risk:
these tests pin the exact nested/flat parsing behavior (the v0.1.1 fix)
and the exact vital-sign thresholds, independent of ethics_ruler.
test_ethics.py continues to cover the integration (that
_detect_human_at_risk still produces the same human_at_risk verdict
end to end).
"""
import pytest

from sett.biometric_ruler.biometric_reading import BiometricReading


class TestFromContextParsing:

    def test_nested_health_dict_is_read(self):
        reading = BiometricReading.from_context(
            {"health": {"heart_rate_bpm": 180, "temperature_celsius": 40.5}}
        )
        assert reading.heart_rate_bpm == 180
        assert reading.temperature_celsius == 40.5

    def test_flat_context_is_read(self):
        reading = BiometricReading.from_context(
            {"heart_rate_bpm": 180, "temperature_celsius": 40.5}
        )
        assert reading.heart_rate_bpm == 180
        assert reading.temperature_celsius == 40.5

    def test_nested_takes_priority_over_flat(self):
        reading = BiometricReading.from_context(
            {
                "heart_rate_bpm": 70,  # flat — should be ignored
                "health": {"heart_rate_bpm": 180},
            }
        )
        assert reading.heart_rate_bpm == 180

    def test_empty_nested_health_dict_falls_back_to_flat(self):
        reading = BiometricReading.from_context(
            {"health": {}, "heart_rate_bpm": 180}
        )
        assert reading.heart_rate_bpm == 180

    def test_no_health_data_returns_all_none(self):
        reading = BiometricReading.from_context({})
        assert reading.heart_rate_bpm is None
        assert reading.temperature_celsius is None

    def test_non_dict_health_value_does_not_crash(self):
        reading = BiometricReading.from_context({"health": "not a dict"})
        assert reading.heart_rate_bpm is None

    def test_non_dict_context_returns_all_none(self):
        # Defensive: from_context should never raise on unexpected input.
        reading = BiometricReading.from_context({"health": None})
        assert reading.heart_rate_bpm is None
        assert reading.is_critical is False


class TestIsCritical:

    def test_no_data_is_not_critical(self):
        assert BiometricReading().is_critical is False

    def test_normal_vitals_are_not_critical(self):
        reading = BiometricReading(heart_rate_bpm=72, temperature_celsius=36.6)
        assert reading.is_critical is False

    def test_heart_rate_above_max_is_critical(self):
        assert BiometricReading(heart_rate_bpm=151).is_critical is True

    def test_heart_rate_at_max_boundary_is_not_critical(self):
        assert BiometricReading(heart_rate_bpm=150).is_critical is False

    def test_heart_rate_below_min_is_critical(self):
        assert BiometricReading(heart_rate_bpm=39).is_critical is True

    def test_heart_rate_at_min_boundary_is_not_critical(self):
        assert BiometricReading(heart_rate_bpm=40).is_critical is False

    def test_temperature_above_max_is_critical(self):
        assert BiometricReading(temperature_celsius=39.6).is_critical is True

    def test_temperature_at_max_boundary_is_not_critical(self):
        assert BiometricReading(temperature_celsius=39.5).is_critical is False

    def test_temperature_below_min_is_critical(self):
        assert BiometricReading(temperature_celsius=34.9).is_critical is True

    def test_temperature_at_min_boundary_is_not_critical(self):
        assert BiometricReading(temperature_celsius=35.0).is_critical is False

    def test_only_heart_rate_present_and_critical(self):
        reading = BiometricReading(heart_rate_bpm=200)
        assert reading.is_critical is True

    def test_only_temperature_present_and_critical(self):
        reading = BiometricReading(temperature_celsius=41.0)
        assert reading.is_critical is True


class TestSerialization:

    def test_to_dict_contains_expected_keys(self):
        reading = BiometricReading(heart_rate_bpm=180, temperature_celsius=40.5)
        d = reading.to_dict()
        assert d["heart_rate_bpm"] == 180
        assert d["temperature_celsius"] == 40.5
        assert d["is_critical"] is True
        assert "timestamp" in d

    def test_is_frozen(self):
        reading = BiometricReading(heart_rate_bpm=72)
        with pytest.raises(Exception):
            reading.heart_rate_bpm = 200
