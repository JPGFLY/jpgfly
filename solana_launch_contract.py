"""Pure-data Solana prelaunch boundary for JPGFLY.

This module intentionally cannot contact Solana, read a wallet, load a key,
sign a transaction, invoke a CLI, or broadcast anything. It exists to make the
agent's future token-launch intent deterministic, reviewable, hash-bound, and
safe to hand to a separate local signer boundary later.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class SolanaLaunchContractError(ValueError):
    pass


_POLICY_KEYS = {
    "schema",
    "name",
    "mode",
    "chain",
    "network",
    "operation",
    "execution_enabled",
    "rpc_access",
    "wallet_access",
    "private_key_access",
    "generic_signing",
    "browser_wallet_access",
    "publish_signer_identity",
    "store_private_key",
    "store_seed_phrase",
    "adapter",
    "allowed_program_ids",
    "max_total_lamports",
    "max_transactions",
    "max_launches_per_arm",
    "note",
}

_TOKEN_KEYS = {"name", "symbol", "decimals", "metadata_uri"}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, label: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise SolanaLaunchContractError(f"{label} must be text")
    cleaned = value.strip()
    if len(cleaned.encode("utf-8")) < minimum or len(cleaned.encode("utf-8")) > maximum:
        raise SolanaLaunchContractError(f"{label} must be {minimum}-{maximum} UTF-8 bytes")
    if any(ord(char) < 32 or ord(char) == 127 for char in cleaned):
        raise SolanaLaunchContractError(f"{label} contains control characters")
    return cleaned


def _metadata_uri(value: Any) -> str:
    if value in (None, ""):
        return ""
    uri = _text(value, "metadata_uri", 1, 512)
    lowered = uri.casefold()
    if not (lowered.startswith("https://") or lowered.startswith("ipfs://")):
        raise SolanaLaunchContractError("metadata_uri must use https:// or ipfs://")
    if re.search(r"^[a-z]+://[^/@\s]+@", uri, flags=re.I):
        raise SolanaLaunchContractError("metadata_uri must not contain embedded credentials")
    return uri


def validate_prep_policy(policy: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(policy, dict):
        raise SolanaLaunchContractError("Solana prep policy must be an object")

    unknown = set(policy) - _POLICY_KEYS
    if unknown:
        raise SolanaLaunchContractError(f"unknown Solana prep policy fields: {sorted(unknown)}")

    expected = {
        "schema": 1,
        "mode": "SOLANA_MAINNET_PREP",
        "chain": "solana",
        "network": "mainnet-beta",
        "operation": "SOLANA_TOKEN_CREATE_PREP",
        "execution_enabled": False,
        "rpc_access": False,
        "wallet_access": False,
        "private_key_access": False,
        "generic_signing": False,
        "browser_wallet_access": False,
        "publish_signer_identity": False,
        "store_private_key": False,
        "store_seed_phrase": False,
        "adapter": "UNSET",
        "max_total_lamports": 0,
        "max_transactions": 0,
        "max_launches_per_arm": 1,
    }
    for key, value in expected.items():
        if policy.get(key) != value:
            raise SolanaLaunchContractError(f"Solana prep policy requires {key}={value!r}")

    programs = policy.get("allowed_program_ids")
    if programs != []:
        raise SolanaLaunchContractError("Solana prep policy must not authorize any program ids yet")

    validated = json.loads(json.dumps(policy))
    validated["policy_hash"] = _sha256(policy)
    return validated


def build_solana_prep_intent(token: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    validated_policy = validate_prep_policy(policy)
    if not isinstance(token, dict):
        raise SolanaLaunchContractError("token intent must be an object")

    unknown = set(token) - _TOKEN_KEYS
    if unknown:
        raise SolanaLaunchContractError(f"unknown token intent fields: {sorted(unknown)}")

    name = _text(token.get("name"), "name", 1, 32)
    symbol = _text(token.get("symbol"), "symbol", 1, 10)
    if not re.fullmatch(r"[A-Za-z0-9._$-]+", symbol):
        raise SolanaLaunchContractError("symbol contains unsupported characters")

    decimals = token.get("decimals")
    if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 9:
        raise SolanaLaunchContractError("decimals must be an integer from 0 to 9")

    prepared_token = {
        "name": name,
        "symbol": symbol,
        "decimals": decimals,
        "metadata_uri": _metadata_uri(token.get("metadata_uri")),
    }

    intent = {
        "schema": 1,
        "operation": "SOLANA_TOKEN_CREATE_PREP",
        "chain": "solana",
        "network": "mainnet-beta",
        "token": prepared_token,
        "controls": {
            "execution_enabled": False,
            "broadcast": False,
            "rpc_access": False,
            "wallet_access": False,
            "private_key_access": False,
            "generic_signing": False,
            "browser_wallet_access": False,
            "publish_signer_identity": False,
            "adapter": "UNSET",
            "allowed_program_ids": [],
            "max_total_lamports": 0,
            "max_transactions": 0,
            "max_launches_per_arm": 1,
        },
        "policy_hash": validated_policy["policy_hash"],
    }
    intent["intent_hash"] = _sha256(intent)
    return intent


def public_prep_receipt(intent: dict[str, Any]) -> dict[str, Any]:
    """Return only the public, non-signer portion of a prepared intent."""
    if not isinstance(intent, dict) or intent.get("operation") != "SOLANA_TOKEN_CREATE_PREP":
        raise SolanaLaunchContractError("invalid Solana prep intent")
    token = dict(intent.get("token") or {})
    return {
        "schema": 1,
        "operation": intent.get("operation"),
        "chain": intent.get("chain"),
        "network": intent.get("network"),
        "token": {
            "name": token.get("name"),
            "symbol": token.get("symbol"),
            "decimals": token.get("decimals"),
            "metadata_uri": token.get("metadata_uri"),
        },
        "intent_hash": intent.get("intent_hash"),
        "execution_enabled": False,
        "broadcast": False,
    }
