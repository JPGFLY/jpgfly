"""Candidate-based autonomous wrapper for the JPGFLY painting brain.

The underlying procedural painter proposes several possible next actions from the
same observed canvas. This wrapper scores those alternatives, chooses one with
weighted randomness, and commits only the selected branch.

Literal form primitives remain available, but they are deliberately rare.
Most form vocabulary is treated as a hint, fragment, or mutation rather than a
stamp. The browser remains a renderer only.
"""
from __future__ import annotations

import copy
import math
import os
from dataclasses import dataclass
from typing import Any

from pydantic import Field

from brain_provider import (
    BrainAction,
    BrainUnavailable,
    BrainLimits,
    BrainRequest,
    FIGURATIVE_MOTIFS,
    ProceduralFlyBrain,
    OllamaFlyBrain,
    create_fly_brain as create_legacy_brain,
)

BRAIN_VERSION = "JPGFLY-BRAIN/6.4-FLYBRAIN-MALECNS-FALLBACK"

FORM_MODES = ("NONE", "HINT", "FRAGMENT", "MUTATION", "EXPLICIT")

CONTEXT_PASSES = ("GROUND", "ECHO", "COUNTER", "INTEGRATE", "EDIT_RESOLVE")

TENSION_PRESSURES = {
    "DENSITY_VS_VOID": ("VOID", "SCARCITY", "TENSION"),
    "ORDER_VS_RUPTURE": ("RUPTURE", "SYSTEM", "TENSION"),
    "RETURN_VS_ESCAPE": ("RETURN", "ECHO", "EROSION"),
    "CENTER_VS_EDGE": ("FIGURE_FIELD", "TENSION", "RHYTHM"),
    "SYSTEM_VS_NOISE": ("SYSTEM", "NOISE", "NETWORK"),
    "FIGURE_VS_FIELD": ("ORGANIC", "FIGURE_FIELD", "RHYTHM"),
}

PRESSURE_STYLES = {
    "STRUCTURE": {"lattice","contour","segmented","web","branch"},
    "REVISION": {"echo","contour","hook","cross","accent"},
    "RHYTHM": {"wave","ribbon","meander","loop","scallop"},
    "ECHO": {"echo","orbit","loop","contour","coil"},
    "VOID": {"contour","accent","sweep","hook"},
    "TENSION": {"cross","fracture","zigzag","branch","bold"},
    "ORGANIC": {"blob","coil","wave","branch","petal","meander"},
    "FIGURE_FIELD": {"contour","blob","orbit","web","petal"},
    "EROSION": {"fracture","charcoal","scribble","jitter","segmented"},
    "RETURN": {"echo","contour","orbit","loop","hook"},
    "SYSTEM": {"lattice","maze","segmented","web","cross"},
    "SCARCITY": {"accent","contour","hook","segmented"},
    "NOISE": {"scribble","jitter","fracture","cluster","zigzag"},
    "NETWORK": {"web","branch","lattice","cross","starburst"},
    "CHANCE": {"scribble","jitter","meander","sweep","fan"},
    "RUPTURE": {"fracture","cross","zigzag","starburst","scribble"},
    "ABSURD": {"scribble","blob","jitter","rosette","fan"},
}


class CandidateBrainAction(BrainAction):
    motifMode: str = "NONE"
    suggestedForm: str = "NONE"
    decisionMode: str = "ABSTRACT_BUILD"
    roomTension: str = ""
    contextPass: str = "GROUND"
    memoryContext: list[str] = Field(default_factory=list)
    candidateCount: int = 0
    candidateScores: list[dict[str, Any]] = Field(default_factory=list)
    malecnsActivity: dict[str, Any] = Field(default_factory=dict)


