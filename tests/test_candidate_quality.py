from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from candidate_brain import CandidateFlyBrain, create_fly_brain
from brain_provider import BrainAction, BrainRequest, BrainLimits
from agent_profiles import get_agent_profile


class CandidateQualityTests(unittest.TestCase):
    def test_legacy_ollama_provider_setting_cannot_bypass_candidate_agent_brain(self):
        with patch.dict(os.environ,{"JPGFLY_BRAIN_PROVIDER":"ollama"},clear=False):
            brain=create_fly_brain(6,complexity=.9,mutation=.4,density=.6,agent_profile="dreamfly")
        self.assertIsInstance(brain,CandidateFlyBrain)
        self.assertEqual(brain.agent_profile,"dreamfly")

    def test_zebracns_is_bounded_in_loop_critic_by_default(self):
        with patch.dict(os.environ,{},clear=False):
            os.environ.pop("JPGFLY_ZEBRACNS_STRENGTH",None)
            brain=CandidateFlyBrain(5,.9,.4,.6,{})
        self.assertEqual(brain.zebracns_strength,.26)

    def test_zebracns_feedback_cannot_dominate_candidate_score(self):
        brain=CandidateFlyBrain(5,.9,.4,.6,{})
        action=BrainAction(
            intent="MOVE",targetDirection=0,movementDistance=20,curvature=0,speed=.5,duration=200,
            brushDown=True,pressure=.5,hesitation=0,exploration=.5,
            attentionTarget={"kind":"whole_canvas","point":[400,250]},eraseIntent=False,
            movementStyle="contour",relationshipToExistingMarks="test",confidence=.8,reason="test",phase="EXPLORATION",
        )
        extreme={"signals":{"novelty_seek":1,"exploration":1,"persistence":1,"attention_lock":1,"escape_drive":1,"repetition_drive":1,"state_instability":1,"completion_pressure":1,"arousal":1}}
        for mode in ("CONTRADICT","NEGATIVE_SPACE","REVISIT","CONNECT","ERASE","ABSTRACT_BUILD","FINISH"):
            value=brain._zebracns_candidate_bias(action,mode,"EXPLICIT",extreme)
            self.assertLessEqual(abs(value),.42)

    def test_specialist_agents_stay_inside_their_declared_visual_vocabularies(self):
        observation={
            "sequence":0,"canvasOccupancy":.22,"negativeSpace":.78,"intersections":4,
            "directionalUniformity":.28,"densityContrast":.26,"localDensity":.30,
            "repetition":.18,"meaningfulChangeRate":.82,"consecutiveLowChange":0,
            "physicalActionCount":0,"occupiedRegions":5,"regionalContrast":.28,
            "familyCounts":{},"currentForelegPosition":[400.,250.],
        }
        limits=BrainLimits(max_session_duration_ms=240000,max_brain_decisions=320,max_physical_actions=320,max_consecutive_low_change=60)
        for profile in ("sprayfly","dreamfly"):
            brain=CandidateFlyBrain(31,.9,.5,.62,{"_agent_profile":profile})
            action=brain.decide(BrainRequest(observation=observation),limits)
            spec=get_agent_profile(profile)
            self.assertEqual(action.intent,"MOVE")
            self.assertIn(action.movementStyle,spec["styles"])
            self.assertIn(action.brushTool,spec["brushes"])
            self.assertIn(action.technique,spec["techniques"])

    def test_sparse_room_cannot_finish_normally(self):
        brain = CandidateFlyBrain(42, .94, .46, .62, {})
        brain.decision_count = 80
        action = BrainAction(
            intent="FINISH_ARTWORK",
            targetDirection=0,
            movementDistance=0,
            curvature=0,
            speed=0,
            duration=0,
            brushDown=False,
            pressure=0,
            hesitation=0,
            exploration=0,
            attentionTarget={"kind":"whole_canvas","point":[400,250]},
            eraseIntent=False,
            movementStyle="contour",
            relationshipToExistingMarks="final_evaluation",
            confidence=1.0,
            reason="done",
            phase="RESOLUTION",
            evaluation={"readiness":.95,"finishReady":True},
        )
        ready, diagnostics = brain._finish_quality(
            {
                "canvasOccupancy": .06,
                "occupiedRegions": 1,
                "intersections": 0,
                "familyCounts": {"contour": 2},
                "meaningfulChangeRate": .8,
            },
            action,
        )
        self.assertFalse(ready)
        self.assertFalse(diagnostics["checks"]["coverage"])
        self.assertFalse(diagnostics["checks"]["regions"])

    def test_compositionally_developed_room_can_finish(self):
        brain = CandidateFlyBrain(42, .94, .46, .62, {})
        brain.decision_count = max(260, int(brain.desired_decisions*.68))
        brain._mode_counts = {"ABSTRACT_BUILD":40,"CONNECT":30,"REVISIT":20,"CONTRADICT":20}
        brain._brush_counts = {"ink_line":30,"dry_brush":20,"fine_pen":20,"soft_paint":20}
        brain._technique_counts = {"continuous":30,"hatching":20,"overpainting":20,"layered_glazing":20}
        brain._context_counts = {"GROUND":30,"ECHO":30,"COUNTER":30,"INTEGRATE":30}
        action = BrainAction(
            intent="FINISH_ARTWORK",
            targetDirection=0,
            movementDistance=0,
            curvature=0,
            speed=0,
            duration=0,
            brushDown=False,
            pressure=0,
            hesitation=0,
            exploration=0,
            attentionTarget={"kind":"whole_canvas","point":[400,250]},
            eraseIntent=False,
            movementStyle="contour",
            relationshipToExistingMarks="final_evaluation",
            confidence=1.0,
            reason="done",
            phase="RESOLUTION",
            evaluation={"readiness":.82,"finishReady":True,"compositionScore":.74,"regionalSpread":.58},
        )
        ready, diagnostics = brain._finish_quality(
            {
                "canvasOccupancy": .34,
                "occupiedRegions": 7,
                "intersections": 15,
                "familyCounts": {"contour":4,"scribble":4,"cross":3,"wave":2,"branch":2,"orbit":1,"lattice":1},
                "meaningfulChangeRate": .72,
            },
            action,
        )
        self.assertTrue(ready)
        self.assertTrue(diagnostics["checks"]["mature"])
        self.assertTrue(diagnostics["checks"]["context_passes"])
        self.assertTrue(diagnostics["checks"]["director"])
        self.assertGreaterEqual(diagnostics["artisticSignals"], 7)


    def test_finish_quality_accepts_vision_observation_without_scoring_side_effects(self):
        brain = CandidateFlyBrain(7, .9, .4, .6, {})
        brain.decision_count = max(220, int(brain.desired_decisions*.7))
        brain._mode_counts = {"CONNECT":20,"CONTRADICT":20,"REVISIT":20}
        brain._brush_counts = {"ink_line":20,"fine_pen":20}
        brain._technique_counts = {"continuous":20,"hatching":20}
        brain._context_counts = {"GROUND":10,"ECHO":10,"COUNTER":10,"INTEGRATE":10}
        action = BrainAction(intent="FINISH_ARTWORK",targetDirection=0,movementDistance=0,curvature=0,speed=0,duration=0,brushDown=False,pressure=0,hesitation=0,exploration=0,attentionTarget={"kind":"whole_canvas","point":[400,250]},eraseIntent=False,movementStyle="contour",relationshipToExistingMarks="final_evaluation",confidence=1,reason="done",phase="RESOLUTION",evaluation={"readiness":.8,"finishReady":True,"compositionScore":.7,"regionalSpread":.5})
        ready, diagnostics = brain._finish_quality({"canvasOccupancy":.3,"occupiedRegions":6,"intersections":10,"familyCounts":{"contour":4,"wave":3,"branch":2},"meaningfulChangeRate":.7,"visionComposition":{"nextGoal":"RESOLVE","target":[.5,.5],"relations":.7,"readability":.7}}, action)
        self.assertIsInstance(ready, bool)
        self.assertIn("checks", diagnostics)

    def test_reading_memory_changes_context_without_forcing_literal_forms(self):
        experience = {
            "rooms_seen": 8,
            "readings_seen": 5,
            "strength": .18,
            "conceptual_strength": .14,
            "conceptual_pressures": {"RETURN": .4, "ECHO": .3, "SYSTEM": .2, "RUPTURE": .1},
            "motifs": {"CHAIR": 1.0},
            "brushes": {"fine_pen": .6},
            "techniques": {"hatching": .6},
            "recent_rooms": [],
        }
        brain = CandidateFlyBrain(17, .97, .58, .68, experience)
        snapshot = brain.context_snapshot()
        self.assertIn("RETURN", snapshot["context_pressures"])
        self.assertGreater(snapshot["conceptual_memory_strength"], 0)
        self.assertEqual(brain.memory_context[0], "RETURN")

    def test_recent_room_identity_is_actively_avoided(self):
        recent_room = {
            "composition": [["SWARM", 20]],
            "palette": [["TOXIC_NEON", 20]],
            "subject_program": "INSECT_STUDY",
            "archetype": "TENSION_FIELD",
            "spatial_program": "CENTER_VOID",
            "stroke_dialect": "ANGULAR",
            "styles": [["cross", 20], ["fracture", 18]],
            "brushes": [["fine_pen", 20]],
            "techniques": [["hatching", 20]],
            "artistic_temperament": "NERVOUS",
        }
        experience={"recent_rooms":[recent_room],"strength":.2}
        brain=CandidateFlyBrain(22,.95,.55,.62,experience)
        snapshot=brain.context_snapshot()
        self.assertNotEqual(snapshot["artistic_temperament"],"NERVOUS")

    def test_duration_profiles_and_content_registers_vary_across_seeds(self):
        durations=set();registers=set()
        for seed in range(18):
            brain=CandidateFlyBrain(seed,.95,.5,.62,{})
            durations.add(brain.duration_profile)
            registers.add(brain.content_register)
        self.assertGreaterEqual(len(durations),3)
        self.assertGreaterEqual(len(registers),4)
