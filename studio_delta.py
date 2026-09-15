import json
from fastapi import HTTPException

def install_studio_delta(app, current_id, sessions, load_artwork_record, canonical, text_provider=None):
    @app.get("/api/studio/delta")
    def studio_delta(session_id: str = "", after_decision: int = 0, after_event: int = 0):
        current = current_id()
        if not current:
            raise HTTPException(404, "studio is between rooms")
        if session_id and session_id != current:
            return {"reset": True, "session_id": current}

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
            if sequence > 0 or observation.get("recentMarks") or observation.get("visitedAreas") or action.get("motifReference"):
                signals.append("memory")
            signals.extend(["evaluation", "planning"])
            signals.append("completion" if action.get("intent") == "FINISH_ARTWORK" else "action")
            observation_summary = {
                key: observation.get(key)
                for key in (
                    "canvasOccupancy","nearbyLines","intersections","densityBalance",
                    "repetition","meaningfulChangeRate","densityContrast","localDensity",
                    "directionalUniformity","consecutiveLowChange","occupiedRegions",
                    "regionalContrast","recentMarks"
                )
                if key in observation
            }
            actions.append({
                "sequence": sequence,
                "action": action,
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
            "last_note": last_note.get("text", "") if isinstance(last_note, dict) else str(last_note or ""),
        }

        return {
            "reset": False,
            "session_id": current,
            "status": source.get("status") or source.get("state") or "RUNNING",
            "brain_mode": source.get("brain_mode", "JPGFLY"),
            "brain_version": source.get("brain_version"),
            "brain_source": "server-side painting agent",
            "duration": int(source.get("duration", 0) or 0),
            "decision_count": len(decisions),
            "physical_action_count": int(source.get("physical_action_count", 0) or 0),
            "completion_reason": source.get("completion_reason"),
            "language_state": language_state,
            "actions": json.loads(canonical(actions)),
            "events": json.loads(canonical(events[e0:])),
            "event_count": len(events),
        }