@dataclass
class CandidateFlyBrain(ProceduralFlyBrain):
    """Generate alternatives, score them, then commit one selected future."""

    def __post_init__(self):
        super().__post_init__()
        self.mode = "LOCAL PROCEDURAL FLY BRAIN · CANDIDATE PAINTER · MEMORY + CONTEXT"
        self._candidate_serial = 0
        self._explicit_forms: list[tuple[int, str]] = []
        experience = self.experience or {}
        self.conceptual_strength = max(0.0, min(0.22, float(experience.get("conceptual_strength", 0) or 0)))
        self.context_pressures = dict(experience.get("conceptual_pressures") or {})
        self.memory_context = [name for name, _ in sorted(self.context_pressures.items(), key=lambda item: (-float(item[1]), item[0]))[:4]]
        self.recent_rooms = list(experience.get("recent_rooms") or [])[-8:]
        self.learned_brushes = dict(experience.get("brushes") or {})
        self.learned_techniques = dict(experience.get("techniques") or {})
        self._mode_counts: dict[str, int] = {}
        self._brush_counts: dict[str, int] = {}
        self._technique_counts: dict[str, int] = {}
        self._context_counts: dict[str, int] = {}
        def aggregate_recent(key):
            table: dict[str,float] = {}
            for room in self.recent_rooms[-4:]:
                for value in room.get(key) or []:
                    if isinstance(value,(list,tuple)) and value:
                        name=str(value[0]);weight=float(value[1] if len(value)>1 else 1)
                        table[name]=table.get(name,0.0)+weight
            total=sum(table.values()) or 1.0
            return {k:v/total for k,v in table.items()}
        self._recent_style_weights=aggregate_recent("styles")
        self._recent_brush_weights=aggregate_recent("brushes")
        self._recent_technique_weights=aggregate_recent("techniques")
        self.room_tension = self._choose_room_tension()

    def _choose_room_tension(self) -> str:
        tensions = tuple(TENSION_PRESSURES)
        recent_tensions = {
            str(item[0])
            for room in self.recent_rooms[-3:]
            for item in (room.get("room_tension") or [])[:1]
            if isinstance(item, (list, tuple)) and item
        }
        weights = []
        for tension in tensions:
            memory = sum(float(self.context_pressures.get(axis, 0) or 0) for axis in TENSION_PRESSURES[tension])
            weight = 1.0 + memory * self.conceptual_strength * 9.0
            if tension in recent_tensions:
                weight *= 0.62
            weights.append(max(0.08, weight))
        return self.rng.choices(tensions, weights=weights, k=1)[0]

    def _context_pass(self) -> str:
        progress = max(0.0, min(1.0, self.decision_count / max(1, self.desired_decisions)))
        if progress < 0.18:
            return "GROUND"
        if progress < 0.40:
            return "ECHO"
        if progress < 0.62:
            return "COUNTER"
        if progress < 0.84:
            return "INTEGRATE"
        return "EDIT_RESOLVE"

    def context_snapshot(self) -> dict[str, Any]:
        return {
            "room_tension": self.room_tension,
            "context_pressures": self.memory_context,
            "visual_memory_strength": round(float(getattr(self, "learning_strength", 0) or 0), 4),
            "conceptual_memory_strength": round(self.conceptual_strength, 4),
            "rooms_seen": int((self.experience or {}).get("rooms_seen", 0) or 0),
            "readings_seen": int((self.experience or {}).get("readings_seen", 0) or 0),
            "palette_name": str(getattr(self, "palette_name", "") or ""),
            "composition_mode": str(getattr(self, "composition_mode", "") or ""),
            "subject_program": str(getattr(self, "subject_program_name", "") or ""),
            "archetype": str(getattr(self, "archetype", "") or ""),
            "spatial_program": str(getattr(self, "spatial_program", "") or ""),
            "stroke_dialect": str(getattr(self, "stroke_dialect", "") or ""),
            "duration_profile": str(getattr(self, "duration_profile", "") or ""),
            "tempo_mode": str(getattr(self, "tempo_mode", "") or ""),
            "content_register": str(getattr(self, "content_register", "") or ""),
            "desired_decisions": int(getattr(self, "desired_decisions", 0) or 0),
            "current_goal": str(getattr(self, "goal", "") or ""),
            "style_counts": dict(getattr(self, "style_counts", {}) or {}),
            "context_pass_counts": dict(self._context_counts),
            "decision_mode_counts": dict(self._mode_counts),
            "brush_counts": dict(self._brush_counts),
            "technique_counts": dict(self._technique_counts),
        }

    def _decision_mode(self, action: BrainAction) -> str:
        relation = str(action.relationshipToExistingMarks or "")
        if action.intent == "FINISH_ARTWORK":
            return "FINISH"
        if action.eraseIntent:
            return "ERASE"
        if "avoid_overcrowding" in relation or action.attentionTarget.get("kind") == "negative_space":
            return "NEGATIVE_SPACE"
        if "connect" in relation:
            return "CONNECT"
        if "revisit" in relation or action.motifTransform in {"repeat", "loose_mirror"}:
            return "REVISIT"
        if action.motifTransform in {"interrupt", "cross"} or "contradict" in relation:
            return "CONTRADICT"
        return "ABSTRACT_BUILD"

    def _form_mode(self, action: BrainAction, clone: ProceduralFlyBrain, index: int) -> tuple[str, str]:
        form = str(action.motifHint or "NONE")
        if form not in FIGURATIVE_MOTIFS:
            return "NONE", "NONE"

        phase = str(action.phase or "")
        transform = str(action.motifTransform or "none")
        recent_same = any(
            form == previous and clone.decision_count - at < 72
            for at, previous in self._explicit_forms[-6:]
        )
        explicit_gap = (
            clone.decision_count - self._explicit_forms[-1][0]
            if self._explicit_forms
            else 10_000
        )

        # Explicit primitives are an option, never the default. Early phases almost
        # never choose them; repeated literal objects receive an additional penalty.
        explicit_probability = 0.008
        if phase in {"DEVELOPMENT", "CONTRAST", "REFINEMENT"}:
            explicit_probability += 0.018
        if getattr(clone, "goal", "") == "JOKE":
            explicit_probability += 0.008
        if explicit_gap < 42:
            explicit_probability *= 0.08
        if recent_same:
            explicit_probability *= 0.05

        probe = clone.rng.random()
        if probe < explicit_probability:
            return "EXPLICIT", form
        if transform in {"distort", "cross", "interrupt", "loose_mirror"}:
            return "MUTATION", form
        if transform in {"shrink", "enlarge"} or index % 5 == 0:
            return "FRAGMENT", form
        return "HINT", form

    def _finish_quality(self, observation: dict[str, Any], action: BrainAction) -> tuple[bool, dict[str, Any]]:
        evaluation = action.evaluation or {}
        coverage = float(observation.get("canvasOccupancy", 0) or 0)
        occupied_regions = int(observation.get("occupiedRegions", 0) or 0)
        intersections = int(observation.get("intersections", 0) or 0)
        families = len(observation.get("familyCounts") or {})
        meaningful = float(observation.get("meaningfulChangeRate", 0) or 0)
        readiness = float(evaluation.get("readiness", 0) or 0)
        director_ready = bool(evaluation.get("finishReady", False))

        minimum_decisions = max(180, int(self.desired_decisions * 0.62))
        composition_score = float(evaluation.get("compositionScore", 0) or 0)
        regional_spread = float(evaluation.get("regionalSpread", 0) or 0)
        checks = {
            "mature": self.decision_count >= minimum_decisions,
            "coverage": coverage >= 0.16,
            "regions": occupied_regions >= 4,
            "families": families >= 5,
            "intersections": intersections >= 4,
            "meaningful": meaningful >= 0.30,
            "modes": len(self._mode_counts) >= 4,
            "brushes": len(self._brush_counts) >= 3,
            "techniques": len(self._technique_counts) >= 3,
            "context_passes": len(self._context_counts) >= 4,
            "composition": composition_score >= 0.56,
            "spread": regional_spread >= 0.32,
            "director": director_ready,
            "readiness": readiness >= 0.68,
        }
        artistic_signals = sum(
            1 for key in (
                "coverage","regions","families","intersections","meaningful",
                "modes","brushes","techniques","composition","spread"
            )
            if checks[key]
        )
        ready = (
            checks["mature"]
            and checks["context_passes"]
            and artistic_signals >= 7
            and (checks["director"] or checks["readiness"])
        )
        return ready, {
            "checks": checks,
            "artisticSignals": artistic_signals,
            "coverage": round(coverage, 3),
            "occupiedRegions": occupied_regions,
            "families": families,
            "intersections": intersections,
            "meaningfulChange": round(meaningful, 3),
            "readiness": round(readiness, 3),
            "compositionScore": round(composition_score, 3),
            "regionalSpread": round(regional_spread, 3),
            "minimumDecisions": minimum_decisions,
        }

    def _candidate_score(
        self,
        action: BrainAction,
        observation: dict[str, Any],
        mode: str,
        form_mode: str,
        suggested_form: str,
        clone: ProceduralFlyBrain,
        index: int,
        context_pass: str,
    ) -> float:
        if action.intent == "FINISH_ARTWORK":
            ready, _ = self._finish_quality(observation, action)
            readiness = float((action.evaluation or {}).get("readiness", 0) or 0)
            progress = self.decision_count / max(1, self.desired_decisions)
            if not ready:
                return -5.5 + readiness + min(1.0, progress)
            # FINISH competes with the other artistic options. It becomes more
            # attractive as the room matures, but it is still a Fly Brain choice.
            return 1.9 + readiness * 2.0 + min(1.4, max(0.0, progress - .62) * 2.8)

        density = float(observation.get("localDensity", 0) or 0)
        repetition = float(observation.get("repetition", 0) or 0)
        uniform = float(observation.get("directionalUniformity", 0) or 0)
        contrast = float(observation.get("densityContrast", 0) or 0)
        low = min(1.0, float(observation.get("consecutiveLowChange", 0) or 0) / 10.0)
        style_count = float(self.style_counts.get(action.movementStyle, 0) or 0)
        total = max(1.0, float(self.decision_count))
        novelty = 1.0 - min(1.0, style_count / max(3.0, total * 0.16))

        score = 1.0
        score += novelty * 0.9
        score += float(getattr(self, "drives", {}).get("novelty", 0.5)) * 0.25

        coverage = float(observation.get("canvasOccupancy", 0) or 0)
        occupied_regions = int(observation.get("occupiedRegions", 0) or 0)

        if self.room_tension == "DENSITY_VS_VOID":
            score += 0.30 if (coverage < 0.28 and mode in {"ABSTRACT_BUILD","CONNECT"}) or (coverage >= 0.28 and mode=="NEGATIVE_SPACE") else 0
        elif self.room_tension == "ORDER_VS_RUPTURE":
            score += 0.28 if mode in {"CONNECT","CONTRADICT"} else 0
        elif self.room_tension == "RETURN_VS_ESCAPE":
            score += 0.28 if mode in {"REVISIT","NEGATIVE_SPACE"} else 0
        elif self.room_tension == "CENTER_VS_EDGE":
            score += 0.24 if mode in {"CONNECT","CONTRADICT","ABSTRACT_BUILD"} else 0
        elif self.room_tension == "SYSTEM_VS_NOISE":
            score += 0.30 if action.movementStyle in {"lattice","maze","segmented","scribble","fracture","jitter"} else 0
        elif self.room_tension == "FIGURE_VS_FIELD":
            score += 0.24 if form_mode in {"HINT","FRAGMENT","MUTATION"} or mode in {"ABSTRACT_BUILD","NEGATIVE_SPACE"} else 0

        if coverage < 0.16:
            if mode in {"ABSTRACT_BUILD","CONNECT","CONTRADICT"}:
                score += 0.90
            if mode in {"NEGATIVE_SPACE","ERASE"}:
                score -= 1.15
            if not action.brushDown:
                score -= 0.75
            if action.movementDistance >= 55:
                score += 0.35
        if occupied_regions < 4 and mode in {"CONNECT","ABSTRACT_BUILD","CONTRADICT"}:
            score += 0.32
        if self.decision_count > 45 and mode in {"CONNECT","REVISIT","CONTRADICT","ERASE"}:
            score += 0.26

        if mode == "CONTRADICT":
            score += repetition * 0.8 + uniform * 0.7
        elif mode == "CONNECT":
            score += (1.0 - contrast) * 0.55
        elif mode == "REVISIT":
            score += 0.35 if self.motifs else -0.25
        elif mode == "NEGATIVE_SPACE":
            score += density * 0.75 + low * 0.25
        elif mode == "ERASE":
            score += density * 0.65 + repetition * 0.35
        elif mode == "ABSTRACT_BUILD":
            score += (1.0 - density) * 0.25

        # Each room has a long-form visual argument: establish, remember,
        # contradict, integrate, then edit. This makes hundreds of decisions read
        # as one composition rather than unrelated marks.
        pass_modes = {
            "GROUND": {"ABSTRACT_BUILD": .50, "CONNECT": .32},
            "ECHO": {"REVISIT": .62, "CONNECT": .28},
            "COUNTER": {"CONTRADICT": .68, "ERASE": .28, "ABSTRACT_BUILD": .18},
            "INTEGRATE": {"CONNECT": .58, "REVISIT": .42, "ABSTRACT_BUILD": .16},
            "EDIT_RESOLVE": {"ERASE": .38, "NEGATIVE_SPACE": .32, "REVISIT": .28, "CONNECT": .24},
        }
        score += pass_modes.get(context_pass, {}).get(mode, 0.0)

        # Conceptual reading memory is intentionally abstract. It can make a room
        # more systemic, ruptured, organic, rhythmic, etc., but never asks for a
        # literal illustration of what was read.
        for pressure, pressure_weight in self.context_pressures.items():
            if action.movementStyle in PRESSURE_STYLES.get(pressure, set()):
                score += self.conceptual_strength * float(pressure_weight or 0) * 1.9
        if "RUPTURE" in self.context_pressures and mode == "CONTRADICT":
            score += self.conceptual_strength * float(self.context_pressures["RUPTURE"]) * 1.3
        if "RETURN" in self.context_pressures and mode == "REVISIT":
            score += self.conceptual_strength * float(self.context_pressures["RETURN"]) * 1.3
        if "VOID" in self.context_pressures and mode == "NEGATIVE_SPACE":
            score += self.conceptual_strength * float(self.context_pressures["VOID"]) * 1.15
        if "NETWORK" in self.context_pressures and mode == "CONNECT":
            score += self.conceptual_strength * float(self.context_pressures["NETWORK"]) * 1.15

        # Finished rooms leave habits, not commands. Familiar tools receive a small
        # echo bonus, while dominant styles from the last few rooms receive a small
        # counter-memory penalty so biography does not become repetition.
        score += self.learning_strength * float(self.learned_brushes.get(action.brushTool, 0) or 0) * .24
        score += self.learning_strength * float(self.learned_techniques.get(action.technique, 0) or 0) * .24
        # Long-term memory may echo. Immediate memory must resist cloning.
        recent_style=float(self._recent_style_weights.get(action.movementStyle,0) or 0)
        recent_brush=float(self._recent_brush_weights.get(action.brushTool,0) or 0)
        recent_tech=float(self._recent_technique_weights.get(action.technique,0) or 0)
        score -= recent_style * 1.25
        score -= recent_brush * .62
        score -= recent_tech * .52
        if self.recent_rooms and recent_style==0:
            score += .18
        if self.recent_rooms and recent_brush==0:
            score += .10

        mode_seen = int(self._mode_counts.get(mode, 0) or 0)
        brush_seen = int(self._brush_counts.get(action.brushTool, 0) or 0)
        technique_seen = int(self._technique_counts.get(action.technique, 0) or 0)
        if self.decision_count > 80:
            score += .18 if mode_seen < max(2, self.decision_count * .08) else -.12
            score += .12 if brush_seen < max(2, self.decision_count * .07) else -.08
            score += .12 if technique_seen < max(2, self.decision_count * .07) else -.08

        if form_mode == "HINT":
            score += 0.12
        elif form_mode == "FRAGMENT":
            score += 0.18 + float(getattr(self, "mutation", 0.4)) * 0.08
        elif form_mode == "MUTATION":
            score += 0.22 + float(getattr(self, "mutation", 0.4)) * 0.18
        elif form_mode == "EXPLICIT":
            score -= 1.7
            if self.decision_count < max(45, int(self.desired_decisions * 0.22)):
                score -= 1.0
            if any(suggested_form == old for _, old in self._explicit_forms[-4:]):
                score -= 1.2

        # Avoid deterministic "best move every time". Each candidate gets a small,
        # seeded perturbation before weighted selection.
        score += (clone.rng.random() - 0.5) * 0.28
        score += (index % 3) * 0.015
        return score

    def _as_candidate_action(
        self,
        action: BrainAction,
        mode: str,
        form_mode: str,
        suggested_form: str,
        summaries: list[dict[str, Any]],
        context_pass: str,
    ) -> CandidateBrainAction:
        data = action.model_dump()

        # Hints/fragments/mutations influence the brain's mark choice but are not
        # sent to server mechanics as literal geometry. Only EXPLICIT preserves the
        # primitive name as motifHint.
        if form_mode != "EXPLICIT":
            data["motifHint"] = "NONE"

        if form_mode == "HINT" and suggested_form != "NONE":
            data["reason"] = f"A {suggested_form.lower().replace('_',' ')} is only a possibility. Keep it unresolved."
        elif form_mode == "FRAGMENT" and suggested_form != "NONE":
            data["reason"] = f"Use only a broken trace of the {suggested_form.lower().replace('_',' ')}; do not complete the symbol."
        elif form_mode == "MUTATION" and suggested_form != "NONE":
            data["reason"] = f"Let the {suggested_form.lower().replace('_',' ')} idea deform the gesture without becoming a clean icon."

        return CandidateBrainAction(
            **data,
            motifMode=form_mode,
            suggestedForm=suggested_form,
            decisionMode=mode,
            roomTension=self.room_tension,
            contextPass=context_pass,
            memoryContext=list(self.memory_context),
            candidateCount=len(summaries),
            candidateScores=summaries,
        )

    def decide(self, request: BrainRequest, limits: BrainLimits):
        observation = request.observation
        hard = self.hard_limit(observation, limits)
        if hard:
            action = ProceduralFlyBrain.decide(self, request, limits)
            return CandidateBrainAction(
                **action.model_dump(),
                motifMode="NONE",
                suggestedForm="NONE",
                decisionMode="FINISH",
                roomTension=self.room_tension,
                contextPass=self._context_pass(),
                memoryContext=list(self.memory_context),
                candidateCount=1,
                candidateScores=[{"mode": "FINISH", "score": 99.0}],
            )

        context_pass = self._context_pass()
        candidates = []
        count = 8
        for index in range(count):
            clone = copy.deepcopy(self)

            # Each branch begins from the identical brain/canvas state but explores
            # a different seeded continuation.
            for _ in range(2 + index * 3):
                clone.rng.random()

            action = ProceduralFlyBrain.decide(clone, request, limits)
            mode = self._decision_mode(action)
            form_mode, suggested_form = self._form_mode(action, clone, index)
            score = self._candidate_score(
                action, observation, mode, form_mode, suggested_form, clone, index, context_pass
            )
            candidates.append(
                {
                    "clone": clone,
                    "action": action,
                    "mode": mode,
                    "form_mode": form_mode,
                    "suggested_form": suggested_form,
                    "score": score,
                }
            )

        # Once the room reaches its resolve window, FINISH is always a real
        # candidate instead of depending on one procedural branch randomly
        # proposing it. The Fly Brain still chooses probabilistically by score.
        finish_window = (
            context_pass == "EDIT_RESOLVE"
            or self.decision_count >= max(180, int(self.desired_decisions * .70))
        )
        if finish_window and not any(item["mode"] == "FINISH" for item in candidates):
            finish_clone = copy.deepcopy(self)
            finish_action = finish_clone.finish(observation, limits)
            finish_score = self._candidate_score(
                finish_action, observation, "FINISH", "NONE", "NONE",
                finish_clone, count, context_pass
            )
            candidates.append({
                "clone": finish_clone,
                "action": finish_action,
                "mode": "FINISH",
                "form_mode": "NONE",
                "suggested_form": "NONE",
                "score": finish_score,
            })

        highest = max(item["score"] for item in candidates)
        temperature = 0.62
        weights = [
            math.exp(max(-12.0, min(4.0, (item["score"] - highest) / temperature)))
            for item in candidates
        ]
        chosen = self.rng.choices(candidates, weights=weights, k=1)[0]

        summaries = sorted(
            (
                {
                    "mode": item["mode"],
                    "motifMode": item["form_mode"],
                    "form": item["suggested_form"],
                    "style": item["action"].movementStyle,
                    "contextPass": context_pass,
                    "score": round(float(item["score"]), 3),
                }
                for item in candidates
            ),
            key=lambda item: item["score"],
            reverse=True,
        )[:6]

        # Commit the internal state belonging to the chosen future only.
        self.__dict__.clear()
        self.__dict__.update(chosen["clone"].__dict__)
        self._candidate_serial = int(getattr(self, "_candidate_serial", 0)) + 1
        chosen_action = chosen["action"]
        self._mode_counts[chosen["mode"]] = self._mode_counts.get(chosen["mode"], 0) + 1
        self._brush_counts[chosen_action.brushTool] = self._brush_counts.get(chosen_action.brushTool, 0) + 1
        self._technique_counts[chosen_action.technique] = self._technique_counts.get(chosen_action.technique, 0) + 1
        self._context_counts[context_pass] = self._context_counts.get(context_pass, 0) + 1

        if chosen["form_mode"] == "EXPLICIT" and chosen["suggested_form"] != "NONE":
            self._explicit_forms.append((self.decision_count, chosen["suggested_form"]))
            self._explicit_forms = self._explicit_forms[-12:]

        action=self._as_candidate_action(
            chosen["action"],
            chosen["mode"],
            chosen["form_mode"],
            chosen["suggested_form"],
            summaries,
            context_pass,
        )
        malecns_enabled=os.environ.get("JPGFLY_MALECNS_ENABLED","").strip().lower() in {"1","true","yes","on"} or bool(os.environ.get("JPGFLY_MALECNS_URL","").strip())
        if malecns_enabled:
            bridge=OllamaFlyBrain(self)
            bias=bridge._malecns_bias(observation,action)
            if bias:
                action=bridge._apply_malecns_bias(action,bias)
                action.malecnsActivity={
                    key:bias.get(key)
                    for key in (
                        "active_neurons","total_spikes","visual_spikes","descending_spikes",
                        "turn_signal","forward_signal","attack_signal","sim_ms","wall_ms",
                        "direction_bias","pressure_bias","exploration_bias","scale_bias",
                        "hesitation_bias","finish_inhibition"
                    )
                    if key in bias
                }
                self.mode="LOCAL PROCEDURAL FLY BRAIN · CANDIDATE PAINTER · MEMORY + CONTEXT · MALECNS"
        return action


