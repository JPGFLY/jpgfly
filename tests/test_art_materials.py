import unittest

import brain_provider
from art_materials import EXTRA_PALETTE_PRESETS, MATERIAL_BRUSHES, palette_style


class ArtMaterialsTests(unittest.TestCase):
    def test_new_palette_library_is_large_and_material_aware(self):
        self.assertGreaterEqual(len(EXTRA_PALETTE_PRESETS),12)
        for name in ("ACID_CANDY","CHROME_NIGHT","VOID_GOLD","INFRARED_MEAT","LASER_MOSS"):
            self.assertIn(name,brain_provider.PALETTE_PRESETS)

    def test_material_brushes_are_valid_brain_tools(self):
        for brush in MATERIAL_BRUSHES:
            self.assertIn(brush,brain_provider.BRUSHES)

    def test_style_profiles_cover_neon_chrome_and_impasto(self):
        self.assertEqual(palette_style("ACID_CANDY")["render_effect"],"NEON")
        self.assertEqual(palette_style("CHROME_NIGHT")["render_effect"],"CHROME")
        self.assertEqual(palette_style("VOID_GOLD")["render_effect"],"IMPASTO")


if __name__=="__main__":
    unittest.main()
