import unittest

from composition_vision import _normalize_unit_value, _normalize_vision_payload, VisionComposition


class CompositionVisionNormalizationTests(unittest.TestCase):
    def test_common_model_scales_normalize_to_unit_interval(self):
        self.assertEqual(_normalize_unit_value(0.7), 0.7)
        self.assertEqual(_normalize_unit_value(3), 0.3)
        self.assertEqual(_normalize_unit_value(75), 0.75)
        self.assertEqual(_normalize_unit_value(-4), 0.0)
        self.assertEqual(_normalize_unit_value(400), 1.0)

    def test_out_of_range_model_payload_becomes_schema_valid(self):
        raw = {
            "composition_score": 3,
            "focal_strength": 8,
            "balance": 65,
            "relation_coherence": 0.4,
            "subject_readability": 9,
            "negative_space_quality": 40,
            "depth": 5,
            "next_goal": "STRENGTHEN_FOCAL",
            "target_x": 7,
            "target_y": 25,
            "secondary_x": 0.2,
            "secondary_y": 80,
            "structure": "ASYMMETRIC",
            "flow": "primary to counterweight",
            "avoid": "clutter",
            "note": "continue",
        }
        parsed = VisionComposition.model_validate(_normalize_vision_payload(raw))
        compact = parsed.compact()
        self.assertEqual(compact["score"], 0.3)
        self.assertEqual(compact["focal"], 0.8)
        self.assertEqual(compact["balance"], 0.65)
        self.assertEqual(compact["target"], [0.7, 0.25])
        self.assertEqual(compact["secondaryTarget"], [0.2, 0.8])


if __name__ == "__main__":
    unittest.main()
