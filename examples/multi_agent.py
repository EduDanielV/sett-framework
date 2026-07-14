"""
SETT Framework — Multi-Agent Example
==============================
A SETT system with multiple specialized agents working under one orchestrator.

This example simulates a personal assistant scenario with three agents:
- HealthAgent: monitors biometric data
- ScheduleAgent: manages appointments and reminders
- EnvironmentAgent: tracks weather and ambient conditions

The orchestrator broadcasts the user context to all agents,
each processes independently, and the orchestrator synthesizes
the final response from universal memory.

Run with:
    cd sett-framework
    PYTHONPATH=. python examples/multi_agent.py
"""
from sett import (
    SETTOrchestrator,
    SETTAgent,
    SETTExpert,
    EthicalFilter,
)


# ── HEALTH AGENT ────────────────────────────────────────────────────────────

class HeartRateExpert(SETTExpert):
    """Evaluates heart rate from biometric data."""

    def resolve(self, context):
        bpm = context.get("heart_rate_bpm")
        if bpm is None:
            return {"heart_rate": "no data"}

        if bpm < 60:
            status = "low"
        elif bpm <= 100:
            status = "normal"
        elif bpm <= 140:
            status = "elevated"
        else:
            status = "high"

        if self._private_memory:
            self._private_memory.write("heart_rate_bpm", bpm)
            self._private_memory.write("heart_rate_status", status)

        return {"heart_rate_bpm": bpm, "heart_rate_status": status}


class TemperatureExpert(SETTExpert):
    """Evaluates body temperature from biometric data."""

    def resolve(self, context):
        temp = context.get("temperature_celsius")
        if temp is None:
            return {"temperature": "no data"}

        if temp < 36.0:
            status = "hypothermia risk"
        elif temp <= 37.5:
            status = "normal"
        elif temp <= 38.5:
            status = "low fever"
        else:
            status = "high fever"

        if self._private_memory:
            self._private_memory.write("temperature_celsius", temp)
            self._private_memory.write("temperature_status", status)

        return {"temperature_celsius": temp, "temperature_status": status}


class HealthAgent(SETTAgent):
    """
    Health monitoring agent.
    Combines heart rate and temperature data to produce a health summary.
    """

    def __init__(self):
        super().__init__(name="HealthAgent", domain="health")
        self.register_expert(HeartRateExpert(name="heart_rate"))
        self.register_expert(TemperatureExpert(name="temperature"))

    def process(self, input_data):
        hr = self.get_expert("heart_rate").resolve(input_data)
        temp = self.get_expert("temperature").resolve(input_data)

        # Determine overall health status from private memory
        hr_status = self._private_memory.read("heart_rate_status", "unknown")
        temp_status = self._private_memory.read("temperature_status", "unknown")

        alert = hr_status in ("high", "low") or "fever" in temp_status

        final = {
            **hr, **temp,
            "health_alert": alert,
            "summary": (
                "⚠ Health alert detected." if alert
                else "All health indicators within normal range."
            )
        }
        self._publish_to_universal(final)
        return final


# ── SCHEDULE AGENT ──────────────────────────────────────────────────────────

class AppointmentExpert(SETTExpert):
    """Checks for upcoming appointments from the user's schedule."""

    # In a real system, this would query a calendar service
    MOCK_APPOINTMENTS = [
        {"time": "10:00", "description": "Doctor appointment - Dr. García"},
        {"time": "15:30", "description": "Medication reminder - take blood pressure pill"},
    ]

    def resolve(self, context):
        if self._private_memory:
            self._private_memory.write(
                "appointments", self.MOCK_APPOINTMENTS
            )
        return {"upcoming_appointments": self.MOCK_APPOINTMENTS}


class ReminderExpert(SETTExpert):
    """Generates reminder messages based on appointments."""

    def resolve(self, context):
        appointments = self._private_memory.read("appointments", []) if self._private_memory else []
        reminders = [
            f"Reminder at {a['time']}: {a['description']}"
            for a in appointments
        ]
        return {"reminders": reminders}


