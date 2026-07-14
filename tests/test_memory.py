"""
SETT Framework — Tests: Memory Layer
======================================================
Unit and integration tests for UniversalMemory and PrivateMemory.

Key contracts tested:
  - PrivateMemory is exclusive: no cross-agent access
  - UniversalMemory only exposes agent results, not env context keys
  - EthicalFilter intercepts every UniversalMemory write
  - EnvironmentalContext is stored and retrieved correctly
  - Thread safety: concurrent writes don't corrupt state
"""
import pytest
import threading
from sett.memory_ruler.private import PrivateMemory
from sett.memory_ruler.universal import UniversalMemory
from sett.risk_ruler.risk_level import RiskLevel
from sett.risk_ruler.environmental_context import EnvironmentalContext


# ── PrivateMemory tests ──────────────────────────────────────────────────────

class TestPrivateMemory:

    def test_write_and_read(self):
        mem = PrivateMemory(owner="TestAgent")
        mem.write("key", "value")
        assert mem.read("key") == "value"

    def test_read_missing_key_returns_default(self):
        mem = PrivateMemory(owner="TestAgent")
        assert mem.read("missing") is None
        assert mem.read("missing", "fallback") == "fallback"

    def test_write_overwrites_existing_key(self):
        mem = PrivateMemory(owner="TestAgent")
        mem.write("key", "first")
        mem.write("key", "second")
        assert mem.read("key") == "second"

    def test_get_all_returns_copy(self):
        mem = PrivateMemory(owner="TestAgent")
        mem.write("a", 1)
        mem.write("b", 2)
        snapshot = mem.get_all()
        assert snapshot == {"a": 1, "b": 2}
        # Modifying the copy doesn't affect the memory
        snapshot["a"] = 999
        assert mem.read("a") == 1

    def test_clear_removes_all_values(self):
        mem = PrivateMemory(owner="TestAgent")
        mem.write("x", 1)
        mem.clear()
        assert mem.read("x") is None
        assert mem.get_all() == {}

    def test_history_records_writes(self):
        mem = PrivateMemory(owner="TestAgent")
        mem.write("k1", "v1")
        mem.write("k2", "v2")
        history = mem.get_history()
        assert len(history) == 2
        assert history[0]["key"] == "k1"
        assert history[1]["key"] == "k2"

    def test_each_agent_has_independent_memory(self):
        """Core privacy contract: no cross-contamination between agents."""
        mem_a = PrivateMemory(owner="AgentA")
        mem_b = PrivateMemory(owner="AgentB")
        mem_a.write("secret", "from_a")
        assert mem_b.read("secret") is None

    def test_owner_is_accessible(self):
        mem = PrivateMemory(owner="MyAgent")
        assert mem.owner == "MyAgent"

    def test_repr_shows_owner_and_keys(self):
        mem = PrivateMemory(owner="Agent1")
        mem.write("x", 1)
        r = repr(mem)
        assert "Agent1" in r
        assert "x" in r

    def test_can_store_complex_values(self):
        mem = PrivateMemory(owner="TestAgent")
        mem.write("profile", {"instability": 0.3, "vulnerability": 0.6})
        mem.write("list", [1, 2, 3])
        assert mem.read("profile")["instability"] == 0.3
        assert mem.read("list") == [1, 2, 3]


# ── UniversalMemory tests ─────────────────────────────────────────────────────

