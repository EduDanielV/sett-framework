"""
SETT Framework — StubDomainAgent
==============================
A placeholder agent for a domain that isn't built yet.

Useful when assembling a multi-agent system incrementally: register a
StubDomainAgent for every domain your router or synthesizer needs to
be able to call, so the full turn (dispatch → collect → synthesize)
is testable end to end from day one — even before the real agents for
those domains exist. Swap in the real agent later by registering it
under the same domain name; nothing else in your system needs to
change, because callers only ever depend on the domain string, never
on which concrete agent answers it.

Extracted from a companion-assistant application built on top of SETT — first used to
let a router and a multi-domain synthesizer be built and fully tested
before any of the six domains they route to had a real implementation.

Usage:
    orchestrator.register_agent(StubDomainAgent("health"))
    orchestrator.register_agent(StubDomainAgent("shopping"))
    # ... later, once HealthAgent is ready:
    # orchestrator.register_agent(HealthAgent())  # replaces the stub,
    #                                              # same domain string
"""
from __future__ import annotations
from typing import Any

from sett.core_ruler.agent import SETTAgent


class StubDomainAgent(SETTAgent):
    """
    Recognizes any input for its domain and returns an honest,
    structured "not built yet" result instead of crashing or
    fabricating an answer. A downstream synthesizer (e.g. a
    PhrasingExpert-based one) can narrate this as "that feature isn't
    ready yet" — the same fail-honest spirit as the rest of SETT.

    Args:
        domain: The domain key this stub stands in for (e.g. "health").
        name: Optional human-readable name. Defaults to "Stub[domain]".
    """

    def __init__(self, domain: str, name: str | None = None) -> None:
        super().__init__(name=name or f"Stub[{domain}]", domain=domain)

    def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        result = {
            "status": "stub",
            "domain": self.domain,
            "received": dict(input_data),
        }
        self._publish_to_universal(result)
        return result

    def __repr__(self) -> str:
        return f"StubDomainAgent(domain={self.domain!r})"