class ScheduleAgent(SETTAgent):
    """
    Schedule management agent.
    Reads appointments and produces actionable reminders.
    """

    def __init__(self):
        super().__init__(name="ScheduleAgent", domain="schedule")
        self.register_expert(AppointmentExpert(name="appointments"))
        self.register_expert(ReminderExpert(name="reminders"))

    def process(self, input_data):
        self.get_expert("appointments").resolve(input_data)
        reminders = self.get_expert("reminders").resolve(input_data)
        final = {
            **reminders,
            "schedule_summary": f"{len(reminders['reminders'])} reminder(s) for today."
        }
        self._publish_to_universal(final)
        return final


# ── ENVIRONMENT AGENT ────────────────────────────────────────────────────────

class WeatherExpert(SETTExpert):
    """Provides weather conditions for the user's location."""

    def resolve(self, context):
        city = context.get("city", "Unknown")
        # In a real system, this would call a weather API
        mock_weather = {
            "city": city,
            "condition": "partly cloudy",
            "temperature_celsius": 18,
            "humidity_percent": 65,
            "rain_probability_percent": 20,
        }
        if self._private_memory:
            self._private_memory.write("weather", mock_weather)
        return {"weather": mock_weather}


class AmbientExpert(SETTExpert):
    """Generates a human-readable ambient context summary."""

    def resolve(self, context):
        weather = self._private_memory.read("weather", {}) if self._private_memory else {}
        condition = weather.get("condition", "unknown")
        temp = weather.get("temperature_celsius", "?")
        rain = weather.get("rain_probability_percent", 0)

        summary = f"It's {temp}°C and {condition} in {weather.get('city', 'your city')}."
        if rain > 50:
            summary += " Consider bringing an umbrella."

        return {"ambient_summary": summary}


class EnvironmentAgent(SETTAgent):
    """
    Environmental awareness agent.
    Monitors weather and ambient conditions around the user.
    """

    def __init__(self):
        super().__init__(name="EnvironmentAgent", domain="environment")
        self.register_expert(WeatherExpert(name="weather"))
        self.register_expert(AmbientExpert(name="ambient"))

    def process(self, input_data):
        self.get_expert("weather").resolve(input_data)
        ambient = self.get_expert("ambient").resolve(input_data)
        self._publish_to_universal(ambient)
        return ambient


# ── BUILD THE SYSTEM AND RUN ─────────────────────────────────────────────────

if __name__ == "__main__":
    # Build the orchestrator
    orchestrator = SETTOrchestrator(ethical_filter=EthicalFilter())

    # Register all agents
    orchestrator.register_agent(HealthAgent())
    orchestrator.register_agent(ScheduleAgent())
    orchestrator.register_agent(EnvironmentAgent())

    print(f"Registered agents: {orchestrator.registered_domains}\n")

    # Simulate user context — in AIDA this would come from
    # wearable sensors, user profile, and location services
    user_context = {
        "heart_rate_bpm": 88,
        "temperature_celsius": 37.1,
        "city": "Buenos Aires",
    }

    # Broadcast to ALL agents at once (no domain specified)
    print("── Broadcasting to all agents ──────────────────")
    all_results = orchestrator.process(input_data=user_context)

    for domain, result in all_results.items():
        print(f"\n[{domain.upper()}]")
        for key, value in result.items():
            print(f"  {key}: {value}")

    # Universal memory — everything the orchestrator knows
    print("\n── Universal Memory snapshot ───────────────────")
    memory = orchestrator.read_universal_memory()
    for domain, state in memory.items():
        alert = state.get("health_alert", False)
        marker = "⚠" if alert else "✓"
        print(f"  {marker} {domain}: {list(state.keys())}")

    # Route a second query to a specific agent
    print("\n── Targeted query to HealthAgent ───────────────")
    health_result = orchestrator.process(
        input_data={"heart_rate_bpm": 155, "temperature_celsius": 39.8},
        domain="health"
    )
    print(f"  summary: {health_result['summary']}")
    print(f"  health_alert: {health_result['health_alert']}")

    print("\n── Ethical Audit Log ───────────────────────────")
    for entry in orchestrator.get_ethical_audit_log():
        print(
            f"  [{entry['verdict'].upper()}] "
            f"score={entry['harm_score']:.1f} "
            f"human_at_risk={entry['human_at_risk']}"
        )
