"""Offline authorization guard for a future JPGFLY Solana signer.

This module is deliberately incapable of signing or broadcasting. It validates
only a small execution-plan summary against an exact local policy. No private
key, seed phrase, RPC URL, wallet identity, raw transaction, or transaction
instruction payload is accepted here.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class SolanaSignerGuardError(ValueError):
    pass


_POLICY_KEYS={
    "schema","name","mode","enabled","chain","network","adapter_id",
    "allowed_program_ids","max_total_lamports","max_transactions",
    "required_intent_hash","required_prep_policy_hash","required_simulation_hash",
    "require_simulation","require_intent_hash","require_policy_hash",
    "allow_arbitrary_recipient","allow_raw_transaction_input",
    "allow_generic_signing","allow_key_export","allow_browser_signing",
    "publish_signer_identity","note",
}

_PLAN_KEYS={
    "intent_hash","prep_policy_hash","adapter_id","program_ids",
    "estimated_total_lamports","transaction_count","simulation_hash",
}

_HASH_RE=re.compile(r"^sha256:[0-9a-f]{64}$")
_PROGRAM_RE=re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


def _canonical(value:Any)->str:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)


def _sha256(value:Any)->str:
    return "sha256:"+hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _require_hash(value:Any,label:str)->str:
    if not isinstance(value,str) or not _HASH_RE.fullmatch(value):
        raise SolanaSignerGuardError(f"{label} must be a sha256 hash")
    return value


def _require_program_ids(value:Any)->list[str]:
    if not isinstance(value,list) or not value:
        raise SolanaSignerGuardError("program_ids must be a non-empty list")
    normalized=[]
    for item in value:
        if not isinstance(item,str) or not _PROGRAM_RE.fullmatch(item):
            raise SolanaSignerGuardError("program_ids contains an invalid Solana program id")
        normalized.append(item)
    if len(normalized)!=len(set(normalized)):
        raise SolanaSignerGuardError("program_ids must not contain duplicates")
    return normalized


def validate_signer_policy(policy:dict[str,Any], *, require_enabled:bool=False)->dict[str,Any]:
    if not isinstance(policy,dict):
        raise SolanaSignerGuardError("signer policy must be an object")
    unknown=set(policy)-_POLICY_KEYS
    if unknown:
        raise SolanaSignerGuardError(f"unknown signer policy fields: {sorted(unknown)}")
    if policy.get("schema")!=1 or policy.get("chain")!="solana" or policy.get("network")!="mainnet-beta":
        raise SolanaSignerGuardError("signer policy chain/network/schema mismatch")
    if policy.get("mode") not in {"LOCKED_TEMPLATE","LOCKED_EXECUTION"}:
        raise SolanaSignerGuardError("unsupported signer policy mode")

    for key in ("require_simulation","require_intent_hash","require_policy_hash"):
        if policy.get(key) is not True:
            raise SolanaSignerGuardError(f"signer policy requires {key}=true")
    for key in (
        "allow_arbitrary_recipient","allow_raw_transaction_input","allow_generic_signing",
        "allow_key_export","allow_browser_signing","publish_signer_identity",
    ):
        if policy.get(key) is not False:
            raise SolanaSignerGuardError(f"signer policy requires {key}=false")

    enabled=policy.get("enabled") is True
    adapter=str(policy.get("adapter_id") or "")
    programs=policy.get("allowed_program_ids")
    max_lamports=policy.get("max_total_lamports")
    max_transactions=policy.get("max_transactions")
    required_hashes={
        "required_intent_hash":policy.get("required_intent_hash"),
        "required_prep_policy_hash":policy.get("required_prep_policy_hash"),
        "required_simulation_hash":policy.get("required_simulation_hash"),
    }
    if isinstance(max_lamports,bool) or not isinstance(max_lamports,int) or max_lamports<0:
        raise SolanaSignerGuardError("max_total_lamports must be a non-negative integer")
    if isinstance(max_transactions,bool) or not isinstance(max_transactions,int) or max_transactions<0:
        raise SolanaSignerGuardError("max_transactions must be a non-negative integer")

    if not enabled:
        if (
            policy.get("mode")!="LOCKED_TEMPLATE" or adapter!="UNSET" or programs!=[]
            or max_lamports!=0 or max_transactions!=0 or any(required_hashes.values())
        ):
            raise SolanaSignerGuardError("disabled signer policy must remain a zero-authority template")
    else:
        if policy.get("mode")!="LOCKED_EXECUTION":
            raise SolanaSignerGuardError("enabled signer policy must use LOCKED_EXECUTION mode")
        if adapter in {"","UNSET"}:
            raise SolanaSignerGuardError("enabled signer policy requires an exact adapter_id")
        _require_program_ids(programs)
        if max_lamports<=0 or max_transactions<=0:
            raise SolanaSignerGuardError("enabled signer policy requires positive spend and transaction caps")
        for key,value in required_hashes.items():
            _require_hash(value,key)

    if require_enabled and not enabled:
        raise SolanaSignerGuardError("signer policy is not enabled")

    result=json.loads(json.dumps(policy))
    result["policy_hash"]=_sha256(policy)
    return result


def authorize_execution_plan(plan:dict[str,Any], policy:dict[str,Any])->dict[str,Any]:
    checked=validate_signer_policy(policy,require_enabled=True)
    if not isinstance(plan,dict):
        raise SolanaSignerGuardError("execution plan must be an object")
    unknown=set(plan)-_PLAN_KEYS
    missing=_PLAN_KEYS-set(plan)
    if unknown:
        raise SolanaSignerGuardError(f"unknown execution plan fields: {sorted(unknown)}")
    if missing:
        raise SolanaSignerGuardError(f"missing execution plan fields: {sorted(missing)}")

    intent_hash=_require_hash(plan.get("intent_hash"),"intent_hash")
    prep_policy_hash=_require_hash(plan.get("prep_policy_hash"),"prep_policy_hash")
    simulation_hash=_require_hash(plan.get("simulation_hash"),"simulation_hash")
    if intent_hash!=checked["required_intent_hash"]:
        raise SolanaSignerGuardError("execution plan intent hash does not match locked policy")
    if prep_policy_hash!=checked["required_prep_policy_hash"]:
        raise SolanaSignerGuardError("execution plan prep policy hash does not match locked policy")
    if simulation_hash!=checked["required_simulation_hash"]:
        raise SolanaSignerGuardError("execution plan simulation hash does not match locked policy")

    adapter=plan.get("adapter_id")
    if adapter!=checked["adapter_id"]:
        raise SolanaSignerGuardError("execution plan adapter does not match locked policy")

    programs=_require_program_ids(plan.get("program_ids"))
    allowed=list(checked["allowed_program_ids"])
    if programs!=allowed:
        raise SolanaSignerGuardError("execution plan program ids do not exactly match locked allowlist")

    lamports=plan.get("estimated_total_lamports")
    tx_count=plan.get("transaction_count")
    if isinstance(lamports,bool) or not isinstance(lamports,int) or lamports<0:
        raise SolanaSignerGuardError("estimated_total_lamports must be a non-negative integer")
    if isinstance(tx_count,bool) or not isinstance(tx_count,int) or tx_count<1:
        raise SolanaSignerGuardError("transaction_count must be a positive integer")
    if lamports>checked["max_total_lamports"]:
        raise SolanaSignerGuardError("execution plan exceeds locked lamport cap")
    if tx_count>checked["max_transactions"]:
        raise SolanaSignerGuardError("execution plan exceeds locked transaction cap")

    receipt={
        "schema":1,
        "authorized":True,
        "intent_hash":intent_hash,
        "prep_policy_hash":prep_policy_hash,
        "signer_policy_hash":checked["policy_hash"],
        "simulation_hash":simulation_hash,
        "adapter_id":adapter,
        "program_ids":programs,
        "estimated_total_lamports":lamports,
        "transaction_count":tx_count,
    }
    receipt["authorization_hash"]=_sha256(receipt)
    return receipt
