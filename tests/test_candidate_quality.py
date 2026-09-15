from __future__ import annotations

import unittest

from candidate_brain import CandidateFlyBrain
from brain_provider import BrainAction


class CandidateQualityTests(unittest.TestCase):
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
        self.assertTrue(all(diagnostics["checks"].values()))


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
            "room_tension": [["ORDER_VS_RUPTURE", 20]],
        }
        experience = {
            "rooms_seen": 4,
            "strength": .2,
            "recent_rooms": [recent_room, recent_room, recent_room],
            "palettes": {"TOXIC_NEON": 1.0},
            "composition_modes": {"SWARM": 1.0},
            "subject_programs": {"INSECT_STUDY": 1.0},
            "brushes": {"fine_pen": 1.0},
            "techniques": {"hatching": 1.0},
        }
        brain = CandidateFlyBrain(9127, .97, .58, .68, experience)
        identity = {
            brain.composition_mode,
            brain.palette_name,
            brain.subject_program_name,
            brain.archetype,
            brain.spatial_program,
            brain.stroke_dialect,
        }
        repeated = {
            "SWARM",
            "TOXIC_NEON",
            "INSECT_STUDY",
            "TENSION_FIELD",
            "CENTER_VOID",
            "ANGULAR",
        }
        self.assertGreaterEqual(len(identity - repeated), 4)
        snapshot = brain.context_snapshot()
        self.assertEqual(snapshot["spatial_program"], brain.spatial_program)
        self.assertEqual(snapshot["stroke_dialect"], brain.stroke_dialect)

    def test_duration_profiles_and_content_registers_vary_across_seeds(self):
        durations=set()
        registers=set()
        targets=[]
        for seed in range(40,60):
            brain=CandidateFlyBrain(seed,.9,.55,.62,{})
            durations.add(brain.duration_profile)
            registers.add(brain.content_register)
            targets.append(brain.desired_decisions)
        self.assertGreaterEqual(len(durations),3)
        self.assertGreaterEqual(len(registers),5)
        self.assertLess(min(targets),360)
        self.assertGreater(max(targets),650)

if __name__ == "__main__":
    unittest.main()
