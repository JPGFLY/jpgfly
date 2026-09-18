"""Fail-closed, privacy-safe launch-day readiness gate for JPGFLY on Solana.

The gate contains only boolean safety facts. It deliberately accepts no wallet
address, signer identity, RPC URL, key material, transaction bytes, or token
funding destination. Those belong behind the separate local signer boundary.
"""
from __future__ import annotations

from typing import Any


class SolanaLaunchReadinessError(ValueError):
    pass


REQUIRED_CHECKS = (
    "local_stack_healthy",
    "gateway_credential_separated",
    "privacy_gate_passed",
    "dependency_gate_passed",
    "production_healthcheck_passed",
    "signer_isolated",
    "signer_secret_outside_repo",
    "signer_secret_outside_railway",
    "adapter_locked",
    "program_allowlist_locked",
    "spend_cap_locked",
    "simulation_passed",
    "one_shot_armed",
)


def evaluate_launch_readiness(facts: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(facts, dict):
        raise SolanaLaunchReadinessError("launch readiness facts must be an object")

    unknown = set(facts) - set(REQUIRED_CHECKS)
    missing = set(REQUIRED_CHECKS) - set(facts)
    if unknown:
        raise SolanaLaunchReadinessError(f"unknown launch readiness fields: {sorted(unknown)}")
    if missing:
        raise SolanaLaunchReadinessError(f"missing launch readiness fields: {sorted(missing)}")

    normalized: dict[str, bool] = {}
    for key in REQUIRED_CHECKS:
        value = facts[key]
        if not isinstance(value, bool):
            raise SolanaLaunchReadinessError(f"{key} must be boolean")
        normalized[key] = value

    blockers = [key for key in REQUIRED_CHECKS if not normalized[key]]
    return {
        "schema": 1,
        "ready": not blockers,
        "checks": normalized,
        "blockers": blockers,
    }