class TestUniversalMemory:

    def test_update_and_read(self):
        mem = UniversalMemory()
        mem.update("health", {"bpm": 80})
        assert mem.read("health") == {"bpm": 80}

    def test_read_missing_agent_returns_default(self):
        mem = UniversalMemory()
        assert mem.read("nonexistent") is None
        assert mem.read("nonexistent", {}) == {}

    def test_update_overwrites_previous_result(self):
        mem = UniversalMemory()
        mem.update("health", {"bpm": 80})
        mem.update("health", {"bpm": 95})
        assert mem.read("health")["bpm"] == 95

    def test_read_all_returns_only_agent_results(self):
        """
        read_all() must NOT include EnvironmentalContext entries.
        Those are in a separate namespace with a reserved prefix.
        """
        mem = UniversalMemory()
        mem.update("health", {"bpm": 80})
        mem.update("schedule", {"reminders": []})
        ctx = EnvironmentalContext(
            risk_level=RiskLevel.LEVEL_2, location_id="loc_1"
        )
        mem.publish_environmental_context(ctx)
        result = mem.read_all()
        assert "health" in result
        assert "schedule" in result
        # Environmental context should NOT appear in agent results
        assert not any(k.startswith("__env_ctx__") for k in result)
        assert "loc_1" not in result

    def test_history_records_all_updates(self):
        mem = UniversalMemory()
        mem.update("a", {"x": 1})
        mem.update("b", {"y": 2})
        history = mem.get_history()
        assert len(history) >= 2

    def test_repr_shows_agent_domains(self):
        mem = UniversalMemory()
        mem.update("health", {})
        r = repr(mem)
        assert "health" in r

    def test_ethical_filter_intercepts_update(self):
        """
        Every update() call must be intercepted by the EthicalFilter.
        Verify by checking that the audit log grows on each update.
        """
        from sett import EthicalFilter
        f = EthicalFilter()
        mem = UniversalMemory()
        mem.set_ethical_filter(f)
        mem.update("test", {"data": "safe"})
        assert len(f.get_audit_log()) == 1

    # ── Environmental context ─────────────────────────────────────────────

    def test_publish_and_read_environmental_context(self):
        mem = UniversalMemory()
        ctx = EnvironmentalContext(
            risk_level=RiskLevel.LEVEL_3,
            location_id="store_42",
            source_domain="health",
        )
        mem.publish_environmental_context(ctx)
        retrieved = mem.read_environmental_context("store_42")
        assert retrieved is not None
        assert retrieved.risk_level == RiskLevel.LEVEL_3
        assert retrieved.location_id == "store_42"

    def test_read_environmental_context_returns_none_for_unknown_location(self):
        mem = UniversalMemory()
        result = mem.read_environmental_context("unknown_location")
        assert result is None

    def test_multiple_locations_stored_independently(self):
        mem = UniversalMemory()
        mem.publish_environmental_context(EnvironmentalContext(
            risk_level=RiskLevel.LEVEL_1, location_id="zone_a"
        ))
        mem.publish_environmental_context(EnvironmentalContext(
            risk_level=RiskLevel.LEVEL_4, location_id="zone_b"
        ))
        assert mem.read_environmental_context("zone_a").risk_level == RiskLevel.LEVEL_1
        assert mem.read_environmental_context("zone_b").risk_level == RiskLevel.LEVEL_4

    def test_read_all_environmental_contexts(self):
        mem = UniversalMemory()
        mem.publish_environmental_context(EnvironmentalContext(
            risk_level=RiskLevel.LEVEL_2, location_id="alpha"
        ))
        mem.publish_environmental_context(EnvironmentalContext(
            risk_level=RiskLevel.LEVEL_3, location_id="beta"
        ))
        all_ctx = mem.read_all_environmental_contexts()
        assert "alpha" in all_ctx
        assert "beta" in all_ctx
        assert len(all_ctx) == 2

    def test_env_context_update_overwrites_previous(self):
        """A location's context should be updatable — latest wins."""
        mem = UniversalMemory()
        mem.publish_environmental_context(EnvironmentalContext(
            risk_level=RiskLevel.LEVEL_1, location_id="zone"
        ))
        mem.publish_environmental_context(EnvironmentalContext(
            risk_level=RiskLevel.LEVEL_4, location_id="zone"
        ))
        ctx = mem.read_environmental_context("zone")
        assert ctx.risk_level == RiskLevel.LEVEL_4

    # ── Thread safety ─────────────────────────────────────────────────────

    def test_concurrent_writes_do_not_corrupt_state(self):
        """
        Multiple threads writing to UniversalMemory concurrently
        should not corrupt the stored data.
        """
        mem = UniversalMemory()
        errors = []

        def write_many(domain: str):
            try:
                for i in range(50):
                    mem.update(domain, {"count": i})
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=write_many, args=(f"agent_{i}",))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        result = mem.read_all()
        assert len(result) == 5  # 5 agents, each with a result
