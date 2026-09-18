import unittest

from room_theme import THEMES, choose_room_theme


class RoomThemeTests(unittest.TestCase):
    def test_rotation_contains_requested_subjects(self):
        ids={item["id"] for item in THEMES}
        self.assertTrue({
            "DESIRE_AND_SEX",
            "ART_AND_ARTISTS",
            "POETRY_AND_LANGUAGE",
            "PHILOSOPHY",
            "HUMOR_AND_ABSURDITY",
            "CRYPTO_AND_TERMINAL",
        }.issubset(ids))

    def test_theme_is_deterministic_for_same_seed(self):
        context={"earlier_rooms":[]}
        self.assertEqual(choose_room_theme(context,1234),choose_room_theme(context,1234))

    def test_sex_is_not_confined_to_bodily_visual_register(self):
        context={"visual_context":{"content_register":"FORMAL"},"earlier_rooms":[]}
        found={choose_room_theme(context,seed)["id"] for seed in range(400)}
        self.assertIn("DESIRE_AND_SEX",found)
        self.assertIn("CRYPTO_AND_TERMINAL",found)
        self.assertIn("HUMOR_AND_ABSURDITY",found)

    def test_required_instruction_is_explicit(self):
        context={"earlier_rooms":[]}
        for seed in range(50):
            theme=choose_room_theme(context,seed)
            self.assertIn("PRIMARY SUBJECT:",theme["instruction"])
            self.assertIn(theme["id"],theme["instruction"])


if __name__=="__main__":
    unittest.main()
