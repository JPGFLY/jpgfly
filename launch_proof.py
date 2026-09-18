"""Independent offline verifier for JPGFLY local launch proof bundles.

This module uses only Python's standard library. It does not import the JPGFLY
server, launch engine, broker, network clients, blockchain libraries, or keys.
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any


REQUIRED_EVENTS = [
    "BUILD_PRECOMMITTED",
    "HUMAN_ARMED_CAPABILITY",
    "SYSTEM_INPUT_BASELINE",
    "AUTONOMY_WINDOW_STARTED",
    "AGENT_DECISION",
    "LAUNCH_INTENT_CREATED",
    "AGENT_LAUNCH_CONTROL_ACTIVATED",
    "BROKER_POLICY_ACCEPTED",
    "LOCAL_MOCK_LAUNCH_CONFIRMED",
]

FORBIDDEN_POLICY_TRUE = (
    "network_access",
    "rpc_access",
    "wallet_access",
    "private_key_access",
    "generic_signing",
)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def verify_event_chain(events: Any, session_id: str) -> tuple[list[str], str | None, list[str]]:
    errors: list[str] = []
    names: list[str] = []
    previous = None

    if not isinstance(events, list):
        return ["events must be a list"], None, names

    for index, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"event {index}: not an object")
            continue
        names.append(str(event.get("event") or ""))
        if event.get("session_id") != session_id:
            errors.append(f"event {index}: session mismatch")
        if event.get("sequence") != index:
            errors.append(f"event {index}: sequence mismatch")
        if event.get("previous_hash") != previous:
            errors.append(f"event {index}: previous hash mismatch")
        core = {
            "session_id": event.get("session_id"),
            "sequence": event.get("sequence"),
            "timestamp": event.get("timestamp"),
            "event": event.get("event"),
            "data": event.get("data"),
            "previous_hash": event.get("previous_hash"),
        }
        expected = sha256_json(core)
        if event.get("hash") != expected:
            errors.append(f"event {index}: hash mismatch")
        previous = event.get("hash")

    return errors, previous, names


def verify_bundle(bundle: Any) -> dict[str, Any]:
    errors: list[str] = []

    if not isinstance(bundle, dict):
        return {
            "verified": False,
            "result": "FAIL",
            "errors": ["bundle must be an object"],
        }

    supplied_bundle_hash = bundle.get("bundle_hash")
    unsigned_bundle = dict(bundle)
    unsigned_bundle.pop("bundle_hash", None)
    calculated_bundle_hash = sha256_json(unsigned_bundle)
    if supplied_bundle_hash != calculated_bundle_hash:
        errors.append("bundle hash mismatch")

    if bundle.get("schema") != 1:
        errors.append("unsupported bundle schema")
    if bundle.get("kind") != "JPGFLY_LOCAL_AUTONOMY_PROOF":
        errors.append("unexpected bundle kind")

    session_id = str(bundle.get("session_id") or "")
    if len(session_id) != 32 or any(ch not in "0123456789abcdef" for ch in session_id.lower()):
        errors.append("invalid session id")

    policy = bundle.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy missing")
        policy = {}
    if policy.get("mode") != "LOCAL_MOCK_ONLY":
        errors.append("policy mode is not LOCAL_MOCK_ONLY")
    for key in FORBIDDEN_POLICY_TRUE:
        if policy.get(key) is not False:
            errors.append(f"unsafe policy capability: {key}")
    if int(policy.get("max_launches_per_arm", 0) or 0) != 1:
        errors.append("policy is not one-shot")
    input_policy = policy.get("system_input_guard")
    if not isinstance(input_policy, dict) or input_policy.get("required") is not True:
        errors.append("system-input guard is not required")
    else:
        if input_policy.get("source") != "WINDOWS_GETLASTINPUTINFO":
            errors.append("unexpected system-input guard source")
        if input_policy.get("records_content") is not False:
            errors.append("system-input guard must not record content")
    policy_hash = sha256_json(policy)

    receipt = bundle.get("receipt")
    if not isinstance(receipt, dict):
        errors.append("receipt missing")
        receipt = {}
    if receipt.get("session_id") != session_id:
        errors.append("receipt session mismatch")
    if receipt.get("policy_hash") != policy_hash:
        errors.append("receipt policy hash mismatch")
    if int(receipt.get("human_inputs_after_arm", -1)) != 0:
        errors.append("receipt reports human input after ARM")
    if receipt.get("human_approval_at_execution") is not False:
        errors.append("receipt reports human approval at execution")
    for key in FORBIDDEN_POLICY_TRUE:
        if receipt.get(key) is not False:
            errors.append(f"unsafe receipt capability: {key}")

    input_guard = receipt.get("system_input_guard")
    if not isinstance(input_guard, dict):
        errors.append("system-input guard receipt missing")
    else:
        baseline = input_guard.get("baseline")
        final = input_guard.get("final")
        if input_guard.get("unchanged") is not True:
            errors.append("system-input marker changed after ARM")
        if input_guard.get("records_content") is not False:
            errors.append("system-input receipt indicates content recording")
        if not isinstance(baseline, dict) or not isinstance(final, dict):
            errors.append("system-input baseline/final snapshot missing")
        else:
            if baseline.get("supported") is not True or final.get("supported") is not True:
                errors.append("system-input sentinel was not supported")
            if baseline.get("source") != "WINDOWS_GETLASTINPUTINFO" or final.get("source") != "WINDOWS_GETLASTINPUTINFO":
                errors.append("system-input source mismatch")
            if baseline.get("records_content") is not False or final.get("records_content") is not False:
                errors.append("system-input snapshot recorded content")
            if baseline.get("last_input_tick_ms") != final.get("last_input_tick_ms"):
                errors.append("system-input baseline/final tick mismatch")

    events = bundle.get("events")
    chain_errors, last_hash, names = verify_event_chain(events, session_id)
    errors.extend(chain_errors)

    positions: list[int] = []
    for name in REQUIRED_EVENTS:
        try:
            positions.append(names.index(name))
        except ValueError:
            errors.append(f"missing event: {name}")
    if len(positions) == len(REQUIRED_EVENTS) and positions != sorted(positions):
        errors.append("required event order is invalid")

    if "HUMAN_INPUT_AFTER_ARM" in names:
        errors.append("browser human input occurred after ARM")
    if "SYSTEM_HUMAN_INPUT_DETECTED" in names:
        errors.append("Windows user input occurred after ARM")
    if "SYSTEM_INPUT_GUARD_FAILED" in names:
        errors.append("system-input sentinel failed during autonomy window")
    if "AUTONOMY_PROOF_INVALIDATED" in names:
        errors.append("autonomy proof was invalidated")
    if names.count("LOCAL_MOCK_LAUNCH_CONFIRMED") != 1:
        errors.append("launch must be confirmed exactly once")
    if receipt.get("receipt_hash") != last_hash:
        errors.append("receipt hash does not match final audit hash")

    precommit = None
    if isinstance(events, list):
        precommit = next(
            (event for event in events if isinstance(event, dict) and event.get("event") == "BUILD_PRECOMMITTED"),
            None,
        )
    manifest = ((precommit or {}).get("data") or {}).get("manifest") if precommit else None
    manifest_hash = ((precommit or {}).get("data") or {}).get("manifest_hash") if precommit else None
    if not isinstance(manifest, dict):
        errors.append("build manifest missing")
        manifest = {}
    else:
        if policy.get("require_git_commit") is True and not manifest.get("git_commit"):
            errors.append("Git commit identity missing from manifest")
        if policy.get("require_clean_tracked_worktree") is True and manifest.get("git_tracked_worktree_clean") is not True:
            errors.append("tracked Git worktree was not clean at ARM")
        manifest_base = dict(manifest)
        embedded_manifest_hash = manifest_base.pop("manifest_hash", None)
        recomputed_manifest_hash = sha256_json(manifest_base)
        if embedded_manifest_hash != recomputed_manifest_hash:
            errors.append("embedded build manifest hash mismatch")
        if manifest_hash != embedded_manifest_hash:
            errors.append("precommit build manifest hash mismatch")
        if receipt.get("build_manifest_hash") != embedded_manifest_hash:
            errors.append("receipt build manifest hash mismatch")
        if manifest.get("policy_hash") != policy_hash:
            errors.append("manifest policy hash mismatch")

    source_snapshot = bundle.get("source_snapshot")
    manifest_files = manifest.get("files") if isinstance(manifest, dict) else None
    bundle_source_snapshot_hash = bundle.get("source_snapshot_hash")
    precommit_source_snapshot_hash = ((precommit or {}).get("data") or {}).get("source_snapshot_hash") if precommit else None
    snapshot_core = {
        "schema": 1,
        "session_id": session_id,
        "manifest_hash": manifest_hash,
        "source_snapshot": source_snapshot,
        "art_policy_snapshot": bundle.get("art_policy_snapshot"),
    }
    calculated_source_snapshot_hash = sha256_json(snapshot_core)
    if bundle_source_snapshot_hash != calculated_source_snapshot_hash:
        errors.append("frozen source snapshot hash mismatch")
    if precommit_source_snapshot_hash != bundle_source_snapshot_hash:
        errors.append("frozen source snapshot does not match BUILD_PRECOMMITTED event")
    if not isinstance(source_snapshot, dict):
        errors.append("source snapshot missing")
        source_snapshot = {}
    if isinstance(manifest_files, dict):
        for name, expected_hash in manifest_files.items():
            snapshot = source_snapshot.get(name)
            if not isinstance(snapshot, str):
                errors.append(f"source snapshot missing: {name}")
                continue
            try:
                raw = base64.b64decode(snapshot, validate=True)
            except Exception:
                errors.append(f"source snapshot is not valid base64: {name}")
                continue
            actual_hash = sha256_bytes(raw)
            if actual_hash != expected_hash:
                errors.append(f"source snapshot hash mismatch: {name}")

    art_policy_expected = manifest.get("art_policy_hash") if isinstance(manifest, dict) else None
    art_policy_snapshot = bundle.get("art_policy_snapshot")
    if art_policy_expected:
        if not isinstance(art_policy_snapshot, str):
            errors.append("art policy snapshot missing")
        else:
            try:
                art_policy_raw = base64.b64decode(art_policy_snapshot, validate=True)
            except Exception:
                errors.append("art policy snapshot is not valid base64")
            else:
                if sha256_bytes(art_policy_raw) != art_policy_expected:
                    errors.append("art policy snapshot hash mismatch")

    final_event = None
    if isinstance(events, list):
        final_event = next(
            (
                event for event in reversed(events)
                if isinstance(event, dict) and event.get("event") == "LOCAL_MOCK_LAUNCH_CONFIRMED"
            ),
            None,
        )
    final_data = (final_event or {}).get("data") or {}
    if final_data.get("broadcast") is not False:
        errors.append("local proof unexpectedly reports broadcast")
    if final_data.get("result") != "LOCAL_PROOF_ONLY":
        errors.append("unexpected local launch result")

    broker_event = None
    if isinstance(events, list):
        broker_event = next(
            (event for event in events if isinstance(event, dict) and event.get("event") == "BROKER_POLICY_ACCEPTED"),
            None,
        )
    broker_data = (broker_event or {}).get("data") or {}
    for key in FORBIDDEN_POLICY_TRUE:
        if broker_data.get(key) is not False:
            errors.append(f"broker did not prove {key}=false")

    passed = not errors
    return {
        "schema": 1,
        "project": "JPGFLY",
        "session_id": session_id,
        "verified": passed,
        "result": "PASS" if passed else "FAIL",
        "errors": errors,
        "bundle_hash": supplied_bundle_hash,
        "calculated_bundle_hash": calculated_bundle_hash,
        "event_count": len(events) if isinstance(events, list) else 0,
        "last_event_hash": last_hash,
        "policy_hash": policy_hash,
        "build_manifest_hash": manifest_hash,
    }
