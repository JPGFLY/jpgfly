from __future__ import annotations

import unittest

import brain_provider
import server_mechanics


class ShapeVocabularyTests(unittest.TestCase):
    def test_every_literal_brain_motif_has_server_geometry_and_theme(self):
        missing_geometry = sorted(set(brain_provider.FIGURATIVE_MOTIFS) - set(server_mechanics.FIGURE_MOTIFS))
        missing_theme = sorted(set(brain_provider.FIGURATIVE_MOTIFS) - set(brain_provider.MOTIF_THEMES))
        self.assertEqual(missing_geometry, [])
        self.assertEqual(missing_theme, [])

    def test_expanded_shape_library_is_broad(self):
        self.assertGreaterEqual(len(server_mechanics.FIGURE_MOTIFS), 70)
        for motif in (
            "CIRCLE","TRIANGLE","CUBE","MAZE","HAND","SKULL","DOG_FACE",
            "JELLYFISH","OCTOPUS","SUN","MOON","PLANET","HOUSE","STAIRCASE",
        ):
            self.assertIn(motif, server_mechanics.FIGURE_MOTIFS)

    def test_expanded_abstract_mark_families_are_available(self):
        for style in (
            "wave","zigzag","ribbon","vortex","rosette","maze",
            "meander","blob","fan","helix","scallop","scribble",
        ):
            self.assertIn(style, brain_provider.STYLES)

    def test_literal_primitive_respects_canvas(self):
        points = server_mechanics.figurative_primitive("OCTOPUS", [400, 250], 0.5, 150)
        self.assertTrue(points)
        self.assertLessEqual(len(points), 96)
        for x, y in points:
            self.assertGreaterEqual(x, server_mechanics.MARGIN)
            self.assertLessEqual(x, server_mechanics.CANVAS_WIDTH - server_mechanics.MARGIN)
            self.assertGreaterEqual(y, server_mechanics.MARGIN)
            self.assertLessEqual(y, server_mechanics.CANVAS_HEIGHT - server_mechanics.MARGIN)


if __name__ == "__main__":
    unittest.main()
