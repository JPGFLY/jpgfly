import gzip
import json
from fastapi import HTTPException, Request
from fastapi.responses import Response

# Public live UI fields only. Keep private planner/model internals on the server.
_PUBLIC_ACTION_FIELDS = (
    "intent", "phase", "movementStyle", "brushTool", "technique", "brushDown",
    "pressure", "color", "duration", "hesitation", "targetDirection", "movementDistance",
    "curvature", "eraseIntent", "relationshipToExistingMarks", "motifHint", "motifMode",
    "suggestedForm", "decisionMode", "contextPass", "compositionPass", "macroIntent",
    "autonomyGoal", "paletteName", "renderEffect", "materialStyle", "scale",
    "candidateCount", "artisticTemperament", "compositionMode", "zebracnsCriticPressure",
)
_PUBLIC_EVENT_TYPES = {
    "clear", "stroke", "move", "tip_down", "tip_up", "pause", "fly_comment",
    "state_change", "finish_artwork", "session_end",
}
_PUBLIC_OBSERVATION_FIELDS = (
    "canvasOccupancy", "intersections", "densityContrast", "localDensity",
    "repetition", "meaningfulChangeRate", "directionalUniformity",
    "consecutiveLowChange",
)
_MALE_PUBLIC_FIELDS = (
    "active_neurons", "total_spikes", "visual_spikes", "descending_spikes",
    "turn_signal", "forward_signal", "attack_signal", "sim_ms", "wall_ms",
    "direction_bias", "pressure_bias", "exploration_bias", "scale_bias",
    "hesitation_bias", "finish_inhibition",
)
_ZEBRA_PUBLIC_SIGNALS = (
    "visual_salience", "arousal", "persistence", "exploration", "novelty_seek",
    "attention_lock", "escape_drive", "repetition_drive", "state_instability",
    "completion_pressure", "tempo",
)


def _public_action(action):
    compact = {key: action.get(key) for key in _PUBLIC_ACTION_FIELDS if key in action}
    scores = action.get("candidateScores") or []
    if scores and isinstance(scores[0], dict):
        top = scores[0]
        compact["candidateScores"] = [{
            key: top.get(key)
            for key in ("mode", "motifMode", "score")
            if key in top
        }]
    memory = action.get("memoryContext") or []
    if isinstance(memory, list) and memory:
        compact["memoryContext"] = [str(item)[:64] for item in memory[:3]]

    male = action.get("malecnsActivity")
    if isinstance(male, dict) and male:
        compact["malecnsActivity"] = {
            key: male.get(key) for key in _MALE_PUBLIC_FIELDS if key in male
        }

    zebra = action.get("zebracnsActivity")
    if isinstance(zebra, dict) and zebra:
        signals = zebra.get("signals") if isinstance(zebra.get("signals"), dict) else {}
        compact["zebracnsActivity"] = {
            "dataset": str(zebra.get("dataset") or "")[:120],
            "frame": int(zebra.get("frame", 0) or 0),
            "sampled_neurons": int(zebra.get("sampled_neurons", 0) or 0),
            "action": str(zebra.get("action") or "NONE")[:24],
            "signals": {
                key: signals.get(key) for key in _ZEBRA_PUBLIC_SIGNALS if key in signals
            },
        }
    return compact


def _response(payload, request):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = {"Cache-Control": "no-store"}
    accepts_gzip = "gzip" in request.headers.get("accept-encoding", "").lower()
    if accepts_gzip and len(raw) >= 16 * 1024:
        raw = gzip.compress(raw, compresslevel=5, mtime=0)
        headers["Content-Encoding"] = "gzip"
        headers["Vary"] = "Accept-Encoding"
    return Response(raw, media_type="application/json", headers=headers)


def install_studio_delta(app, current_id, sessions, load_artwork_record, canonical, text_provider=None):
    @app.get("/api/studio/delta")
    def studio_delta(request: Request, session_id: str = "", after_decision: int = 0, after_event: int = 0):
        current = current_id()
        if not current:
            raise HTTPException(404, "studio is between rooms")
        if session_id and session_id != current:
            return _response({"reset": True, "session_id": current}, request)

        source = sessions.get(current)
        if source is None:
            source = load_artwork_record(current)
        if not source:
            raise HTTPException(404, "studio session unavailable")

        decisions = source.get("brain_decisions") or []
        events = source.get("events") or []
        d0 = max(0, min(int(after_decision or 0), len(decisions)))
        e0 = max(0, min(int(after_event or 0), len(events)))

        actions = []
        for record in decisions[d0:]:
            action = record.get("action") or {}
            observation = record.get("observation") or {}
            sequence = int(record.get("sequence", len(actions) + d0) or 0)
            signals = ["perception"]
            if sequence > 0 or action.get("motifReference"):
                signals.append("memory")
            signals.extend(["evaluation", "planning"])
            signals.append("completion" if action.get("intent") == "FINISH_ARTWORK" else "action")
            observation_summary = {
                key: observation.get(key)
                for key in _PUBLIC_OBSERVATION_FIELDS
                if key in observation
            }
            actions.append({
                "sequence": sequence,
                "action": _public_action(action),
                "observation_summary": observation_summary,
                "signals": signals,
            })

        commentary = source.get("public_commentary") or []
        last_note = commentary[-1] if commentary else {}
        provider = ""
        if callable(text_provider):
            try:
                provider = str(text_provider() or "").upper()
            except Exception:
                provider = ""
        if not provider:
            provider = str((last_note.get("provider") if isinstance(last_note, dict) else "") or source.get("text_provider") or "PROCEDURAL").upper()
        language_state = {
            "provider": provider,
            "source": "trained FLM text voice" if provider == "FLM" else provider.lower() or "procedural",
            "pending": bool(source.get("_commentary_busy", False)),
            "note_count": len(commentary),
        }

        public_events = [
            event for event in events[e0:]
            if isinstance(event, dict) and event.get("type") in _PUBLIC_EVENT_TYPES
        ]

        payload = {
            "reset": False,
            "session_id": current,
            "status": source.get("status") or source.get("state") or "RUNNING",
            "brain_mode": source.get("brain_mode", "JPGFLY"),
            "brain_version": source.get("brain_version"),
            "brain_source": "server-side painting agent",
            "agent_profile": source.get("agent_profile", "jpgfly"),
            "agent_name": source.get("agent_name", "JPGFLY"),
            "agent_lore": source.get("agent_lore", ""),
            "agent_echo_rule": source.get("agent_echo_rule", ""),
            "spawned_from": source.get("spawned_from"),
            "room_echoes": list(source.get("room_echoes") or [])[:4],
            "duration": int(source.get("duration", 0) or 0),
            "decision_count": len(decisions),
            "physical_action_count": int(source.get("physical_action_count", 0) or 0),
            "completion_reason": source.get("completion_reason"),
            "language_state": language_state,
            "actions": actions,
            "events": public_events,
            "event_count": len(events),
        }
        return _response(payload, request)
