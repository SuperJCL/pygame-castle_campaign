"""Unit tests for castle.py (Block and Castle).

Run from the project root:  python -m unittest discover tests
Expected values are worked out by hand from the castle template in docs/M0_design.md §4.5.
"""
import unittest

from castle import Block, Castle


# Top-left corners (x, y) of the 15 blocks, derived by hand from the template
# ("....##" x3, "...###", "######"), 32 px blocks, ground at y = 560.
LEFT_BLOCKS = {
    (328, 400), (360, 400),
    (328, 432), (360, 432),
    (328, 464), (360, 464),
    (296, 496), (328, 496), (360, 496),
    (200, 528), (232, 528), (264, 528), (296, 528), (328, 528), (360, 528),
}
# The right castle is the left one mirrored: x' = 1280 - x - 32.
RIGHT_BLOCKS = {
    (920, 400), (888, 400),
    (920, 432), (888, 432),
    (920, 464), (888, 464),
    (952, 496), (920, 496), (888, 496),
    (1048, 528), (1016, 528), (984, 528), (952, 528), (920, 528), (888, 528),
}


def positions(blocks):
    return {(block.x, block.y) for block in blocks}


class BlockTest(unittest.TestCase):
    def test_damage_is_capped_at_remaining_hp(self):
        block = Block(0, 0)
        for _ in range(3):
            block.take_damage(30)          # 100 -> 70 -> 40 -> 10
        dealt = block.take_damage(30)      # only 10 HP were left
        self.assertEqual(dealt, 10)
        self.assertEqual(block.hp, 0)
        self.assertTrue(block.is_destroyed())

    def test_contains_uses_the_block_rectangle(self):
        block = Block(100, 200)            # covers x 100..131, y 200..231
        self.assertTrue(block.contains(100, 200))
        self.assertTrue(block.contains(131.9, 231.9))
        self.assertFalse(block.contains(132, 210))
        self.assertFalse(block.contains(110, 199.9))


class CastleLayoutTest(unittest.TestCase):
    def test_new_castle_has_15_full_blocks(self):
        castle = Castle("left")
        self.assertEqual(len(castle.blocks), 15)
        self.assertTrue(all(block.hp == 100 for block in castle.blocks))
        self.assertEqual(castle.total_hp(), 1500)
        self.assertEqual(castle.destruction_percent(), 0.0)
        self.assertFalse(castle.has_fallen())

    def test_left_castle_matches_template(self):
        self.assertEqual(positions(Castle("left").blocks), LEFT_BLOCKS)

    def test_right_castle_is_the_mirror_image(self):
        self.assertEqual(positions(Castle("right").blocks), RIGHT_BLOCKS)


class BlastTest(unittest.TestCase):
    def test_blast_damages_only_blocks_whose_centre_is_within_radius(self):
        castle = Castle("right")
        # Impact on the front face, bottom row. Centre distances (by hand):
        # (904,544) 16 px, (936,544) 48 px, (904,512) 35.8 px -> hit;
        # (968,544) 80 px, (936,512) 57.7 px, (904,480) 66 px -> not hit.
        blocks_hit, damage = castle.apply_blast(888, 544, radius=50, damage=30)
        self.assertEqual(blocks_hit, 3)
        self.assertEqual(damage, 90)
        damaged = {(b.x, b.y) for b in castle.blocks if b.hp < 100}
        self.assertEqual(damaged, {(888, 528), (920, 528), (888, 496)})
        self.assertAlmostEqual(castle.destruction_percent(), 6.0)

    def test_blast_radius_boundary_is_inclusive(self):
        castle = Castle("left")
        # Block (200,528) has centre (216,544). (186,584) is exactly 50 px away (30-40-50).
        self.assertEqual(castle.apply_blast(186, 584, radius=50, damage=30), (1, 30))
        # One pixel further left is 50.6 px away: nothing is hit.
        self.assertEqual(castle.apply_blast(185, 584, radius=50, damage=30), (0, 0))

    def test_destroyed_block_stops_blocking_and_takes_no_more_damage(self):
        castle = Castle("right")
        target = castle.block_at(904, 544)          # front-bottom block (888,528)
        self.assertIsNotNone(target)
        target.take_damage(100)
        self.assertIsNone(castle.block_at(904, 544))
        self.assertEqual(len(castle.alive_blocks()), 14)
        # Same blast as above: only the two surviving blocks in range are hit.
        self.assertEqual(castle.apply_blast(888, 544, radius=50, damage=30), (2, 60))


class DestructionTest(unittest.TestCase):
    def test_castle_falls_at_exactly_60_percent(self):
        castle = Castle("left")
        blocks = castle.blocks
        for block in blocks[:8]:
            block.take_damage(100)                  # 800 damage
        blocks[8].take_damage(99)                   # 899 damage = 59.93 %
        self.assertAlmostEqual(castle.destruction_percent(), 59.9333, places=3)
        self.assertFalse(castle.has_fallen())
        blocks[8].take_damage(1)                    # 900 damage = 60 %
        self.assertEqual(castle.destruction_percent(), 60.0)
        self.assertTrue(castle.has_fallen())


if __name__ == "__main__":
    unittest.main()
