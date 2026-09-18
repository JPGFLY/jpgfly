"""Local-only autonomous launch proof harness for JPGFLY.

This module intentionally contains no blockchain client, RPC URL, wallet SDK,
private key handling, or generic signing primitive. It exists only to prove the
agent -> UI -> restricted capability -> tamper-evident receipt flow locally.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from launch_broker import LocalMockLaunchBroker, LaunchBrokerError


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str | None:
    try:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _git_commit(repo_root: Path) -> str | None:
    git_dir = repo_root / ".git"
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if head.startswith("ref: "):
        ref = head[5:].strip()
        ref_path = git_dir / ref
        try:
            return ref_path.read_text(encoding="utf-8").strip() or None
        except OSError:
            packed = git_dir / "packed-refs"
            try:
                for line in packed.read_text(encoding="utf-8").splitlines():
                    if not line or line.startswith("#") or line.startswith("^"):
                        continue
                    sha, name = line.split(" ", 1)
                    if name.strip() == ref:
                        return sha.strip()
            except (OSError, ValueError):
                return None
            return None
    return head or None


def _git_tracked_worktree_clean(repo_root: Path) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return not bool(result.stdout.strip())


class LaunchLabError(RuntimeError):
    pass


class LaunchLabManager:
    def __init__(self, root: Path, policy_path: Path):
        self.root = Path(root)
        self.policy_path = Path(policy_path)
        self.repo_root = Path(__file__).resolve().parent
        self.lock = threading.RLock()
        self.rng = secrets.SystemRandom()
        self.policy = self._load_policy()
        self.policy_hash = _sha256(self.policy)
        self.broker = LocalMockLaunchBroker(self.policy, self.root / "launch" / "broker")
        self.sessions_dir = self.root / "launch" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir = self.root / "launch" / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.bundles_dir = self.root / "launch" / "bundles"
        self.bundles_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir = self.root / "launch" / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_state_path = self.runtime_dir / "current.json"
        self.state = self._idle_state()
        self._recover_runtime_state()

    def _persist_runtime_state(self) -> None:
        payload = {
            "schema": 1,
            "policy_hash": self.policy_hash,
            "state": json.loads(json.dumps(self.state)),
        }
        payload["snapshot_hash"] = _sha256(payload)
        temporary = self.runtime_state_path.with_suffix(".json.tmp")
        temporary.write_text(_canonical(payload), encoding="utf-8")
        temporary.replace(self.runtime_state_path)

    def _validate_event_chain(self, events: list[dict[str, Any]], session_id: str) -> tuple[list[str], str | None]:
        errors: list[str] = []
        previous = None
        for index, event in enumerate(events):
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
            expected = _sha256(core)
            if event.get("hash") != expected:
                errors.append(f"event {index}: hash mismatch")
            previous = event.get("hash")
        return errors, previous

    def _recover_runtime_state(self) -> None:
        if not self.runtime_state_path.is_file():
            return
        try:
            payload = json.loads(self.runtime_state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise LaunchLabError("launch runtime snapshot is unreadable") from exc
        if not isinstance(payload, dict):
            raise LaunchLabError("launch runtime snapshot is invalid")
        supplied_hash = payload.get("snapshot_hash")
        unsigned = dict(payload)
        unsigned.pop("snapshot_hash", None)
        if supplied_hash != _sha256(unsigned):
            raise LaunchLabError("launch runtime snapshot hash mismatch")
        if payload.get("policy_hash") != self.policy_hash:
            # Policy changed after the last run. Preserve old audit files but do not
            # revive a session under different rules.
            self.state = self._idle_state()
            self._persist_runtime_state()
            return
        recovered = payload.get("state")
        if not isinstance(recovered, dict):
            raise LaunchLabError("launch runtime state is invalid")
        session_id = recovered.get("session_id")
        if not session_id:
            self.state = self._idle_state()
            return
        events = self._read_session_events(str(session_id))
        errors, last_hash = self._validate_event_chain(events, str(session_id))
        if errors:
            raise LaunchLabError("launch audit chain is corrupt: " + "; ".join(errors[:4]))
        if recovered.get("last_event_hash") != last_hash:
            raise LaunchLabError("launch runtime snapshot does not match audit chain")
        recovered["events"] = events
        self.state = recovered

        recovered_state = str(self.state.get("state") or "")
        if recovered_state in {"ARMED", "DECIDED"}:
            self.state["state"] = "BLOCKED_RESTART"
            self._append_event(
                "PROCESS_RESTART_RECOVERED",
                {"state_before_restart": recovered_state},
            )
            self._append_event(
                "AUTONOMY_PROOF_INVALIDATED",
                {"reason": "process restarted during active autonomy window"},
            )
        else:
            self._persist_runtime_state()

    def _load_policy(self) -> dict[str, Any]:
        policy = json.loads(self.policy_path.read_text(encoding="utf-8"))
        required_false = (
            "network_access",
            "rpc_access",
            "wallet_access",
            "private_key_access",
            "generic_signing",
        )
        if str(policy.get("mode")) != "LOCAL_MOCK_ONLY":
            raise LaunchLabError("launch policy must be LOCAL_MOCK_ONLY")
        for key in required_false:
            if policy.get(key) is not False:
                raise LaunchLabError(f"local launch policy requires {key}=false")
        if int(policy.get("max_launches_per_arm", 0)) != 1:
            raise LaunchLabError("local launch policy requires max_launches_per_arm=1")
        return policy

    def _tracked_source_paths(self) -> dict[str, Path]:
        return {
            "launch_lab.py": self.repo_root / "launch_lab.py",
            "launch_broker.py": self.repo_root / "launch_broker.py",
            "launch_proof.py": self.repo_root / "launch_proof.py",
            "local_input_guard.py": self.repo_root / "local_input_guard.py",
            "verify_launch_bundle.py": self.repo_root / "verify_launch_bundle.py",
            "launch_policy.local.json": self.policy_path,
            "app.py": self.repo_root / "app.py",
            "web/launch-lab.html": self.repo_root / "web" / "launch-lab.html",
            "web/launch-lab.js": self.repo_root / "web" / "launch-lab.js",
            "web/launch-lab.css": self.repo_root / "web" / "launch-lab.css",
            "web/launch-proof.html": self.repo_root / "web" / "launch-proof.html",
            "web/launch-proof.js": self.repo_root / "web" / "launch-proof.js",
            "web/launch-proof.css": self.repo_root / "web" / "launch-proof.css",
            "web/main-character.mjs": self.repo_root / "web" / "main-character.mjs",
            "web/art-engine.mjs": self.repo_root / "web" / "art-engine.mjs",
            "scripts/check-launch-lab.ps1": self.repo_root / "scripts" / "check-launch-lab.ps1",
            ".github/workflows/launch-lab-security.yml": self.repo_root / ".github" / "workflows" / "launch-lab-security.yml",
        }

    def _build_manifest(self) -> dict[str, Any]:
        tracked = self._tracked_source_paths()
        files = {name: _file_sha256(path) for name, path in tracked.items()}
        missing = sorted(name for name, digest in files.items() if digest is None)
        if missing:
            raise LaunchLabError("proof-critical source files are missing: " + ", ".join(missing))

        art_policy_path = self.root / "art-policy-v2.json"
        art_policy_hash = _file_sha256(art_policy_path)
        if art_policy_hash is None:
            raise LaunchLabError("trained art policy file is missing")

        git_commit = _git_commit(self.repo_root)
        git_clean = _git_tracked_worktree_clean(self.repo_root)
        if self.policy.get("require_git_commit") is True and not git_commit:
            raise LaunchLabError("Git commit identity is unavailable")
        if self.policy.get("require_clean_tracked_worktree") is True and git_clean is not True:
            raise LaunchLabError("tracked Git worktree must be clean before ARM")

        manifest = {
            "git_commit": git_commit,
            "git_tracked_worktree_clean": git_clean,
            "policy_hash": self.policy_hash,
            "files": files,
            "art_policy_hash": art_policy_hash,
        }
        manifest["manifest_hash"] = _sha256(manifest)
        return manifest

    def _snapshot_path(self, session_id: str) -> Path:
        return self.snapshots_dir / f"{session_id}.json"

    def _bundle_path(self, session_id: str) -> Path:
        return self.bundles_dir / f"{session_id}.json"

    def _freeze_precommit_snapshot(self, session_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
        source_snapshot: dict[str, str] = {}
        tracked = self._tracked_source_paths()
        manifest_files = manifest.get("files") or {}
        for name, expected_hash in manifest_files.items():
            path = tracked.get(name)
            if path is None or not path.is_file():
                raise LaunchLabError(f"proof source is unavailable at ARM: {name}")
            raw = path.read_bytes()
            if "sha256:" + hashlib.sha256(raw).hexdigest() != expected_hash:
                raise LaunchLabError(f"proof source changed while ARM was being prepared: {name}")
            source_snapshot[name] = base64.b64encode(raw).decode("ascii")

        art_policy_path = self.root / "art-policy-v2.json"
        if not art_policy_path.is_file():
            raise LaunchLabError("trained art policy file is unavailable at ARM")
        art_policy_raw = art_policy_path.read_bytes()
        if "sha256:" + hashlib.sha256(art_policy_raw).hexdigest() != manifest.get("art_policy_hash"):
            raise LaunchLabError("trained art policy changed while ARM was being prepared")

        snapshot = {
            "schema": 1,
            "session_id": session_id,
            "manifest_hash": manifest.get("manifest_hash"),
            "source_snapshot": source_snapshot,
            "art_policy_snapshot": base64.b64encode(art_policy_raw).decode("ascii"),
        }
        snapshot["snapshot_hash"] = _sha256(snapshot)
        path = self._snapshot_path(session_id)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(_canonical(snapshot), encoding="utf-8")
        temporary.replace(path)
        return snapshot

    def _load_precommit_snapshot(self, session_id: str, expected_hash: str | None = None) -> dict[str, Any]:
        path = self._snapshot_path(session_id)
        if not path.is_file():
            raise LaunchLabError("frozen precommit source snapshot is missing")
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise LaunchLabError("frozen precommit source snapshot is unreadable") from exc
        if not isinstance(snapshot, dict):
            raise LaunchLabError("frozen precommit source snapshot is invalid")
        supplied = snapshot.get("snapshot_hash")
        unsigned = dict(snapshot)
        unsigned.pop("snapshot_hash", None)
        calculated = _sha256(unsigned)
        if supplied != calculated:
            raise LaunchLabError("frozen precommit source snapshot hash mismatch")
        if expected_hash is not None and supplied != expected_hash:
            raise LaunchLabError("frozen precommit source snapshot does not match audit commitment")
        if snapshot.get("session_id") != session_id:
            raise LaunchLabError("frozen precommit source snapshot session mismatch")
        return snapshot

    def _agent_readiness(self, context: dict[str, Any] | None) -> dict[str, Any]:
        context = dict(context or {})
        requirements = dict(self.policy.get("agent_readiness") or {})
        art = dict(context.get("art_policy") or {})
        allowed_states = set(requirements.get("allowed_studio_states") or [])

        checks = {
            "brain_version_present": bool(str(context.get("brain_version") or "").strip()),
            "studio_state_allowed": not allowed_states or str(context.get("studio_state") or "") in allowed_states,
            "art_policy_available": (
                art.get("available") is True
                if requirements.get("require_art_policy_available") is True
                else True
            ),
            "art_rooms_ready": int(art.get("rooms_trained", 0) or 0) >= int(requirements.get("min_art_rooms", 0) or 0),
            "art_samples_ready": int(art.get("samples_trained", 0) or 0) >= int(requirements.get("min_art_samples", 0) or 0),
            "art_confidence_ready": float(art.get("confidence", 0.0) or 0.0) >= float(requirements.get("min_art_confidence", 0.0) or 0.0),
        }
        return {
            "ready": all(checks.values()),
            "checks": checks,
            "requirements": requirements,
            "observed": {
                "brain_version": context.get("brain_version"),
                "studio_state": context.get("studio_state"),
                "studio_decisions": context.get("studio_decisions"),
                "art_policy": {
                    "available": art.get("available"),
                    "rooms_trained": art.get("rooms_trained"),
                    "samples_trained": art.get("samples_trained"),
                    "confidence": art.get("confidence"),
                    "mean_reward": art.get("mean_reward"),
                },
            },
        }

    def _system_input_snapshot_from_context(self, context: dict[str, Any] | None) -> dict[str, Any]:
        raw = dict((context or {}).get("system_input") or {})
        return {
            "supported": raw.get("supported") is True,
            "source": str(raw.get("source") or ""),
            "last_input_tick_ms": raw.get("last_input_tick_ms"),
            "records_content": raw.get("records_content") is True,
        }

    def _validate_system_input_baseline(self, context: dict[str, Any] | None) -> dict[str, Any]:
        guard = dict(self.policy.get("system_input_guard") or {})
        snapshot = self._system_input_snapshot_from_context(context)
        if guard.get("required") is not True:
            return snapshot
        if snapshot.get("supported") is not True:
            raise LaunchLabError("required Windows system-input sentinel is unavailable")
        if snapshot.get("source") != str(guard.get("source") or ""):
            raise LaunchLabError("unexpected system-input sentinel source")
        if snapshot.get("records_content") is not False:
            raise LaunchLabError("system-input sentinel must not record input content")
        tick = snapshot.get("last_input_tick_ms")
        if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
            raise LaunchLabError("system-input sentinel returned an invalid tick")
        return snapshot

    def _check_system_input_guard(self, context: dict[str, Any] | None) -> bool:
        guard = dict(self.policy.get("system_input_guard") or {})
        if guard.get("required") is not True:
            return True
        baseline = dict(self.state.get("system_input_baseline") or {})
        current = self._system_input_snapshot_from_context(context)
        self.state["system_input_final"] = current

        valid_current = (
            current.get("supported") is True
            and current.get("source") == str(guard.get("source") or "")
            and current.get("records_content") is False
            and isinstance(current.get("last_input_tick_ms"), int)
            and not isinstance(current.get("last_input_tick_ms"), bool)
        )
        if not valid_current:
            self.state["state"] = "BLOCKED_INPUT_GUARD"
            self._append_event(
                "SYSTEM_INPUT_GUARD_FAILED",
                {"current": current},
            )
            self._append_event(
                "AUTONOMY_PROOF_INVALIDATED",
                {"reason": "system-input sentinel became unavailable or invalid"},
            )
            return False

        if current.get("last_input_tick_ms") != baseline.get("last_input_tick_ms"):
            self.state["human_inputs_after_arm"] = int(self.state.get("human_inputs_after_arm", 0) or 0) + 1
            self.state["state"] = "BLOCKED_HUMAN_INPUT"
            self._append_event(
                "SYSTEM_HUMAN_INPUT_DETECTED",
                {
                    "baseline_last_input_tick_ms": baseline.get("last_input_tick_ms"),
                    "current_last_input_tick_ms": current.get("last_input_tick_ms"),
                    "source": current.get("source"),
                    "records_content": False,
                },
            )
            self._append_event(
                "AUTONOMY_PROOF_INVALIDATED",
                {"reason": "Windows last-input marker changed after ARM"},
            )
            return False

        return True

    def _idle_state(self) -> dict[str, Any]:
        return {
            "mode": "LOCAL_MOCK_ONLY",
            "state": "IDLE",
            "session_id": None,
            "armed_at": None,
            "decision_due_at": None,
            "decided_at": None,
            "confirmed_at": None,
            "human_inputs_after_arm": 0,
            "agent_actions": 0,
            "launches": 0,
            "intent_hash": None,
            "activation_due_at": None,
            "receipt_hash": None,
            "last_event_hash": None,
            "build_manifest": None,
            "build_manifest_hash": None,
            "source_snapshot_hash": None,
            "proof_bundle_hash": None,
            "readiness": None,
            "system_input_baseline": None,
            "system_input_final": None,
            "events": [],
            "stack": {},
            "proof": {
                "human_approval_at_execution": False,
                "human_launch_control": False,
                "network_access": False,
                "rpc_access": False,
                "wallet_access": False,
                "private_key_access": False,
                "generic_signing": False,
                "policy_hash": self.policy_hash,
            },
        }

    def _session_path(self) -> Path:
        sid = self.state.get("session_id")
        if not sid:
            raise LaunchLabError("no active launch session")
        return self.sessions_dir / f"{sid}.jsonl"

    def _append_event(self, event: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        data = dict(data or {})
        previous_hash = self.state.get("last_event_hash")
        record_core = {
            "session_id": self.state.get("session_id"),
            "sequence": len(self.state["events"]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": str(event),
            "data": data,
            "previous_hash": previous_hash,
        }
        record = dict(record_core)
        record["hash"] = _sha256(record_core)
        self.state["last_event_hash"] = record["hash"]
        self.state["events"].append(record)
        path = self._session_path()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(record))
            handle.write(chr(10))
        self._persist_runtime_state()
        return record

    def _public_state(self) -> dict[str, Any]:
        state = json.loads(json.dumps(self.state))
        state["policy"] = self.policy
        state["events"] = state.get("events", [])[-80:]
        return state

    def status(self) -> dict[str, Any]:
        with self.lock:
            return self._public_state()

    def arm(self, stack: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            if self.state.get("state") in {"ARMED", "DECIDED"}:
                raise LaunchLabError("launch lab is already armed")
            delay_config = dict(self.policy.get("decision_delay_seconds") or {})
            low = max(1.0, float(delay_config.get("min", 6)))
            high = max(low, float(delay_config.get("max", 12)))
            delay = self.rng.uniform(low, high)
            now = datetime.now(timezone.utc)
            session_id = secrets.token_hex(16)
            build_manifest = self._build_manifest()
            system_input_baseline = self._validate_system_input_baseline(context)
            precommit_snapshot = self._freeze_precommit_snapshot(session_id, build_manifest)
            self.state = self._idle_state()
            self.state.update(
                state="ARMED",
                session_id=session_id,
                armed_at=now.isoformat(),
                decision_due_at=time.time() + delay,
                stack=dict(stack or {}),
                build_manifest=build_manifest,
                build_manifest_hash=build_manifest["manifest_hash"],
                source_snapshot_hash=precommit_snapshot["snapshot_hash"],
                system_input_baseline=system_input_baseline,
                system_input_final=system_input_baseline,
            )
            self._append_event(
                "BUILD_PRECOMMITTED",
                {
                    "manifest": build_manifest,
                    "manifest_hash": build_manifest["manifest_hash"],
                    "source_snapshot_hash": precommit_snapshot["snapshot_hash"],
                },
            )
            self._append_event(
                "HUMAN_ARMED_CAPABILITY",
                {
                    "policy_hash": self.policy_hash,
                    "mode": "LOCAL_MOCK_ONLY",
                    "decision_delay_seconds": round(delay, 3),
                    "context": dict(context or {}),
                },
            )
            self._append_event(
                "SYSTEM_INPUT_BASELINE",
                {
                    "source": system_input_baseline.get("source"),
                    "last_input_tick_ms": system_input_baseline.get("last_input_tick_ms"),
                    "records_content": False,
                },
            )
            self._append_event(
                "AUTONOMY_WINDOW_STARTED",
                {
                    "human_inputs_after_arm": 0,
                    "human_approval_at_execution": False,
                },
            )
            return self._public_state()

    def reset(self) -> dict[str, Any]:
        with self.lock:
            if self.state.get("session_id"):
                self._append_event("HUMAN_RESET", {"state_before_reset": self.state.get("state")})
            self.state = self._idle_state()
            self._persist_runtime_state()
            return self._public_state()

    def record_human_input(self, kind: str) -> dict[str, Any]:
        with self.lock:
            if self.state.get("state") not in {"ARMED", "DECIDED"}:
                return self._public_state()
            self.state["human_inputs_after_arm"] += 1
            self._append_event(
                "HUMAN_INPUT_AFTER_ARM",
                {
                    "kind": str(kind)[:48],
                    "count": self.state["human_inputs_after_arm"],
                },
            )
            if self.policy.get("block_on_human_input_after_arm") is True:
                self.state["state"] = "BLOCKED_HUMAN_INPUT"
                self._append_event(
                    "AUTONOMY_PROOF_INVALIDATED",
                    {"reason": "human input occurred after ARM"},
                )
            return self._public_state()

    def _execute_locked(self) -> None:
        if self.state.get("state") != "DECIDED":
            raise LaunchLabError("no autonomous launch decision is pending")
        if self.state.get("human_inputs_after_arm") != 0:
            raise LaunchLabError("human input occurred after ARM")
        if self.state.get("launches", 0) >= 1:
            raise LaunchLabError("one-launch policy already consumed")
        if any(
            self.policy.get(key) is not False
            for key in ("network_access", "rpc_access", "wallet_access", "private_key_access", "generic_signing")
        ):
            raise LaunchLabError("local-only launch policy boundary violated")

        self.state["agent_actions"] += 1
        self._append_event(
            "AGENT_LAUNCH_CONTROL_ACTIVATED",
            {
                "intent_hash": self.state.get("intent_hash"),
                "human_inputs_after_arm": 0,
                "activation": "server-side autonomous one-time capability",
            },
        )

        broker_request = {
            "operation": "LOCAL_MOCK_TOKEN_LAUNCH",
            "session_id": self.state["session_id"],
            "policy_hash": self.policy_hash,
            "build_manifest_hash": self.state.get("build_manifest_hash"),
            "intent_hash": self.state.get("intent_hash"),
            "human_inputs_after_arm": 0,
        }
        try:
            broker_result = self.broker.execute(broker_request)
        except LaunchBrokerError as exc:
            self.state["state"] = "BROKER_REJECTED"
            self._append_event("BROKER_REJECTED", {"reason": str(exc)[:240]})
            raise LaunchLabError(str(exc)) from exc

        self._append_event(
            "BROKER_POLICY_ACCEPTED",
            {
                "request_hash": broker_result["request_hash"],
                "broker_receipt_hash": broker_result["broker_receipt_hash"],
                "network_access": False,
                "rpc_access": False,
                "wallet_access": False,
                "private_key_access": False,
                "generic_signing": False,
            },
        )
        self.state["launches"] = 1
        self.state["state"] = "CONFIRMED"
        self.state["confirmed_at"] = datetime.now(timezone.utc).isoformat()
        final = self._append_event(
            "LOCAL_MOCK_LAUNCH_CONFIRMED",
            {
                "intent_hash": self.state.get("intent_hash"),
                "build_manifest_hash": self.state.get("build_manifest_hash"),
                "broker_receipt_hash": broker_result["broker_receipt_hash"],
                "result": broker_result["result"],
                "broadcast": broker_result["broadcast"],
            },
        )
        self.state["receipt_hash"] = final["hash"]
        self.state["activation_due_at"] = None
        self._persist_runtime_state()
        try:
            self._seal_current_proof_bundle()
        except Exception as exc:
            self.state["state"] = "PROOF_SEAL_FAILED"
            self._append_event(
                "AUTONOMY_PROOF_INVALIDATED",
                {"reason": f"proof bundle sealing failed: {str(exc)[:180]}"},
            )
            raise LaunchLabError("proof bundle sealing failed") from exc

    def tick(self, stack: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            self.state["stack"] = dict(stack or {})

            if self.state.get("state") == "ARMED":
                if not self._check_system_input_guard(context):
                    return self._public_state()
                if time.time() < float(self.state.get("decision_due_at") or 0):
                    return self._public_state()
                if self.state.get("human_inputs_after_arm", 0) != 0:
                    self.state["state"] = "BLOCKED_HUMAN_INPUT"
                    self._append_event("AUTONOMY_PROOF_INVALIDATED", {"reason": "human input counter nonzero"})
                    return self._public_state()
                if self.policy.get("require_stack_healthy") is True and not bool(stack.get("healthy")):
                    return self._public_state()

                readiness = self._agent_readiness(context)
                self.state["readiness"] = readiness
                if not readiness["ready"]:
                    return self._public_state()

                intent_payload = {
                    "operation": "LOCAL_MOCK_TOKEN_LAUNCH",
                    "session_id": self.state["session_id"],
                    "policy_hash": self.policy_hash,
                    "build_manifest_hash": self.state.get("build_manifest_hash"),
                    "human_inputs_after_arm": 0,
                    "stack": dict(stack or {}),
                    "context": dict(context or {}),
                    "readiness": readiness,
                }
                intent_hash = _sha256(intent_payload)
                self.state.update(
                    state="DECIDED",
                    decided_at=datetime.now(timezone.utc).isoformat(),
                    intent_hash=intent_hash,
                    activation_due_at=time.time() + 2.2,
                )
                self.state["agent_actions"] += 1
                self._append_event(
                    "AGENT_DECISION",
                    {
                        "decision": "LAUNCH",
                        "intent_hash": intent_hash,
                        "build_manifest_hash": self.state.get("build_manifest_hash"),
                        "reason": "Fly runtime readiness passed; stack healthy; no human input after ARM",
                        "readiness": readiness,
                        "context": dict(context or {}),
                    },
                )
                self._append_event(
                    "LAUNCH_INTENT_CREATED",
                    {
                        "intent_hash": intent_hash,
                        "policy_hash": self.policy_hash,
                        "operation": "LOCAL_MOCK_TOKEN_LAUNCH",
                    },
                )
                return self._public_state()

            if self.state.get("state") == "DECIDED":
                if not self._check_system_input_guard(context):
                    return self._public_state()
                if self.state.get("human_inputs_after_arm", 0) != 0:
                    self.state["state"] = "BLOCKED_HUMAN_INPUT"
                    self._append_event("AUTONOMY_PROOF_INVALIDATED", {"reason": "human input counter nonzero"})
                    return self._public_state()
                if self.policy.get("require_stack_healthy") is True and not bool(stack.get("healthy")):
                    return self._public_state()
                if time.time() >= float(self.state.get("activation_due_at") or 0):
                    self._execute_locked()

            return self._public_state()

    def _read_session_events(self, session_id: str) -> list[dict[str, Any]]:
        if not session_id or any(ch not in "0123456789abcdef" for ch in session_id.lower()) or len(session_id) != 32:
            raise LaunchLabError("invalid launch session id")
        path = self.sessions_dir / f"{session_id}.jsonl"
        if not path.is_file():
            raise LaunchLabError("launch session audit file not found")
        events = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LaunchLabError(f"audit JSON is invalid at line {line_number}") from exc
            if not isinstance(item, dict):
                raise LaunchLabError(f"audit event at line {line_number} is not an object")
            events.append(item)
        return events

    def verify_session(self, session_id: str | None = None) -> dict[str, Any]:
        with self.lock:
            sid = session_id or self.state.get("session_id")
            if not sid:
                raise LaunchLabError("no launch session to verify")
            events = self._read_session_events(str(sid))
            errors, previous = self._validate_event_chain(events, str(sid))
            names: list[str] = [str(event.get("event") or "") for event in events]

            required = [
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
            positions = []
            for name in required:
                try:
                    positions.append(names.index(name))
                except ValueError:
                    errors.append(f"missing event: {name}")
            if len(positions) == len(required) and positions != sorted(positions):
                errors.append("required event order is invalid")
            if "HUMAN_INPUT_AFTER_ARM" in names:
                errors.append("browser human input occurred after ARM")
            if "SYSTEM_HUMAN_INPUT_DETECTED" in names:
                errors.append("Windows user input occurred after ARM")
            if "SYSTEM_INPUT_GUARD_FAILED" in names:
                errors.append("system-input sentinel failed during autonomy window")
            if "AUTONOMY_PROOF_INVALIDATED" in names:
                errors.append("autonomy proof was invalidated")
            if names.count("LOCAL_MOCK_LAUNCH_CONFIRMED") > 1:
                errors.append("launch confirmation occurred more than once")

            precommit = next((event for event in events if event.get("event") == "BUILD_PRECOMMITTED"), None)
            manifest = ((precommit or {}).get("data") or {}).get("manifest") if precommit else None
            manifest_hash = ((precommit or {}).get("data") or {}).get("manifest_hash") if precommit else None
            if not isinstance(manifest, dict):
                errors.append("build precommit manifest missing")
            else:
                if self.policy.get("require_git_commit") is True and not manifest.get("git_commit"):
                    errors.append("Git commit identity missing from manifest")
                if self.policy.get("require_clean_tracked_worktree") is True and manifest.get("git_tracked_worktree_clean") is not True:
                    errors.append("tracked Git worktree was not clean at ARM")
            if isinstance(manifest, dict) and manifest_hash != _sha256({k: v for k, v in manifest.items() if k != "manifest_hash"}):
                # The stored manifest contains its own manifest_hash. Recompute the exact construction.
                base = dict(manifest)
                embedded = base.pop("manifest_hash", None)
                recomputed = _sha256(base)
                if embedded != recomputed or manifest_hash != embedded:
                    errors.append("build manifest hash mismatch")

            passed = not errors
            return {
                "schema": 1,
                "project": "JPGFLY",
                "session_id": sid,
                "verified": passed,
                "result": "PASS" if passed else "FAIL",
                "errors": errors,
                "event_count": len(events),
                "last_event_hash": previous,
                "build_manifest": manifest,
                "build_manifest_hash": manifest_hash,
                "human_input_after_arm": "HUMAN_INPUT_AFTER_ARM" in names,
                "autonomy_invalidated": "AUTONOMY_PROOF_INVALIDATED" in names,
                "confirmed_once": names.count("LOCAL_MOCK_LAUNCH_CONFIRMED") == 1,
            }

    def receipt(self) -> dict[str, Any]:
        with self.lock:
            if not self.state.get("session_id"):
                raise LaunchLabError("no launch receipt exists")
            return {
                "schema": 1,
                "project": "JPGFLY",
                "mode": "LOCAL_MOCK_ONLY",
                "session_id": self.state["session_id"],
                "state": self.state["state"],
                "policy_hash": self.policy_hash,
                "intent_hash": self.state.get("intent_hash"),
                "receipt_hash": self.state.get("receipt_hash") or self.state.get("last_event_hash"),
                "build_manifest": self.state.get("build_manifest"),
                "build_manifest_hash": self.state.get("build_manifest_hash"),
                "readiness": self.state.get("readiness"),
                "system_input_guard": {
                    "baseline": self.state.get("system_input_baseline"),
                    "final": self.state.get("system_input_final"),
                    "unchanged": (
                        (self.state.get("system_input_baseline") or {}).get("last_input_tick_ms")
                        == (self.state.get("system_input_final") or {}).get("last_input_tick_ms")
                    ),
                    "records_content": False,
                },
                "human_inputs_after_arm": self.state.get("human_inputs_after_arm", 0),
                "agent_actions": self.state.get("agent_actions", 0),
                "human_approval_at_execution": False,
                "network_access": False,
                "rpc_access": False,
                "wallet_access": False,
                "private_key_access": False,
                "generic_signing": False,
                "events": list(self.state.get("events") or []),
            }

    def _build_current_proof_bundle(self) -> dict[str, Any]:
        if not self.state.get("session_id"):
            raise LaunchLabError("no launch session exists")
        session_id = str(self.state["session_id"])
        receipt = self.receipt()
        verification = self.verify_session(session_id)
        snapshot = self._load_precommit_snapshot(
            session_id,
            self.state.get("source_snapshot_hash"),
        )

        bundle = {
            "schema": 1,
            "kind": "JPGFLY_LOCAL_AUTONOMY_PROOF",
            "project": "JPGFLY",
            "session_id": session_id,
            "created_at": self.state.get("confirmed_at") or self.state.get("decided_at") or self.state.get("armed_at"),
            "policy": json.loads(json.dumps(self.policy)),
            "receipt": receipt,
            "verification": verification,
            "events": list(self.state.get("events") or []),
            "source_snapshot_hash": snapshot.get("snapshot_hash"),
            "source_snapshot": snapshot.get("source_snapshot"),
            "art_policy_snapshot": snapshot.get("art_policy_snapshot"),
        }
        bundle["bundle_hash"] = _sha256(bundle)
        return bundle

    def _seal_current_proof_bundle(self) -> dict[str, Any]:
        bundle = self._build_current_proof_bundle()
        session_id = str(bundle["session_id"])
        path = self._bundle_path(session_id)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(_canonical(bundle), encoding="utf-8")
        temporary.replace(path)
        self.state["proof_bundle_hash"] = bundle["bundle_hash"]
        self._persist_runtime_state()
        return bundle

    def proof_bundle(self) -> dict[str, Any]:
        with self.lock:
            if not self.state.get("session_id"):
                raise LaunchLabError("no launch session exists")
            session_id = str(self.state["session_id"])
            path = self._bundle_path(session_id)
            if path.is_file():
                try:
                    bundle = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    raise LaunchLabError("sealed proof bundle is unreadable") from exc
                if not isinstance(bundle, dict):
                    raise LaunchLabError("sealed proof bundle is invalid")
                supplied = bundle.get("bundle_hash")
                unsigned = dict(bundle)
                unsigned.pop("bundle_hash", None)
                if supplied != _sha256(unsigned):
                    raise LaunchLabError("sealed proof bundle hash mismatch")
                if bundle.get("session_id") != session_id:
                    raise LaunchLabError("sealed proof bundle session mismatch")
                return bundle
            return self._build_current_proof_bundle()
