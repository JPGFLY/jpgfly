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
import time
import urllib.request
from dataclasses import dataclass
from typing import Any

from pydantic import Field
from zebracns import artistic_zebracns_state
from art_policy import get_art_policy, features as art_policy_features
from agent_profiles import get_agent_profile, normalize_agent_profile

from brain_provider import (
    BrainAction,
    BrainLimits,
    BrainRequest,
    FIGURATIVE_MOTIFS,
    CONCRETE_SUBJECT_PROGRAMS,
    CONCRETE_MOTIFS,
    ProceduralFlyBrain,
    OllamaFlyBrain,
    PALETTE_PRESETS,
)

BRAIN_VERSION = "JPGFLY-BRAIN/7.1-TEMPORAL-ART-POLICY"

_SUPPORT_HEALTH_AT = 0.0
_SUPPORT_HEALTH_OK = True

def _support_nodes_online(max_age: float = 2.5) -> bool:
    """Return whether the configured Qwen/FLM support layer is reachable.

    The Fly Brain itself remains local/procedural. This status only controls
    whether the public session is labelled FULL or DUMB DUMB fallback.
    """
    global _SUPPORT_HEALTH_AT, _SUPPORT_HEALTH_OK
    now = time.monotonic()
    if now - _SUPPORT_HEALTH_AT < max_age:
        return _SUPPORT_HEALTH_OK

    checks = []
    ollama = os.environ.get("JPGFLY_OLLAMA_URL", "").strip().rstrip("/")
    flm = os.environ.get("JPGFLY_FLM_URL", "").strip().rstrip("/")
    control = os.environ.get("JPGFLY_CONTROL_TOKEN", "").strip()
    if ollama:
        checks.append((ollama + "/api/tags", os.environ.get("JPGFLY_OLLAMA_AUTH_TOKEN", "").strip() or control))
    if flm:
        checks.append((flm + "/health", os.environ.get("JPGFLY_FLM_AUTH_TOKEN", "").strip() or control))

    if not checks:
        _SUPPORT_HEALTH_AT = now
        _SUPPORT_HEALTH_OK = True
        return True

    ok = True
    for url, token in checks:
        headers = {"accept": "application/json"}
        if token:
            headers["authorization"] = "Bearer " + token
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=2.5) as response:
                if not (200 <= int(getattr(response, "status", 200)) < 300):
                    ok = False
                    break
        except Exception:
            ok = False
            break

    _SUPPORT_HEALTH_AT = now
    _SUPPORT_HEALTH_OK = ok
    return ok

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


