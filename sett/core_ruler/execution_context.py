"""Immutable execution identity and run-local context propagation.

``ExecutionContext`` carries correlation identifiers through a SETT run.
It deliberately contains no application state and no domain-specific
objects. Contexts are immutable and child operations receive derived
contexts with a new ``run_id`` and a causal ``parent_id``.
"""
from __future__ import annotations

import json
import math
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Generic, TypeAlias, TypeVar
from uuid import UUID, uuid4

from sett.exceptions import SETTValidationError

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]
T = TypeVar("T")

_MAX_METADATA_KEYS = 32
_MAX_METADATA_DEPTH = 8
_MAX_METADATA_BYTES = 16 * 1024
_SENSITIVE_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "api_key",
    "credential",
)

_ACTIVE_CONTEXT: ContextVar[ExecutionContext | None] = ContextVar(
    "sett_execution_context", default=None
)
_ACTIVE_CAUSE_ID: ContextVar[str | None] = ContextVar(
    "sett_trace_cause_id", default=None
)


def _new_id() -> str:
    return str(uuid4())


def _validate_identifier(name: str, value: str | None) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise SETTValidationError(f"{name} must be a non-empty string or None.")
    if len(value) > 255:
        raise SETTValidationError(f"{name} must not exceed 255 characters.")


def _freeze_value(value: Any, depth: int = 0) -> JsonValue:
    if depth > _MAX_METADATA_DEPTH:
        raise SETTValidationError(
            f"ExecutionContext metadata exceeds depth {_MAX_METADATA_DEPTH}."
        )
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SETTValidationError(
                "ExecutionContext metadata numbers must be finite."
            )
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, JsonValue] = {}
        for raw_key, item in value.items():
            if not isinstance(raw_key, str) or not raw_key:
                raise SETTValidationError(
                    "ExecutionContext metadata keys must be non-empty strings."
                )
            lowered = raw_key.lower()
            if lowered.startswith("sett."):
                raise SETTValidationError(
                    "ExecutionContext metadata keys beginning with 'sett.' "
                    "are reserved for the framework."
                )
            if any(fragment in lowered for fragment in _SENSITIVE_FRAGMENTS):
                raise SETTValidationError(
                    f"ExecutionContext metadata key {raw_key!r} is sensitive "
                    "and cannot be used for trace correlation."
                )
            frozen[raw_key] = _freeze_value(item, depth + 1)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item, depth + 1) for item in value)
    raise SETTValidationError(
        "ExecutionContext metadata accepts only JSON-safe values; "
        f"got {type(value).__name__}."
    )


def _thaw_value(value: JsonValue) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return value


def _freeze_metadata(metadata: Mapping[str, Any] | None) -> Mapping[str, JsonValue]:
    raw = dict(metadata or {})
    if len(raw) > _MAX_METADATA_KEYS:
        raise SETTValidationError(
            f"ExecutionContext metadata accepts at most {_MAX_METADATA_KEYS} keys."
        )
    frozen = _freeze_value(raw)
    assert isinstance(frozen, Mapping)
    serialized = json.dumps(
        _thaw_value(frozen),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(serialized) > _MAX_METADATA_BYTES:
        raise SETTValidationError(
            f"ExecutionContext metadata exceeds {_MAX_METADATA_BYTES} bytes."
        )
    return frozen


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Immutable identity for one node in a causal execution tree."""

    trace_id: str = field(default_factory=_new_id)
    run_id: str = field(default_factory=_new_id)
    parent_id: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    application_id: str | None = None
    instance_id: str | None = None
    subject_id: str | None = None
    session_id: str | None = None
    turn_id: str | None = None
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "trace_id",
            "run_id",
            "parent_id",
            "application_id",
            "instance_id",
            "subject_id",
            "session_id",
            "turn_id",
        ):
            _validate_identifier(name, getattr(self, name))
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise SETTValidationError("created_at must be timezone-aware.")
        object.__setattr__(self, "created_at", self.created_at.astimezone(timezone.utc))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    @classmethod
    def create(
        cls,
        *,
        trace_id: str | None = None,
        run_id: str | None = None,
        application_id: str | None = None,
        instance_id: str | None = None,
        subject_id: str | None = None,
        session_id: str | None = None,
        turn_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ExecutionContext:
        """Create a root context, generating identifiers when omitted."""
        return cls(
            trace_id=trace_id or _new_id(),
            run_id=run_id or _new_id(),
            application_id=application_id,
            instance_id=instance_id,
            subject_id=subject_id,
            session_id=session_id,
            turn_id=turn_id,
            metadata=metadata or {},
        )

    def derive(
        self,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> ExecutionContext:
        """Create an immutable child context within the same trace."""
        merged = self.metadata_dict()
        if metadata:
            merged.update(metadata)
        return ExecutionContext(
            trace_id=self.trace_id,
            run_id=_new_id(),
            parent_id=self.run_id,
            application_id=self.application_id,
            instance_id=self.instance_id,
            subject_id=self.subject_id,
            session_id=self.session_id,
            turn_id=self.turn_id,
            metadata=merged,
        )

    def metadata_dict(self) -> dict[str, Any]:
        """Return a mutable defensive copy of safe metadata."""
        return _thaw_value(self.metadata)

    def safe_view(self) -> dict[str, Any]:
        """Return a JSON-safe defensive representation."""
        return {
            "trace_id": self.trace_id,
            "run_id": self.run_id,
            "parent_id": self.parent_id,
            "created_at": self.created_at.isoformat(),
            "application_id": self.application_id,
            "instance_id": self.instance_id,
            "subject_id": self.subject_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "metadata": self.metadata_dict(),
        }


@dataclass(frozen=True, slots=True)
class TracedResult(Generic[T]):
    """Additive result envelope for callers that need explicit trace identity."""

    result: T
    trace_id: str
    context: ExecutionContext


def current_execution_context() -> ExecutionContext | None:
    """Return the context active in this thread/task, if any."""
    return _ACTIVE_CONTEXT.get()


def current_trace_cause_id() -> str | None:
    """Return the event that caused the currently active operation."""
    return _ACTIVE_CAUSE_ID.get()


@contextmanager
def execution_scope(
    context: ExecutionContext,
    cause_id: str | None = None,
) -> Iterator[ExecutionContext]:
    """Bind a context and cause for the duration of one operation."""
    context_token = _ACTIVE_CONTEXT.set(context)
    cause_token = _ACTIVE_CAUSE_ID.set(cause_id)
    try:
        yield context
    finally:
        _ACTIVE_CAUSE_ID.reset(cause_token)
        _ACTIVE_CONTEXT.reset(context_token)


def _is_uuid(value: str) -> bool:
    """Internal validation helper retained for conformance tooling."""
    try:
        UUID(value)
    except (ValueError, AttributeError):
        return False
    return True
