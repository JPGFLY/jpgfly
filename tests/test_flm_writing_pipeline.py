from __future__ import annotations

import unittest

import flm_text_provider as flm


class FLMWritingPipelineTests(unittest.TestCase):
    def test_room_brief_compacts_raw_context(self):
        brief = flm._room_brief(
            {
                "room_code": "ROOM-0012",
                "motif_counts": {"MASK": 12, "EYE": 4},
                "composition_mode_counts": {"CENTRAL_ICON": 20},
                "goal_counts": {"OBSESS": 8},
                "color_counts": {"#111111": 10, "#ff2d8d": 7},
                "structural_metrics": {"intersections": 22, "erasureActions": 3},
                "thought_fragments": ["The face keeps returning."],
                "public_commentary": [{"text": "This loop is becoming a face."}],
            }
        )
        self.assertIn("MASK:12", brief)
        self.assertIn("CENTRAL_ICON:20", brief)
        self.assertIn("The face keeps returning.", brief)
        self.assertLessEqual(len(brief), 2600)

    def test_candidate_score_penalizes_generic_telemetry_copy(self):
        good = {
            "room_title": "Borrowed Face",
            "room_description": " ".join([
                "The face assembled itself from marks that were never asked to become a portrait.",
                "A loop became an eye only after a later contour gave it something to belong to.",
                "Recognition is greedy that way, recruiting accidents until they start behaving like identity.",
            ] * 4),
            "anomaly_report": "An older loop becomes an eye only because a later contour surrounds it. A partly erased line still holds the lower face together.",
            "fly_statement": "I did not plan a person. The room accused me of one. I left the evidence incomplete.",
        }
        generic = {
            "room_title": "Abstract Composition",
            "room_description": "This artwork explores visual elements and creates a sense of movement. " * 16,
            "anomaly_report": "The composition features recorded intersections and visual elements. The artwork creates a sense of space.",
            "fly_statement": "I kept moving until the room stopped asking. I stopped. I am finished.",
        }
        self.assertGreater(flm._candidate_score(good), flm._candidate_score(generic))


if __name__ == "__main__":
    unittest.main()
