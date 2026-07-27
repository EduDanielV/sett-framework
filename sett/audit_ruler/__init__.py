"""Tamper-evident audit helpers used by SETT's public audit surfaces."""

from sett.audit_ruler.chain import append_chained_entry, verify_chain

__all__ = ["append_chained_entry", "verify_chain"]