def _experience_without_literal_motif_lockin(experience: dict[str, Any] | None) -> dict[str, Any]:
    value = dict(experience or {})
    # Historical rooms may contain literal motif counts. Do not feed those concrete
    # object frequencies back into the next room as a preference.
    value["motifs"] = {}
    return value


def create_fly_brain(seed, *, complexity=.96, mutation=.42, density=.64, experience=None):
    if os.environ.get("JPGFLY_BRAIN_PROVIDER", "procedural").lower() == "ollama":
        return create_legacy_brain(
            seed,
            complexity=complexity,
            mutation=mutation,
            density=density,
            experience=_experience_without_literal_motif_lockin(experience),
        )

    if experience is None:
        try:
            from experience_memory import visual_bias
            experience = visual_bias()
        except Exception:
            experience = {}

    return CandidateFlyBrain(
        seed,
        complexity,
        mutation,
        density,
        _experience_without_literal_motif_lockin(experience),
    )


def configured_brain_mode():
    if os.environ.get("JPGFLY_BRAIN_PROVIDER", "procedural").lower() == "ollama":
        return "OLLAMA REQUESTED — VERIFIED PER SESSION"
    return "LOCAL PROCEDURAL FLY BRAIN · 8 CANDIDATES / MEMORY-CONTEXT CHOICE"
