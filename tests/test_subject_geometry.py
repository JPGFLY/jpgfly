import unittest
import base64
from unittest.mock import patch

from brain_provider import FIGURATIVE_MOTIFS, SUBJECT_PROGRAMS, BrainRequest, BrainLimits
from candidate_brain import CandidateFlyBrain
from composition_vision import VisionComposition, render_canvas_preview
from server_mechanics import FIGURE_MOTIFS, FIGURE_SHAPES, compound_figurative_parts, ServerCanvasMechanics
from app import validate_mechanical_trace
from subject_catalog import DRAWABLE_ALIAS_BASE, DRAWABLE_PROGRAMS


class SubjectGeometryTests(unittest.TestCase):
    def test_every_brain_motif_has_server_geometry(self):
        missing = sorted(set(FIGURATIVE_MOTIFS) - set(FIGURE_MOTIFS))
        self.assertEqual(missing, [], f"brain motifs without geometry: {missing}")

    def test_every_subject_program_references_drawable_motifs(self):
        errors = {}
        for program, motifs in SUBJECT_PROGRAMS.items():
            missing = sorted(set(motifs) - set(FIGURE_MOTIFS))
            if missing:
                errors[program] = missing
        self.assertEqual(errors, {}, f"subject programs contain undrawable motifs: {errors}")

    def test_geometry_is_nontrivial(self):
        invalid = {}
        for motif in FIGURATIVE_MOTIFS:
            points = FIGURE_SHAPES.get(motif)
            if not isinstance(points, (list, tuple)) or len(points) < 4:
                invalid[motif] = "too few points"
                continue
            if not all(
                isinstance(point, (list, tuple))
                and len(point) == 2
                and all(isinstance(value, (int, float)) for value in point)
                for point in points
            ):
                invalid[motif] = "invalid point data"
        self.assertEqual(invalid, {}, f"invalid figurative geometry: {invalid}")

    def test_large_catalog_is_actually_large(self):
        self.assertGreaterEqual(len(DRAWABLE_ALIAS_BASE), 400)
        self.assertGreaterEqual(len(DRAWABLE_PROGRAMS), 12)

    def test_every_catalog_alias_has_valid_base_and_geometry(self):
        missing_bases = sorted(
            alias for alias, base in DRAWABLE_ALIAS_BASE.items()
            if base not in FIGURE_SHAPES
        )
        missing_aliases = sorted(
            alias for alias in DRAWABLE_ALIAS_BASE
            if alias not in FIGURE_MOTIFS
        )
        self.assertEqual(missing_bases, [], f"catalog aliases with missing bases: {missing_bases}")
        self.assertEqual(missing_aliases, [], f"catalog aliases without renderer geometry: {missing_aliases}")

    def test_every_large_catalog_subject_has_compound_parts(self):
        failures = {}
        for motif in DRAWABLE_ALIAS_BASE:
            parts = compound_figurative_parts(motif, [400, 250], 0.0, 100.0)
            if not isinstance(parts, list) or len(parts) < 2:
                failures[motif] = 0 if not parts else len(parts)
                continue
            if any(not isinstance(part, list) or len(part) < 2 for part in parts):
                failures[motif] = "invalid-part"
        self.assertEqual(failures, {}, f"catalog subjects collapsed to doodle paths: {failures}")

    def test_compound_subject_execution_emits_disconnected_strokes(self):
        mechanics = ServerCanvasMechanics(1234, "test-room")
        action = {
            "movementDistance": 110,
            "branchingDepth": 0,
            "brushDown": True,
            "eraseIntent": False,
            "motifHint": "TAXI",
            "targetDirection": 0.0,
            "curvature": 0.0,
            "movementStyle": "contour",
            "duration": 500,
            "hesitation": 20,
            "brushTool": "ink_line",
            "pressure": 0.7,
            "speed": 0.6,
            "color": "#111111",
            "phase": "DEVELOPMENT",
            "layerRole": "subject",
            "motifTransform": "none",
            "strokeCharacter": "clean",
            "scale": 1.0,
            "technique": "continuous",
            "compositionPass": "BUILD_PRIMARY",
            "macroIntent": "draw a recognizable car",
            "paletteName": "MONO_DIRTY",
            "materialStyle": "ink_line",
            "renderEffect": "MATTE",
            "paintDepth": 0.1,
        }
        events, change = mechanics.execute(action, 1)
        strokes = [event for event in events if event.get("type") == "stroke"]
        moves = [event for event in events if event.get("type") == "move"]
        self.assertGreaterEqual(len(strokes), 4)
        self.assertGreaterEqual(len(moves), 1)
        self.assertTrue(all(event.get("compoundSubject") is True for event in strokes))
        self.assertEqual(change.get("compoundSubject"), "TAXI")


    def test_compound_subject_trace_validates_as_one_brain_move(self):
        mechanics = ServerCanvasMechanics(1234, "compound-trace-test")
        action = {
            "intent": "MOVE",
            "movementDistance": 110,
            "branchingDepth": 0,
            "brushDown": True,
            "eraseIntent": False,
            "motifHint": "TAXI",
            "targetDirection": 0.0,
            "curvature": 0.0,
            "movementStyle": "contour",
            "duration": 500,
            "hesitation": 20,
            "brushTool": "ink_line",
            "pressure": 0.7,
            "speed": 0.6,
            "color": "#111111",
            "phase": "DEVELOPMENT",
            "layerRole": "subject",
            "motifTransform": "none",
            "strokeCharacter": "clean",
            "scale": 1.0,
            "technique": "continuous",
            "compositionPass": "BUILD_PRIMARY",
            "macroIntent": "draw a recognizable car",
            "paletteName": "MONO_DIRTY",
            "materialStyle": "ink_line",
            "renderEffect": "MATTE",
            "paintDepth": 0.1,
        }
        before = len(mechanics.events)
        mechanics.execute(action, 0)
        physical = mechanics.events[before:]
        events = mechanics.events[:before] + [{
            "type": "brain_decision",
            "timestamp": 100,
            "decision": 0,
            "intent": "MOVE",
        }] + physical
        session = {"brain_decisions": [{"action": action}]}
        validate_mechanical_trace(session, events)

    def test_compound_subject_points_stay_inside_canvas(self):
        for start in ([30,30], [770,30], [30,470], [770,470]):
            parts = compound_figurative_parts("TAXI", list(start), 1.2, 145)
            self.assertTrue(parts)
            for part in parts:
                for x, y in part:
                    self.assertGreaterEqual(x, 24)
                    self.assertLessEqual(x, 776)
                    self.assertGreaterEqual(y, 24)
                    self.assertLessEqual(y, 476)


    def test_concrete_room_commits_explicit_subjects_to_selected_actions(self):
        brain = CandidateFlyBrain(seed=20260916, complexity=.96, mutation=.42, density=.58, experience={})
        brain.subject_program_name = "CRYPTO_MARKET"
        brain.subject_program = SUBJECT_PROGRAMS["CRYPTO_MARKET"]
        brain.motif_theme = brain.subject_program[0]
        brain.motif_theme_hold = 0
        brain.next_intrusion = 0

        mechanics = ServerCanvasMechanics(20260916, "brain-renderer-test")
        selected = []
        compound_strokes = []

        with patch("candidate_brain.artistic_zebracns_state", return_value={}):
            for sequence in range(64):
                observation = mechanics.observe(sequence)
                action = brain.decide(BrainRequest(observation=observation), BrainLimits())

                if action.intent == "FINISH_ARTWORK":
                    break

                events, _ = mechanics.execute(action.model_dump(), sequence + 1)
                if action.motifMode == "EXPLICIT" and action.motifHint != "NONE":
                    selected.append(action.motifHint)
                    compound_strokes.extend(
                        event for event in events
                        if event.get("type") == "stroke" and event.get("compoundSubject")
                    )

        self.assertGreaterEqual(
            len(selected), 3,
            f"concrete room selected too few explicit subjects: {selected}",
        )
        self.assertGreaterEqual(
            len(compound_strokes), 6,
            f"explicit selections did not become enough visible compound strokes: {selected}",
        )
        self.assertTrue(
            all(motif in FIGURATIVE_MOTIFS for motif in selected),
            f"selected explicit motifs were not drawable: {selected}",
        )


    def test_room_brush_palette_is_small_and_coherent(self):
        brain = CandidateFlyBrain(seed=77, complexity=.92, mutation=.35, density=.56, experience={})
        self.assertGreaterEqual(len(brain.room_brushes), 1)
        self.assertLessEqual(len(brain.room_brushes), 3)

        mechanics = ServerCanvasMechanics(77, "brush-coherence-test")
        used = set()
        with patch("candidate_brain.artistic_zebracns_state", return_value={}):
            for sequence in range(48):
                observation = mechanics.observe(sequence)
                action = brain.decide(BrainRequest(observation=observation), BrainLimits())
                if action.intent == "FINISH_ARTWORK":
                    break
                if action.brushDown and not action.eraseIntent:
                    used.add(action.brushTool)
                mechanics.execute(action.model_dump(), sequence + 1)

        self.assertTrue(
            used.issubset(set(brain.room_brushes)),
            f"room escaped its brush palette: palette={brain.room_brushes}, used={sorted(used)}",
        )
        self.assertLessEqual(len(used), 3)

    def test_composition_vision_preview_is_png_and_schema_is_strict(self):
        preview=render_canvas_preview([
            [[80,80],[180,120],[250,95]],
            [[420,280],[500,240],[610,290]],
            [[250,95],[420,280]],
        ],current_position=[420,280])
        raw=base64.b64decode(preview)
        self.assertTrue(raw.startswith(bytes([137,80,78,71,13,10,26,10])))
        parsed=VisionComposition.model_validate({
            "composition_score":.55,
            "focal_strength":.4,
            "balance":.6,
            "relation_coherence":.3,
            "subject_readability":.5,
            "negative_space_quality":.7,
            "depth":.35,
            "next_goal":"CONNECT_SUBJECTS",
            "target_x":.52,
            "target_y":.48,
            "avoid":"new unrelated objects",
            "note":"connect the two masses",
        })
        compact=parsed.compact()
        self.assertEqual(compact["nextGoal"],"CONNECT_SUBJECTS")
        self.assertEqual(compact["target"],[.52,.48])

    def test_expanded_programs_are_present(self):
        for name in ("PEOPLE_AND_POSES", "AFTER_DARK", "DEGEN_TERMINAL", "EVERYDAY_REALITY"):
            self.assertIn(name, SUBJECT_PROGRAMS)
            self.assertGreaterEqual(len(SUBJECT_PROGRAMS[name]), 9)


if __name__ == "__main__":
    unittest.main()
