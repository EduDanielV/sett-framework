"""
SETT Framework — Action
==============================
An Action is a real-world side effect described as DATA, not as code.

This is the core of the "actions as data" model: an expert never calls
send_sms(...) or charge_payment(...) directly. Instead it returns an
Action describing what it wants to happen. Only the SETTExecutor —
via a handler registered explicitly for that action_type — is allowed
to actually perform the effect, and only after the EthicalFilter
approves it.

This is what makes the guarantee structural rather than a convention:
the expert physically has no reference to the real client (Twilio,
an email SDK, a payment API). It can only describe intent.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone


@dataclass
class Action:
    """
    A proposed real-world side effect, described as data.

    Args:
        action_type: Identifies which registered handler should run this
                     action (e.g. "send_sms", "call_emergency_services",
                     "charge_payment"). Must match a handler registered
                     with SETTExecutor.register_handler().
        payload: Data the handler needs to actually perform the effect
                 (e.g. {"to": "+54...", "message": "..."}).
        proposed_by: The domain of the agent that proposed this action.
                     Used for logging/audit only — never used to identify
                     or expose anything about the end user.
    """
    action_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    proposed_by: str = "unknown"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __repr__(self) -> str:
        return (
            f"Action(action_type={self.action_type!r}, "
            f"proposed_by={self.proposed_by!r})"
        )
