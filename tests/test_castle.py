"""Unit tests for castle.py (Block, cover layouts and Castle).

Run from the project root:  python -m unittest discover tests
Expected values are worked out by hand from the slot positions in docs/M0_design.md
(M3.4-A): 32 px blocks, ground at y = 560, left columns at x 172, 204, 236 and 268.
"""
import itertools
import unittest

from castle import (BLOCK_HP, DEFAULT_LAYOUT, MAX_BLOCKS, SLOT_COUNT, Block, Castle,
                    layout_problem, place_block, remove_block, slot_position)

# Top-left corners (x, y) of the 8 cover slots, by hand. Slots 0-3 are the bottom row
# (slot 0 nearest the team's characters); slots 4-7 sit on top of slots 0-3.
LEFT_SLOTS = [(172, 528), (204, 528), (236, 528), (268, 528),
              (172, 496), (204, 496), (236, 496), (268, 496)]
# The right side is the mirror image: x' = 1280 - x - 32.
RIGHT_SLOTS = [(1076, 528), (1044, 528), (1012, 528), (980, 528),
               (1076, 496), (1044, 496), (1012, 496), (980, 496)]


def positions(blocks):
    return [(block.x, block.y) for block in blocks]


class BlockTest(unittest.TestCase):
    def test_damage_is_capped_at_remaining_hp(self):
        block = Block(0, 0)
        for _ in range(3):
            block.take_damage(30)          # 100 -> 70 -> 40 -> 10
        dealt = block.take_damage(30)      # only 10 HP were left
        self.assertEqual(dealt, 10)
        self.assertEqual(block.hp, 0)
        self.assertTrue(block.is_destroyed())

    def test_restore_heals_up_to_max_hp_but_never_a_destroyed_block(self):
        block = Block(0, 0)
        block.take_damage(30)
        self.assertEqual(block.restore(150), 30)       # only 30 HP were missing
        self.assertEqual(block.hp, 100)
        block.take_damage(100)
        self.assertEqual(block.restore(150), 0)        # destroyed blocks stay destroyed
        self.assertTrue(block.is_destroyed())

    def test_contains_uses_the_block_rectangle(self):
        block = Block(100, 200)            # covers x 100..131, y 200..231
        self.assertTrue(block.contains(100, 200))
        self.assertTrue(block.contains(131.9, 231.9))
        self.assertFalse(block.contains(132, 210))
        self.assertFalse(block.contains(110, 199.9))

    def test_rect_is_the_32_px_square(self):
        self.assertEqual(Block(100, 200).rect(), (100, 200, 32, 32))


class LayoutTest(unittest.TestCase):
    def test_each_side_has_8_slots_in_two_rows(self):
        self.assertEqual(SLOT_COUNT, 8)
        self.assertEqual([slot_position("left", s) for s in range(8)], LEFT_SLOTS)

    def test_the_right_slots_mirror_the_left_slots(self):
        self.assertEqual([slot_position("right", s) for s in range(8)], RIGHT_SLOTS)

    def test_a_castle_has_one_full_block_on_each_chosen_slot(self):
        castle = Castle("right", (4, 0, 1))
        self.assertEqual(castle.layout, (0, 1, 4))                 # kept in slot order
        self.assertEqual(positions(castle.blocks), [RIGHT_SLOTS[0], RIGHT_SLOTS[1], RIGHT_SLOTS[4]])
        self.assertTrue(all(block.hp == BLOCK_HP for block in castle.blocks))
        self.assertEqual((castle.max_hp, castle.total_hp()), (300, 300))

    def test_the_default_layout_is_legal_and_uses_the_whole_budget(self):
        self.assertEqual(MAX_BLOCKS, 6)
        self.assertEqual(len(DEFAULT_LAYOUT), MAX_BLOCKS)
        self.assertIsNone(layout_problem(DEFAULT_LAYOUT))
        self.assertEqual(positions(Castle("left").blocks), [LEFT_SLOTS[s] for s in DEFAULT_LAYOUT])

    def test_a_team_may_place_no_blocks_at_all(self):
        castle = Castle("left", ())
        self.assertEqual(castle.blocks, ())
        self.assertEqual((castle.max_hp, castle.total_hp()), (0, 0))
        self.assertFalse(castle.is_damaged())
        self.assertEqual(castle.apply_blast(200, 540, radius=50, damage=50), (0, 0))

    def test_illegal_layouts_are_explained_and_refused(self):
        cases = [((0, 1, 2, 3, 4, 5, 6), "at most 6"),          # over the budget
                 ((0, 0), "only one block"),                   # the same slot twice
                 ((8,), "0 to 7"), ((-1,), "0 to 7"), (("1",), "0 to 7"),
                 ((5,), "needs a block under it"),             # slot 5 would float over slot 1
                 ((0, 1, 6), "needs a block under it")]
        for layout, words in cases:
            with self.subTest(layout=layout):
                self.assertIn(words, layout_problem(layout))
                with self.assertRaises(ValueError):
                    Castle("left", layout)

    def test_there_are_76_legal_layouts(self):
        # By hand: k bottom blocks and j raised blocks on top of them, k + j <= 6:
        # 1 + 4*2 + 6*4 + 4*8 + 1*11 = 76.
        self.assertEqual(len(legal_layouts()), 76)


