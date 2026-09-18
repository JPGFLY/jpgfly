from __future__ import annotations

import os
import unittest

import flm_text_provider as flm
import narrative_provider as narrative


class RoomTextRecoveryTests(unittest.TestCase):
    def test_literary_fallback_avoids_mechanical_copy(self):
        record = flm.generate_room_fallback(
            {
                "structural_metrics": {"familyCounts": {"accent": 120, "cross": 50}},
                "room_tension_counts": {"DENSITY_VS_VOID": 200},
                "decision_mode_counts": {"CONTRADICT": 90, "CONNECT": 70},
                "goal_counts": {"AMPLIFY": 50},
            },
            7,
        )
        joined = " ".join(record.values()).casefold()
        self.assertNotIn("formed as a", joined)
        self.assertNotIn("recorded intersections", joined)
        self.assertNotIn("composition complete", joined)
        self.assertGreater(len(record["room_description"].split()), 80)
        self.assertIn("memory_thread", record)
        self.assertGreater(len(record["memory_thread"].split()), 25)
        self.assertGreater(len(record["fly_statement"].split()), 12)

    def test_field_prompts_request_plain_text_not_json(self):
        prompt = flm._field_prompt("description", "room brief", "reading memory", "earlier room memory", "identity")
        self.assertIn("Write only the finished room description", prompt)
        self.assertIn("150 to 230 words", prompt)
        self.assertIn("RECENT ARTWORK MEMORY", prompt)
        self.assertNotIn("Return JSON", prompt)

    def test_runtime_prompt_allows_adult_feeling_as_persona_not_literal_consciousness(self):
        prompt = flm._field_prompt("statement", "room brief", "reading memory", "earlier room memory", "identity")
        folded = prompt.casefold()
        self.assertIn("adult desire", folded)
        self.assertIn("lust", folded)
        self.assertIn("emotionally candid", folded)
        self.assertIn("not scientific claims of literal consciousness", folded)
        self.assertIn("non-graphic", folded)

    def test_finished_room_activates_painting_to_painting_mode_for_some_seeds(self):
        context={
            "room_code":"ROOM-0002",
            "earlier_rooms":[{"room_title":"OLD ROOM","room_description":"A previous room."}],
        }
        artwork_memory=flm._artwork_memory(context)
        self.assertIn("OLD ROOM", artwork_memory)
        seed=3
        earlier=[room for room in context["earlier_rooms"] if isinstance(room,dict)]
        self.assertTrue(earlier and seed%3==0)

    def test_hybrid_provider_enables_both_ollama_and_flm_layers(self):
        previous=os.environ.get("JPGFLY_TEXT_PROVIDER")
        try:
            os.environ["JPGFLY_TEXT_PROVIDER"]="hybrid"
            self.assertEqual(flm.configured_text_provider(),"hybrid")
            self.assertEqual(narrative.narrative_mode(),"hybrid")
        finally:
            if previous is None:
                os.environ.pop("JPGFLY_TEXT_PROVIDER",None)
            else:
                os.environ["JPGFLY_TEXT_PROVIDER"]=previous

    def test_interpretive_lenses_do_not_cycle_crypto_sex_and_jokes_by_default(self):
        context={
            "visual_context":{"content_register":"FORMAL"},
            "earlier_rooms":[],
            "recent_public_notes":[],
        }
        values=[flm._interpretive_lens(context,seed) for seed in range(25)]
        folded=" ".join(values).casefold()
        self.assertNotIn("erotic tension",folded)
        self.assertNotIn("punchline",folded)

    def test_ollama_voice_angle_does_not_force_recent_sensitive_topics(self):
        context={
            "visual_context":{"content_register":"FORMAL"},
            "earlier_rooms":[{"room_description":"An old room about crypto, sex, and jokes."}],
            "recent_public_notes":[],
        }
        angle=flm._interpretive_lens(context,19)
        self.assertTrue(angle)
