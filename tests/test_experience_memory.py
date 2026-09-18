from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import experience_memory as memory


class ExperienceMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = os.environ.get("JPGFLY_DATA_DIR")
        os.environ["JPGFLY_DATA_DIR"] = self.temp.name

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("JPGFLY_DATA_DIR", None)
        else:
            os.environ["JPGFLY_DATA_DIR"] = self.previous
        self.temp.cleanup()

    def test_reading_builds_topic_memory_once(self):
        text = "The painting speaks about memory, death, money, Bitcoin and flies. " * 4
        first = memory.record_reading(text, source="essay.txt", title="Essay")
        second = memory.record_reading(text, source="essay.txt", title="Essay")
        self.assertEqual(first["readings_seen"], 1)
        self.assertEqual(second["readings_seen"], 1)
        self.assertGreater(first["topics"].get("art", 0), 0)
        self.assertGreater(first["topics"].get("crypto", 0), 0)
        self.assertGreater(first["topics"].get("insects", 0), 0)
        self.assertTrue(first["topic_passages"].get("dreams_memory"))

    def test_philosophy_adult_humor_and_crypto_terminal_topics(self):
        text = (
            "A philosopher jokes about desire and flesh while a transaction flashes across a terminal "
            "through a terminal shell. The hash enters a block, the nonce changes, an RPC call "
            "returns chain state, and the punchline is absurd."
        )
        data = memory.record_reading(text, source="topics.txt", title="Topics")
        self.assertGreater(data["topics"].get("philosophy", 0), 0)
        self.assertGreater(data["topics"].get("desire_body", 0), 0)
        self.assertGreater(data["topics"].get("humor_absurdity", 0), 0)
        self.assertGreater(data["topics"].get("crypto_terminal", 0), 0)

    def test_completed_room_creates_slow_visual_bias(self):
        record = {
            "session_id": "a" * 64,
            "room_code": "ROOM-0001",
            "room_title": "Chair Memory",
            "room_description": "A repeated chair crosses the room.",
            "completed_at": "2026-09-12T00:00:00+00:00",
            "provenance": {
                "completeFlyActionHistory": [
                    {"action": {
                        "intent": "MOVE",
                        "motifHint": "CHAIR",
                        "paletteName": "FUNERAL_NEON",
                        "compositionMode": "CORNER_NEST",
                        "autonomyGoal": "OBSESS",
                        "subjectProgram": "ROOM_OBJECTS",
                        "technique": "hatching",
                        "brushTool": "fine_pen",
                    }}
                    for _ in range(50)
                ]
            },
        }
        memory.record_room_experience(record)
        bias = memory.visual_bias()
        self.assertEqual(bias["rooms_seen"], 1)
        self.assertGreater(bias["strength"], 0)
        self.assertIn("CHAIR", bias["motifs"])
        self.assertIn("FUNERAL_NEON", bias["palettes"])
        # A single room is intentionally capped and cannot create full determinism.
        self.assertLessEqual(bias["strength"], 0.38)


    def test_recent_room_memory_preserves_agent_lineage_metadata(self):
        record = {
            "session_id":"c"*64,
            "room_code":"ROOM-0003",
            "room_title":"Spray Child",
            "agent_profile":"sprayfly",
            "agent_name":"SPRAYFLY",
            "spawned_from":"ROOM-0001",
            "completed_at":"2026-09-14T00:00:00+00:00",
            "structural_metrics":{"familyCounts":{"scribble":8}},
            "visual_context":{"style_counts":{"scribble":8}},
        }
        memory.record_room_experience(record)
        recent=memory.visual_bias()["recent_rooms"][-1]
        self.assertEqual(recent["agent_profile"],"sprayfly")
        self.assertEqual(recent["agent_name"],"SPRAYFLY")
        self.assertEqual(recent["spawned_from"],"ROOM-0001")

    def test_compact_room_can_rebuild_visual_memory_without_replay(self):
        record = {
            "session_id": "b" * 64,
            "room_code": "ROOM-0002",
            "room_title": "Compact Memory",
            "room_description": "A lattice returns as a damaged network.",
            "memory_thread": "The room carries a previous structural habit without copying the old image.",
            "completed_at": "2026-09-13T00:00:00+00:00",
            "structural_metrics": {
                "familyCounts": {"lattice": 22, "fracture": 9},
                "brushCounts": {"fine_pen": 18, "charcoal_grain": 7},
                "techniqueCounts": {"hatching": 18, "smudged_dragging": 7},
                "decisionModeCounts": {"REVISIT": 12, "CONTRADICT": 9},
                "contextPassCounts": {"GROUND": 8, "ECHO": 8, "COUNTER": 5},
            },
            "visual_context": {
                "palette_name": "FUNERAL_NEON",
                "composition_mode": "WEB_FIELD",
                "subject_program": "GEOMETRIC_RITUAL",
                "current_goal": "REVISIT",
                "room_tension": "ORDER_VS_RUPTURE",
                "style_counts": {"lattice": 22, "fracture": 9},
                "brush_counts": {"fine_pen": 18, "charcoal_grain": 7},
                "technique_counts": {"hatching": 18, "smudged_dragging": 7},
                "decision_mode_counts": {"REVISIT": 12, "CONTRADICT": 9},
                "context_pass_counts": {"GROUND": 8, "ECHO": 8, "COUNTER": 5},
            },
        }
        memory.record_room_experience(record)
        bias = memory.visual_bias()
        self.assertIn("FUNERAL_NEON", bias["palettes"])
        self.assertIn("WEB_FIELD", bias["composition_modes"])
        self.assertIn("fine_pen", bias["brushes"])
        self.assertIn("hatching", bias["techniques"])
        self.assertTrue(bias["recent_rooms"][0]["styles"])

    def test_readings_become_abstract_visual_pressure_not_literal_motifs(self):
        memory.record_reading(
            "Memory returns through dreams while a terminal network breaks into noise and absurd jokes.",
            source="pressure.txt",
            title="Pressure",
        )
        bias = memory.visual_bias()
        self.assertGreater(bias["conceptual_strength"], 0)
        self.assertIn("RETURN", bias["conceptual_pressures"])
        self.assertIn("SYSTEM", bias["conceptual_pressures"])
        self.assertNotIn("DREAM", bias["motifs"])

    def test_reading_folder_self_syncs(self):
        readings = Path(self.temp.name) / "readings"
        readings.mkdir(parents=True)
        (readings / "note.md").write_text(
            "Poetry, dreams and art return through memory.", encoding="utf-8"
        )
        compact = memory.compact_experience()
        self.assertEqual(compact["readings_seen"], 1)
        self.assertIn("poetry", compact["topics"])
        self.assertIn("dreams_memory", compact["topic_memory"])


if __name__ == "__main__":
    unittest.main()