def legal_layouts():
    """Every legal layout (76 of them), each as a sorted tuple."""
    return [subset for size in range(SLOT_COUNT + 1)
            for subset in itertools.combinations(range(SLOT_COUNT), size)
            if layout_problem(subset) is None]


class PlacementTest(unittest.TestCase):
    """M3.4-B: what one click on a cover slot does on the placement screen."""

    def test_placing_on_an_empty_slot_adds_a_block(self):
        self.assertEqual(place_block((0, 1), 2), ((0, 1, 2), None))
        self.assertEqual(place_block((), 3), ((3,), None))
        self.assertEqual(place_block((1, 0), 4), ((0, 1, 4), None))     # kept in slot order

    def test_a_raised_block_needs_a_block_under_it(self):
        layout, problem = place_block((0,), 5)                         # slot 5 sits on slot 1
        self.assertEqual(layout, (0,))
        self.assertIn("needs a block under it", problem)
        self.assertEqual(place_block((0, 1), 5), ((0, 1, 5), None))

    def test_the_seventh_block_is_refused(self):
        layout, problem = place_block(DEFAULT_LAYOUT, 6)
        self.assertEqual(layout, DEFAULT_LAYOUT)
        self.assertIn(f"at most {MAX_BLOCKS}", problem)

    def test_a_slot_cannot_get_a_second_block(self):
        layout, problem = place_block((0,), 0)
        self.assertEqual(layout, (0,))
        self.assertIn("only one block", problem)

    def test_removing_a_block(self):
        self.assertEqual(remove_block((0, 1, 2), 1), ((0, 2), (1,)))

    def test_removing_a_supporting_block_also_removes_the_block_on_top(self):
        self.assertEqual(remove_block((0, 1, 4, 5), 1), ((0, 4), (1, 5)))
        self.assertEqual(remove_block(DEFAULT_LAYOUT, 0), ((1, 2, 3, 5), (0, 4)))

    def test_removing_a_raised_block_keeps_the_block_under_it(self):
        self.assertEqual(remove_block((0, 4), 4), ((0,), (4,)))

    def test_removing_from_an_empty_slot_changes_nothing(self):
        self.assertEqual(remove_block((0,), 3), ((0,), ()))

    def test_every_click_on_every_legal_layout_leaves_a_legal_layout(self):
        # The placement screen places on an empty slot and removes from an occupied one.
        for layout in legal_layouts():
            for slot in range(SLOT_COUNT):
                if slot in layout:
                    result, removed = remove_block(layout, slot)
                    self.assertIn(slot, removed)
                    self.assertEqual(sorted(result + removed), list(layout))
                else:
                    result, problem = place_block(layout, slot)
                    self.assertEqual(result, layout if problem else tuple(sorted(layout + (slot,))))
                self.assertIsInstance(result, tuple)
                self.assertEqual(list(result), sorted(result))
                self.assertIsNone(layout_problem(result), (layout, slot, result))

    def test_every_legal_layout_can_be_built_by_clicks_and_cleared_to_zero_blocks(self):
        for target in legal_layouts():
            layout = ()
            for slot in target:                     # sorted: supports come first
                layout, problem = place_block(layout, slot)
                self.assertIsNone(problem)
            self.assertEqual(layout, target)
            while layout:
                layout, _ = remove_block(layout, layout[0])
            self.assertEqual(layout, ())
        self.assertIsNone(layout_problem(()))


