from __future__ import annotations

import unittest

import app as jpgfly


class ArchiveSearchTests(unittest.TestCase):
    def setUp(self):
        jpgfly.ARTWORKS.clear()
        jpgfly.ARTWORKS.update({
            "a": {
                "session_id": "a",
                "room_code": "ROOM-0001",
                "room_title": "Borrowed Face",
                "room_description": "A mask-like contour becomes a face.",
                "anomaly_report": "One eye belongs to an older gesture.",
                "fly_statement": "The room accused me of a person.",
                "concept": "identity and mistaken recognition",
                "thought_fragments": ["keep the damaged contour"],
                "public_commentary": [{"text": "A face is forming badly."}],
                "structural_metrics": {"markFamilies": ["contour", "scribble"]},
                "completed_at": "2026-09-12T20:00:00+00:00",
            },
            "b": {
                "session_id": "b",
                "room_code": "ROOM-0002",
                "room_title": "Center Charges Interest",
                "room_description": "A spiral begins to behave like value.",
                "anomaly_report": "Two loops share a center.",
                "fly_statement": "The middle started acting rich.",
                "concept": "money, agreement and attention",
                "thought_fragments": ["orbit the dense center"],
                "public_commentary": [{"text": "The center is hoarding attention."}],
                "structural_metrics": {"markFamilies": ["orbit", "spiral"]},
                "completed_at": "2026-09-12T21:00:00+00:00",
            },
        })

    def tearDown(self):
        jpgfly.ARTWORKS.clear()

    def test_search_title_description_statement_and_commentary(self):
        self.assertEqual(jpgfly.archive_artworks(q="borrowed")["total"], 1)
        self.assertEqual(jpgfly.archive_artworks(q="mask")["total"], 1)
        self.assertEqual(jpgfly.archive_artworks(q="rich")["total"], 1)
        self.assertEqual(jpgfly.archive_artworks(q="hoarding")["total"], 1)

    def test_multiword_search_requires_all_terms(self):
        result = jpgfly.archive_artworks(q="money attention")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["artworks"][0]["session_id"], "b")

    def test_structural_metadata_is_searchable(self):
        self.assertEqual(jpgfly.archive_artworks(q="scribble")["total"], 1)
        self.assertEqual(jpgfly.archive_artworks(q="spiral")["total"], 1)


if __name__ == "__main__":
    unittest.main()
