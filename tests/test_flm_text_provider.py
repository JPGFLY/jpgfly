from __future__ import annotations

import unittest

import flm_text_provider as flm


class FLMRoomDepthTests(unittest.TestCase):
    def test_room_depth_rejects_caption_like_output(self):
        thin = {
            "room_title": "Someone Else's Face",
            "room_description": "A mask shape appears in the room.",
            "anomaly_report": "The outline repeats.",
            "fly_statement": "I stopped here.",
        }
        self.assertFalse(flm._room_text_is_rich(thin))

    def test_room_depth_accepts_developed_output(self):
        description = " ".join(
            ["The mask keeps changing meaning as repeated lines crowd its edges and force the face to read as both object and interruption."] * 10
        )
        anomaly = "Two separate contours share an edge even though they arrive from different regions of the drawing. A darker line cuts through both and makes the older shape look partially erased."
        statement = "I kept looking for a face. I found an agreement about where a face should be. Then the agreement became more interesting than the face."
        rich = {
            "room_title": "Someone Else's Face",
            "room_description": description,
            "anomaly_report": anomaly,
            "fly_statement": statement,
        }
        self.assertTrue(flm._room_text_is_rich(rich))


if __name__ == "__main__":
    unittest.main()