class BlastTest(unittest.TestCase):
    def test_blast_damages_only_blocks_whose_centre_is_within_radius(self):
        castle = Castle("right")                       # default layout: slots 0-5
        # Centre distances from (1040, 500), by hand: slot 5 (1060,512) 23.3 px,
        # slot 1 (1060,544) 48.3 px, slot 2 (1028,544) 45.6 px -> hit;
        # slot 4 (1092,512) 53.4 px, slot 3 (996,544) 62.2 px, slot 0 (1092,544) 68.1 px -> not hit.
        self.assertEqual(castle.apply_blast(1040, 500, radius=50, damage=30), (3, 90))
        damaged = [(b.x, b.y) for b in castle.blocks if b.hp < 100]
        self.assertEqual(sorted(damaged), sorted([RIGHT_SLOTS[1], RIGHT_SLOTS[2], RIGHT_SLOTS[5]]))

    def test_blast_radius_boundary_is_inclusive(self):
        castle = Castle("left", (0,))                  # one block, centre (188, 544)
        self.assertEqual(castle.apply_blast(158, 584, radius=50, damage=30), (1, 30))   # 30-40-50
        self.assertEqual(castle.apply_blast(157, 584, radius=50, damage=30), (0, 0))    # 50.6 px

    def test_destroyed_block_stops_blocking_and_takes_no_more_damage(self):
        castle = Castle("right")
        target = castle.block_at(1050, 540)            # slot 1 (1044, 528)
        self.assertIsNotNone(target)
        target.take_damage(100)
        self.assertIsNone(castle.block_at(1050, 540))
        self.assertEqual(len(castle.alive_blocks()), 5)
        self.assertEqual(castle.apply_blast(1040, 500, radius=50, damage=30), (2, 60))


class RepairTest(unittest.TestCase):
    def test_repair_heals_the_most_damaged_blocks_first_and_skips_destroyed_ones(self):
        # docs/M0_design.md §3.4 example: HP [100, 40, 70, 0] -> [100, 100, 85, 0].
        castle = Castle("left", (0, 1, 2, 3))
        full, low, mid, gone = castle.blocks
        low.take_damage(60)                     # 40 HP
        mid.take_damage(30)                     # 70 HP
        gone.take_damage(100)                   # destroyed
        self.assertEqual(castle.repair(75), 75)  # 60 to the 40-HP block, 15 to the 70-HP block
        self.assertEqual([b.hp for b in (full, low, mid, gone)], [100, 100, 85, 0])
        self.assertTrue(gone.is_destroyed())
        self.assertEqual(len(castle.alive_blocks()), 3)

    def test_repair_never_goes_above_full_health(self):
        castle = Castle("left", (0, 1))
        a, b = castle.blocks
        a.take_damage(10)                       # 90 HP
        b.take_damage(5)                        # 95 HP
        self.assertEqual(castle.repair(150), 15)  # only 15 HP were missing; the rest is lost
        self.assertEqual((a.hp, b.hp), (100, 100))

    def test_repair_ties_go_to_the_lower_slot_on_both_sides(self):
        # Equal HP: the lower slot number first, so mirrored castles are repaired alike.
        for side in ("left", "right"):
            with self.subTest(side=side):
                castle = Castle(side, (0, 3))
                near, far = castle.blocks       # slot 0 (next to the characters), slot 3
                near.take_damage(50)
                far.take_damage(50)
                castle.repair(30)
                self.assertEqual((near.hp, far.hp), (80, 50))

    def test_only_damaged_surviving_blocks_count_as_repairable(self):
        castle = Castle("left", (0, 1))
        self.assertFalse(castle.is_damaged())
        castle.blocks[0].take_damage(100)       # destroyed blocks can't be repaired
        self.assertFalse(castle.is_damaged())
        castle.blocks[1].take_damage(1)
        self.assertTrue(castle.is_damaged())


if __name__ == "__main__":
    unittest.main()
