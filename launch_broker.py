"""Strict local launch broker for JPGFLY.

No wallet, network, RPC, signing, or blockchain code is allowed here.
This is the policy boundary that a future chain-specific adapter must sit behind.
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any


class LaunchBrokerError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


_ALLOWED_KEYS = {
    "operation",
    "session_id",
    "policy_hash",
    "build_manifest_hash",
    "intent_hash",
    "human_inputs_after_arm",
}


class LocalMockLaunchBroker:
    def __init__(self, policy: dict[str, Any], state_dir: Path | None = None):
        self.policy = json.loads(json.dumps(policy))
        self.lock = threading.RLock()
        self.state_dir = Path(state_dir) if state_dir is not None else None
        if self.state_dir is not None:
            self.state_dir.mkdir(parents=True, exist_ok=True)

    def _receipt_path(self, session_id: str) -> Path | None:
        if self.state_dir is None:
            return None
        return self.state_dir / f"{session_id}.json"

    def _load_receipt(self, session_id: str) -> dict[str, Any] | None:
        path = self._receipt_path(session_id)
        if path is None or not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise LaunchBrokerError("stored broker receipt is unreadable")
        if not isinstance(value, dict):
            raise LaunchBrokerError("stored broker receipt is invalid")
        return value

    def _store_receipt(self, session_id: str, receipt: dict[str, Any]) -> None:
        path = self._receipt_path(session_id)
        if path is None:
            return
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(_canonical(receipt), encoding="utf-8")
        temporary.replace(path)

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            if not isinstance(request, dict):
                raise LaunchBrokerError("launch broker request must be an object")

            keys = set(request)
            unknown = keys - _ALLOWED_KEYS
            missing = _ALLOWED_KEYS - keys
            if unknown:
                raise LaunchBrokerError(f"unknown launch broker fields: {sorted(unknown)}")
            if missing:
                raise LaunchBrokerError(f"missing launch broker fields: {sorted(missing)}")

            if request["operation"] != "LOCAL_MOCK_TOKEN_LAUNCH":
                raise LaunchBrokerError("operation is not allowed")
            if not isinstance(request["session_id"], str) or len(request["session_id"]) != 32:
                raise LaunchBrokerError("invalid session id")
            if not isinstance(request["intent_hash"], str) or not request["intent_hash"].startswith("sha256:"):
                raise LaunchBrokerError("invalid intent hash")
            if not isinstance(request["build_manifest_hash"], str) or not request["build_manifest_hash"].startswith("sha256:"):
                raise LaunchBrokerError("invalid build manifest hash")
            if not isinstance(request["policy_hash"], str) or not request["policy_hash"].startswith("sha256:"):
                raise LaunchBrokerError("invalid policy hash")
            if int(request["human_inputs_after_arm"]) != 0:
                raise LaunchBrokerError("human input after ARM is not allowed")

            for key in ("network_access", "rpc_access", "wallet_access", "private_key_access", "generic_signing"):
                if self.policy.get(key) is not False:
                    raise LaunchBrokerError(f"unsafe policy capability: {key}")

            if int(self.policy.get("max_launches_per_arm", 0)) != 1:
                raise LaunchBrokerError("broker requires one-shot launch policy")
            request_hash = _sha256(request)
            existing = self._load_receipt(request["session_id"])
            if existing is not None:
                if existing.get("request_hash") != request_hash:
                    raise LaunchBrokerError("launch capability already consumed with a different request")
                recovered = json.loads(json.dumps(existing))
                recovered["recovered"] = True
                return recovered

            result = {
                "schema": 1,
                "broker": "JPGFLY_LOCAL_MOCK_BROKER",
                "result": "LOCAL_PROOF_ONLY",
                "broadcast": False,
                "network_access": False,
                "rpc_access": False,
                "wallet_access": False,
                "private_key_access": False,
                "generic_signing": False,
                "request_hash": request_hash,
                "session_id": request["session_id"],
                "intent_hash": request["intent_hash"],
                "policy_hash": request["policy_hash"],
                "build_manifest_hash": request["build_manifest_hash"],
            }
            result["broker_receipt_hash"] = _sha256(result)
            self._store_receipt(request["session_id"], result)
            return result