ARTISTIC_TEMPERAMENTS = {
    "OBSESSIVE": {
        "density_scale": .82, "family_cap": 5,
        "modes": {"REVISIT": .34, "CONNECT": .12, "ERASE": .10},
        "styles": {"echo","contour","loop","coil","hook","scallop"},
    },
    "VIOLENT_MINIMAL": {
        "density_scale": .58, "family_cap": 4,
        "modes": {"CONTRADICT": .42, "NEGATIVE_SPACE": .34, "ERASE": .26},
        "styles": {"bold","fracture","cross","sweep","accent"},
    },
    "TENDER": {
        "density_scale": .68, "family_cap": 5,
        "modes": {"REVISIT": .24, "CONNECT": .28, "NEGATIVE_SPACE": .14},
        "styles": {"wave","ribbon","contour","petal","meander","sweep"},
    },
    "ARCHITECTURAL": {
        "density_scale": .74, "family_cap": 6,
        "modes": {"CONNECT": .38, "CONTRADICT": .20, "NEGATIVE_SPACE": .16},
        "styles": {"lattice","maze","segmented","web","cross","branch"},
    },
    "NERVOUS": {
        "density_scale": .76, "family_cap": 6,
        "modes": {"CONTRADICT": .34, "ERASE": .18, "REVISIT": .16},
        "styles": {"jitter","fracture","scribble","zigzag","cluster","hook"},
    },
    "MONUMENTAL": {
        "density_scale": .66, "family_cap": 4,
        "modes": {"ABSTRACT_BUILD": .26, "CONNECT": .22, "CONTRADICT": .20},
        "styles": {"bold","sweep","web","starburst","branch","blob"},
    },
    "ASCETIC": {
        "density_scale": .50, "family_cap": 4,
        "modes": {"NEGATIVE_SPACE": .42, "REVISIT": .20, "ERASE": .18},
        "styles": {"accent","contour","hook","segmented","fine"},
    },
    "DECAYING": {
        "density_scale": .64, "family_cap": 5,
        "modes": {"ERASE": .36, "CONTRADICT": .26, "REVISIT": .18},
        "styles": {"fracture","charcoal","scribble","jitter","segmented","contour"},
    },
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
    zebracnsActivity: dict[str, Any] = Field(default_factory=dict)
    zebracnsCriticPressure: float = Field(default=0.0, ge=-.42, le=.42)
    artisticTemperament: str = ""
    artPolicy: dict[str, Any] = Field(default_factory=dict)


@dataclass
class CandidateFlyBrain(ProceduralFlyBrain):
    """Generate alternatives, score them, then commit one selected future."""

    def __post_init__(self):
        super().__post_init__()
        self.mode = "LOCAL PROCEDURAL FLY BRAIN · CANDIDATE PAINTER · MEMORY + CONTEXT"
        self._candidate_serial = 0
        self._explicit_forms: list[tuple[int, str]] = []
        experience = self.experience or {}
        self.agent_profile = normalize_agent_profile(experience.get("_agent_profile"))
        self.agent_spec = get_agent_profile(self.agent_profile)
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
        self._art_history: list[dict[str, Any]] = []
        # ZebraCNS is an in-loop critic: it can pressure artistic candidate
        # ranking and finish timing, but never writes stroke mechanics directly.
        # Keep the critic bounded so disagreement changes the work without
        # replacing the Fly as the final actor.
        self.zebracns_strength=max(0.0,min(0.40,float(os.environ.get("JPGFLY_ZEBRACNS_STRENGTH",".26") or .26)))
        self.last_zebracns_state: dict[str, Any] = {}
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
        recent_temperaments=[
            str(room.get("artistic_temperament") or "")
            for room in self.recent_rooms[-4:]
            if room.get("artistic_temperament")
        ]
        temperament_pool=[name for name in ARTISTIC_TEMPERAMENTS if name not in recent_temperaments]
        self.artistic_temperament=self.rng.choice(temperament_pool or list(ARTISTIC_TEMPERAMENTS))
        temperament=ARTISTIC_TEMPERAMENTS[self.artistic_temperament]
        self.target_families=min(int(getattr(self,"target_families",6) or 6),int(temperament["family_cap"]))
        self.density=max(.10,min(.86,float(self.density)*float(temperament["density_scale"])))
        if self.artistic_temperament in {"VIOLENT_MINIMAL","ASCETIC","DECAYING"}:
            self.personality["eraseBias"]=max(float(self.personality.get("eraseBias",0)),.23)
            self.personality["crowdAvoidance"]=max(float(self.personality.get("crowdAvoidance",0)),.76)
        if self.artistic_temperament=="OBSESSIVE":
            self.personality["returnBias"]=max(float(self.personality.get("returnBias",0)),.84)
        if self.artistic_temperament=="MONUMENTAL":
            self.personality["scaleBias"]=max(float(self.personality.get("scaleBias",0)),.74)

    def _apply_agent_profile(self, action: BrainAction, index: int) -> BrainAction:
        """Constrain a proposal to the room-born artist's declared vocabulary."""
        spec = self.agent_spec
        if self.agent_profile == "jpgfly":
            return action
        serial = max(0, int(self.decision_count)) + int(index)
        styles = tuple(spec.get("styles") or ())
        brushes = tuple(spec.get("brushes") or ())
        techniques = tuple(spec.get("techniques") or ())
        palettes = tuple(spec.get("palettes") or ())
        if styles:
            action.movementStyle = styles[(serial * 3 + index) % len(styles)]
        if brushes:
            action.brushTool = brushes[(serial * 5 + index) % len(brushes)]
        if techniques:
            action.technique = techniques[(serial * 7 + index) % len(techniques)]
        if palettes:
            palette = palettes[(serial + index) % len(palettes)]
            action.paletteName = palette
            colors = tuple(PALETTE_PRESETS.get(palette) or ())
            if colors:
                action.color = colors[(serial * 2 + index) % len(colors)]
        if self.agent_profile == "dreamfly":
            action.eraseIntent = False if serial % 5 else action.eraseIntent
        return action

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
            "material_style": str(getattr(self, "material_style", "ink_line") or "ink_line"),
            "render_effect": str(getattr(self, "render_effect", "MATTE") or "MATTE"),
            "paint_depth": round(float(getattr(self, "paint_depth", .08) or .08), 3),
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
            "zebracns": self._zebracns_public_activity(self.last_zebracns_state),
            "zebracns_art_bias_strength": round(self.zebracns_strength, 4),
            "artistic_temperament": self.artistic_temperament,
            "art_policy": get_art_policy().status(),
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

        # Concrete rooms must visibly contain recognizable things. Abstract
        # marks still surround and mutate those things, but they are no longer
        # allowed to dominate every decision.
        subject_name = str(getattr(clone, "subject_program_name", "") or "")
        readability = str(getattr(clone, "readability_mode", "") or "")
        subject_led = subject_name in set(CONCRETE_SUBJECT_PROGRAMS) or form in set(CONCRETE_MOTIFS)

        subject_bias = 0.24 if subject_led else 0.035
        if subject_name in {"AFTER_DARK","AFTER_DARK_EXTENDED","CRYPTO_MARKET","DEGEN_TERMINAL","PEOPLE_AND_POSES","PEOPLE_EVERYWHERE"}:
            subject_bias += 0.08

        explicit_probability = 0.08 + subject_bias
        if phase in {"STRUCTURE", "DEVELOPMENT"}:
            explicit_probability += 0.10
        elif phase in {"CONTRAST", "REFINEMENT"}:
            explicit_probability += 0.055
        elif phase == "EXPLORATION":
            explicit_probability *= 0.72
        elif phase == "RESOLUTION":
            explicit_probability *= 0.48

        if readability == "LITERAL":
            explicit_probability += 0.14
        elif readability == "STYLIZED":
            explicit_probability += 0.08
        elif readability in {"HIDDEN", "MUTATED"}:
            explicit_probability *= 0.76

        # Never let a concrete room go dozens of decisions without a readable anchor.
        if subject_led and explicit_gap >= 12 and phase not in {"RESOLUTION"}:
            if not recent_same or clone.rng.random() < 0.58:
                return "EXPLICIT", form

        if explicit_gap < 5:
            explicit_probability *= 0.18
        elif explicit_gap < 9:
            explicit_probability *= 0.55
        if recent_same:
            explicit_probability *= 0.44

        explicit_probability = max(0.035, min(0.56, explicit_probability))
        if clone.rng.random() < explicit_probability:
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
            "families": families >= 3,
            "intersections": intersections >= 4,
            "meaningful": meaningful >= 0.30,
            "modes": len(self._mode_counts) >= 3,
            "brushes": len(self._brush_counts) >= 2,
            "techniques": len(self._technique_counts) >= 2,
            "context_passes": len(self._context_counts) >= 4,
            "editing": sum(int(self._mode_counts.get(name,0) or 0) for name in ("ERASE","CONTRADICT","NEGATIVE_SPACE")) >= max(8,int(self.decision_count*.055)),
            "composition": composition_score >= 0.56,
            "spread": regional_spread >= 0.24,
            "director": director_ready,
            "readiness": readiness >= 0.68,
        }
        artistic_signals = sum(
            1 for key in (
                "coverage","regions","families","intersections","meaningful",
                "modes","brushes","techniques","editing","composition","spread"
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

    @staticmethod
    def _zebracns_public_activity(state: dict[str, Any] | None) -> dict[str, Any]:
        if not state:
            return {}
        signals=state.get("signals") if isinstance(state.get("signals"),dict) else {}
        return {
            "dataset": str(state.get("dataset") or "")[:120],
            "frame": int(state.get("frame",0) or 0),
            "sampled_neurons": int(state.get("sampled_neurons",0) or 0),
            "action": str(state.get("action") or "NONE")[:24],
            "signals": {
                key: round(max(0.0,min(1.0,float(signals.get(key,0) or 0))),4)
                for key in (
                    "arousal","persistence","exploration","novelty_seek",
                    "attention_lock","escape_drive","repetition_drive",
                    "state_instability","completion_pressure","tempo"
                )
            },
        }

    def _zebracns_candidate_bias(
        self,
        action: BrainAction,
        mode: str,
        form_mode: str,
        state: dict[str, Any] | None,
    ) -> float:
        """High-level state bias only; never rewrites physical stroke mechanics."""
        if not state or self.zebracns_strength<=0:
            return 0.0
        signals=state.get("signals") if isinstance(state.get("signals"),dict) else {}
        def sig(name,default=0.0):
            try:return max(0.0,min(1.0,float(signals.get(name,default) or 0)))
            except (TypeError,ValueError):return default
        novelty=sig("novelty_seek",sig("exploration",0.0))
        persistence=sig("persistence")
        attention=sig("attention_lock")
        escape=sig("escape_drive")
        repetition=sig("repetition_drive")
        instability=sig("state_instability",sig("exploration",0.0))
        completion=sig("completion_pressure")
        bias=0.0
        if mode=="CONTRADICT":bias+=novelty*.72+escape*.34+instability*.58
        elif mode=="NEGATIVE_SPACE":bias+=novelty*.34+escape*.76
        elif mode=="REVISIT":bias+=persistence*.66+attention*.58+repetition*.42-novelty*.16
        elif mode=="CONNECT":bias+=persistence*.34+attention*.26+repetition*.18
        elif mode=="ERASE":bias+=instability*.25+escape*.18
        elif mode=="ABSTRACT_BUILD":bias+=novelty*.24+sig("arousal")*.12
        elif mode=="FINISH":bias+=completion*1.18+persistence*.16-novelty*.56-instability*.42
        transform=str(getattr(action,"motifTransform","none") or "none")
        if transform in {"repeat","loose_mirror","extend"}:bias+=repetition*.24
        if transform in {"interrupt","cross","distort"}:bias+=instability*.22+novelty*.18
        if form_mode=="EXPLICIT":bias-=novelty*.10
        # The critic can matter, but one neural frame must never dominate the
        # rest of the candidate score. Both positive and negative pressure are
        # capped before the Fly makes its final choice.
        return max(-.42,min(.42,bias*self.zebracns_strength))

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

        if self.agent_profile != "jpgfly":
            spec = self.agent_spec
            score += 1.15 if action.movementStyle in set(spec.get("styles") or ()) else -4.5
            score += .72 if action.brushTool in set(spec.get("brushes") or ()) else -2.4
            score += .48 if action.technique in set(spec.get("techniques") or ()) else -1.6
            score += float((spec.get("form_bias") or {}).get(form_mode, 0.0))

        # Vision is advisory and only scores future candidates; it never
        # executes strokes or participates in finish-quality validation.
        vision = observation.get("visionComposition") or {}
        if isinstance(vision, dict) and vision:
            goal = str(vision.get("nextGoal") or "")
            goal_modes = {
                "CONNECT_SUBJECTS": {"CONNECT": .95, "REVISIT": .42, "ABSTRACT_BUILD": -.42},
                "STRENGTHEN_FOCAL": {"REVISIT": .78, "CONNECT": .34, "ABSTRACT_BUILD": -.24},
                "CLARIFY_SUBJECT": {"REVISIT": .70, "CONNECT": .28, "ABSTRACT_BUILD": -.38},
                "BUILD_DEPTH": {"REVISIT": .42, "CONTRADICT": .48, "CONNECT": .28},
                "OPEN_NEGATIVE_SPACE": {"NEGATIVE_SPACE": .86, "ERASE": .62, "ABSTRACT_BUILD": -.52},
                "DEVELOP_COUNTERWEIGHT": {"CONNECT": .58, "CONTRADICT": .52},
                "SIMPLIFY": {"ERASE": .72, "NEGATIVE_SPACE": .48, "ABSTRACT_BUILD": -.62},
                "RESOLVE": {"REVISIT": .46, "CONNECT": .34, "ERASE": .28, "ABSTRACT_BUILD": -.46},
            }
            score += float(goal_modes.get(goal, {}).get(mode, 0.0))
            try:
                target = vision.get("target") or [.5, .5]
                secondary = vision.get("secondaryTarget") or target
                chosen = secondary if context_pass in {"COUNTER","INTEGRATE"} and mode in {"CONNECT","CONTRADICT","ABSTRACT_BUILD"} else target
                tx = max(0.0,min(1.0,float(chosen[0]))) * 800.0
                ty = max(0.0,min(1.0,float(chosen[1]))) * 500.0
                pos = observation.get("currentForelegPosition") or [400,250]
                px,py=float(pos[0]),float(pos[1])
                heading=float(action.targetDirection)
                distance=max(0.0,float(action.movementDistance))
                ex=px+math.cos(heading)*distance
                ey=py+math.sin(heading)*distance
                before=math.hypot(tx-px,ty-py)
                after=math.hypot(tx-ex,ty-ey)
                score += max(-.55,min(.72,(before-after)/180.0))
            except (TypeError,ValueError,IndexError):
                pass
            try:
                readability=float(vision.get("readability",1) or 1)
                relations=float(vision.get("relations",1) or 1)
                if form_mode=="EXPLICIT" and readability<.58:
                    score += (.58-readability)*1.15
                if mode=="CONNECT" and relations<.62:
                    score += (.62-relations)*1.30
            except (TypeError,ValueError):
                pass

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
            score += 0.34 if form_mode == "EXPLICIT" else 0.18 if form_mode in {"HINT","FRAGMENT","MUTATION"} else 0.12 if mode in {"ABSTRACT_BUILD","NEGATIVE_SPACE"} else 0

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
            # Coherence beats tool collecting. Reusing an established brush is
            # slightly favored; introducing a third+ brush is actively discouraged.
            if brush_seen > 0:
                score += .10
            elif len(self._brush_counts) >= 2:
                score -= .42
            elif len(self._brush_counts) == 1:
                score -= .10
            if technique_seen > 0:
                score += .05
            elif len(self._technique_counts) >= 3:
                score -= .18

        if form_mode == "HINT":
            score += 0.05
        elif form_mode == "FRAGMENT":
            score += 0.08 + float(getattr(self, "mutation", 0.4)) * 0.05
        elif form_mode == "MUTATION":
            score += 0.10 + float(getattr(self, "mutation", 0.4)) * 0.08
        elif form_mode == "EXPLICIT":
            concrete_form = suggested_form in set(CONCRETE_MOTIFS)
            concrete_room = str(getattr(clone, "subject_program_name", "") or "") in set(CONCRETE_SUBJECT_PROGRAMS)

            # Concrete subjects are a core visual language, not a failure mode.
            # Previous builds penalized EXPLICIT by -1.7 (and another -1.0 early),
            # which made the selector discard faces/objects even when generated.
            if concrete_form or concrete_room:
                score += 0.92
                if context_pass in {"GROUND","ECHO","COUNTER","INTEGRATE"}:
                    score += 0.28
                if coverage < 0.38:
                    score += 0.22
            else:
                score -= 0.18

            # Repetition is still discouraged, but a readable subject is not.
            if any(suggested_form == old for _, old in self._explicit_forms[-4:]):
                score -= 0.48

        temperament=ARTISTIC_TEMPERAMENTS.get(self.artistic_temperament,{})
        score+=float((temperament.get("modes") or {}).get(mode,0) or 0)
        if action.movementStyle in set(temperament.get("styles") or ()):
            score+=.24
        if len(self.style_counts)>=self.target_families and action.movementStyle not in self.style_counts:
            score-=.58
        if self.decision_count>36:
            if len(self._brush_counts)>=2 and action.brushTool not in self._brush_counts:
                score-=.58
            elif action.brushTool in self._brush_counts:
                score+=.08
            if len(self._technique_counts)>=3 and action.technique not in self._technique_counts:
                score-=.22

        regional=float(observation.get("regionalContrast",0) or 0)
        if regional<.12 and mode in {"CONTRADICT","NEGATIVE_SPACE"}:
            score+=.20
        elif regional>.72 and mode in {"CONNECT","REVISIT"}:
            score+=.16

        if context_pass=="EDIT_RESOLVE":
            if mode in {"ERASE","NEGATIVE_SPACE","REVISIT"}:
                score+=.18
            if mode=="ABSTRACT_BUILD":
                score-=.24

        if self.artistic_temperament in {"VIOLENT_MINIMAL","ASCETIC"}:
            if coverage>.46 and mode=="ABSTRACT_BUILD":
                score-=.42
            if coverage>.34 and mode in {"NEGATIVE_SPACE","ERASE"}:
                score+=.28
        elif self.artistic_temperament=="MONUMENTAL":
            if float(action.movementDistance or 0)>=70:
                score+=.20
            if float(action.scale or 1)>=1.15:
                score+=.16

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
            artisticTemperament=self.artistic_temperament,
            artPolicy=get_art_policy().status(),
        )

    def decide(self, request: BrainRequest, limits: BrainLimits):
        observation = request.observation
        zebra_state=artistic_zebracns_state()
        self.last_zebracns_state=zebra_state
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
                zebracnsActivity=self._zebracns_public_activity(zebra_state),
                zebracnsCriticPressure=self._zebracns_candidate_bias(action,"FINISH","NONE",zebra_state),
                artisticTemperament=self.artistic_temperament,
                artPolicy=get_art_policy().status(),
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
            action = clone._apply_agent_profile(action, index)
            mode = self._decision_mode(action)
            form_mode, suggested_form = self._form_mode(action, clone, index)
            if clone.agent_profile == "dreamfly" and form_mode == "EXPLICIT":
                form_mode = "MUTATION"
            score = self._candidate_score(
                action, observation, mode, form_mode, suggested_form, clone, index, context_pass
            )
            score += self._zebracns_candidate_bias(action,mode,form_mode,zebra_state)
            policy_vote=get_art_policy().vote(art_policy_features(
                observation,action.model_dump(),mode,context_pass,zebra_state,
                history=self._art_history[-8:],room_context={"artistic_temperament":self.artistic_temperament},
            ))
            score += float(policy_vote.get("value_vote",0) or 0)
            current_tension=(float(observation.get("densityContrast",0) or 0)+float(observation.get("regionalContrast",0) or 0))*.5
            overwork=float(observation.get("overworkRisk",0) or 0);revision=float(observation.get("revisionPotential",0) or 0);hierarchy=float(observation.get("hierarchyStrength",0) or 0)
            if current_tension<.34:score += max(0.0,float(policy_vote.get("tension",0) or 0))*.26
            elif current_tension>.66:score += max(0.0,-float(policy_vote.get("tension",0) or 0))*.18
            restraint=float(policy_vote.get("restraint",0) or 0)
            if overwork>.44 and restraint>0:score += restraint*.24 if mode in {"NEGATIVE_SPACE","ERASE","REVISIT"} else -restraint*.12
            elif float(observation.get("canvasOccupancy",0) or 0)<.20 and restraint<0 and mode in {"ABSTRACT_BUILD","CONNECT"}:score += (-restraint)*.18
            edit_bias=float(policy_vote.get("edit_bias",0) or 0)
            if revision>.42 and edit_bias>0 and mode in {"ERASE","CONTRADICT","NEGATIVE_SPACE"}:score += edit_bias*.24
            focus=float(policy_vote.get("focus_commitment",0) or 0)
            if hierarchy<.42 and focus>0 and mode in {"REVISIT","CONNECT"}:score += focus*.20
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
            finish_score += self._zebracns_candidate_bias(finish_action,"FINISH","NONE",zebra_state)
            finish_policy=get_art_policy().vote(art_policy_features(observation,finish_action.model_dump(),"FINISH",context_pass,zebra_state,history=self._art_history[-8:],room_context={"artistic_temperament":self.artistic_temperament}))
            finish_score += float(finish_policy.get("value_vote",0) or 0)
            if float(observation.get("overworkRisk",0) or 0)>.55:finish_score += max(0.0,float(finish_policy.get("restraint",0) or 0))*.22
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
        if zebra_state:
            action.zebracnsActivity=self._zebracns_public_activity(zebra_state)
            action.zebracnsCriticPressure=self._zebracns_candidate_bias(
                chosen["action"],chosen["mode"],chosen["form_mode"],zebra_state
            )
            zebra_label=" · ZEBRA CRITIC" if self.zebracns_strength<=0 else " · ZEBRA CRITIC LOOP"
            self.mode="LOCAL PROCEDURAL FLY BRAIN · CANDIDATE PAINTER · MEMORY + CONTEXT"+zebra_label
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
                zebra_label=(" · ZEBRA CRITIC" if self.zebracns_strength<=0 else " · ZEBRACNS ART BIAS") if zebra_state else ""
                self.mode="LOCAL PROCEDURAL FLY BRAIN · CANDIDATE PAINTER · MEMORY + CONTEXT"+zebra_label+" · MALECNS"

        # Qwen/FLM are support nodes around the local art brain. If those nodes
        # are unreachable, keep painting locally but identify the session
        # truthfully as DUMB DUMB fallback. The label automatically clears when
        # the support layer becomes reachable again.
        if not _support_nodes_online():
            self.mode="DUMB DUMB MODE · PURE PYTHON FALLBACK"
        elif "DUMB DUMB MODE" in str(self.mode).upper():
            zebra_label=(" · ZEBRA CRITIC" if self.zebracns_strength<=0 else " · ZEBRACNS ART BIAS") if zebra_state else ""
            self.mode="LOCAL PROCEDURAL FLY BRAIN · CANDIDATE PAINTER · MEMORY + CONTEXT"+zebra_label+(" · MALECNS" if action.malecnsActivity else "")
        self._art_history.append({"observation":dict(observation),"action":action.model_dump()})
        self._art_history=self._art_history[-16:]
        return action


def _experience_without_literal_motif_lockin(experience: dict[str, Any] | None) -> dict[str, Any]:
    value = dict(experience or {})
    # Historical rooms may contain literal motif counts. Do not feed those concrete
    # object frequencies back into the next room as a preference.
    value["motifs"] = {}
    return value


def create_fly_brain(seed, *, complexity=.96, mutation=.42, density=.64, experience=None, agent_profile="jpgfly"):
    # One painting authority for every room-born artist. Qwen remains an
    # advisory vision/composition service; it is never swapped in as a second
    # stroke-producing brain because that would bypass agent vocabularies,
    # room memory and the candidate-selection invariants.
    agent_profile = normalize_agent_profile(agent_profile)
    if experience is None:
        try:
            from experience_memory import visual_bias
            experience = visual_bias()
        except Exception:
            experience = {}
    experience = dict(experience or {})
    experience["_agent_profile"] = agent_profile

    return CandidateFlyBrain(
        seed,
        complexity,
        mutation,
        density,
        _experience_without_literal_motif_lockin(experience),
    )


def configured_brain_mode():
    return "LOCAL PROCEDURAL FLY BRAIN · 8 CANDIDATES / MEMORY-CONTEXT CHOICE · QWEN VISION ADVISORY"
