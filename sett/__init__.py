"""
SETT Framework
==============================
Scalable Expert-based Task Topology

A multi-agent development framework inspired by the Badger Architecture
(Rosa et al., 2019). SETT applies the philosophy of coordinated expert agents
at a macro scale: pre-designed, domain-specialized agents working under a
single orchestrator, each maintaining independent memory, communicating only
final results through a shared universal memory layer.

Author:  Eduardo Daniel Viñales
Paper:   https://doi.org/10.5281/zenodo.21287133 (EN)
         https://doi.org/10.5281/zenodo.21287355 (ES)
         https://doi.org/10.5281/zenodo.21301700 (JP)
LinkedIn: https://www.linkedin.com/in/edudanielv/

Usage:
    from sett import SETTOrchestrator, SETTAgent, SETTExpert, EthicalFilter
"""

__version__ = "0.6.0"
__author__ = "Eduardo Daniel Viñales"
__license__ = "MIT"

# Core building blocks
from sett.core_ruler.orchestrator import SETTOrchestrator
from sett.core_ruler.agent import SETTAgent
from sett.core_ruler.expert import SETTExpert
from sett.core_ruler.phrasing_expert import PhrasingExpert
from sett.core_ruler.action import Action
from sett.core_ruler.executor import SETTExecutor
from sett.core_ruler.stub_agent import StubDomainAgent
from sett.core_ruler.pipeline import (
    PipelineStep,
    PipelineResult,
    StageOutcome,
    RejectionOutcome,
)

# Memory layers
from sett.memory_ruler.universal import UniversalMemory
from sett.memory_ruler.private import PrivateMemory

# Ethics governance layer
from sett.ethics_ruler.ethic_kernel.filter import EthicalFilter, FilterVerdict
from sett.ethics_ruler.ethic_kernel.rules import (
    EthicalRuleset,
    EthicalRule,
    HarmCategory,
    default_ruleset,
)
from sett.ethics_ruler.ethic_kernel.context_analyzer import ContextAnalyzer

# Risk system — three-layer hybrid evaluation
from sett.risk_ruler.risk_level import RiskLevel
from sett.risk_ruler.risk_profile import RiskProfile
from sett.risk_ruler.environmental_context import EnvironmentalContext

# LLM adapters
from sett.services_llm.base import LLMBase

# Exceptions
from sett.exceptions import (
    SETTError,
    SETTEthicalFilterRejectedError,
    SETTEthicalFilterWarningError,
    SETTMemoryAccessDeniedError,
    SETTAgentNotFoundError,
    SETTExpertNotFoundError,
    SETTLLMAdapterError,
    SETTServiceAdapterError,
    SETTConfigurationError,
)

__all__ = [
    # Core
    "SETTOrchestrator",
    "SETTAgent",
    "SETTExpert",
    "PhrasingExpert",
    "Action",
    "SETTExecutor",
    "StubDomainAgent",
    "PipelineStep",
    "PipelineResult",
    "StageOutcome",
    "RejectionOutcome",
    # Memory
    "UniversalMemory",
    "PrivateMemory",
    # Ethics
    "EthicalFilter",
    "FilterVerdict",
    "EthicalRuleset",
    "EthicalRule",
    "HarmCategory",
    "default_ruleset",
    "ContextAnalyzer",
    # Risk system
    "RiskLevel",
    "RiskProfile",
    "EnvironmentalContext",
    # LLM
    "LLMBase",
    # Exceptions
    "SETTError",
    "SETTEthicalFilterRejectedError",
    "SETTEthicalFilterWarningError",
    "SETTMemoryAccessDeniedError",
    "SETTAgentNotFoundError",
    "SETTExpertNotFoundError",
    "SETTLLMAdapterError",
    "SETTServiceAdapterError",
    "SETTConfigurationError",
]
