"""Cover blocks for Castle Siege: Block, the cover slots and Castle.

Each team builds its own cover (its "castle") before the battle: up to MAX_BLOCKS
blocks on the SLOT_COUNT fixed slots in front of its characters. Enemy shots hit
the blocks, and a standing block between an explosion and a character shields
that character (battle.py applies that rule). Blocks never decide who wins:
only defeating every enemy character does.

This module uses only the Python standard library, so it can be tested without
opening a Pygame window. Screen coordinates are used throughout: x grows to the
right and y grows DOWN, so a smaller y means higher on the screen.
"""
import math

GROUND_Y = 560          # y of the ground surface
BLOCK_SIZE = 32         # blocks are 32 x 32 pixel squares
BLOCK_HP = 100          # health of a brand-new block
MAX_BLOCKS = 6          # a team may place up to 6 blocks ...
SLOT_COUNT = 8          # ... on its 8 cover slots

# The slots form 4 columns and 2 rows between a team's characters and its cannon.
# x of the left edge of each column, the column next to the team's characters first.
# The right side is the mirror image of the left (x' = 1280 - x - 32).
COLUMN_X = {"left": (172, 204, 236, 268), "right": (1076, 1044, 1012, 980)}
# Slots 0-3 are the bottom row, on the ground (slot 0 next to the characters).
# Slots 4-7 are the raised row: slot 4 sits on top of slot 0, slot 5 on slot 1, ...
RAISED = 4
# Used until the placement screen exists (M3.4-B), and for quick tests: the whole
# bottom row plus two raised blocks next to the characters.
DEFAULT_LAYOUT = (0, 1, 2, 3, 4, 5)


def slot_position(side, slot):
    """Top-left corner (x, y) of cover slot `slot` (0-7) on `side`."""
    column, row = slot % RAISED, slot // RAISED
    return COLUMN_X[side][column], GROUND_Y - (row + 1) * BLOCK_SIZE


def layout_problem(layout):
    """None if `layout` (the slot numbers that get a block) is legal, otherwise the reason.

    Legal: slots 0 to 7, each used once, at most MAX_BLOCKS blocks, and a raised
    block only on top of a block (no block floats in the air when the battle starts).
    """
    slots = list(layout)
    if any(type(slot) is not int or not 0 <= slot < SLOT_COUNT for slot in slots):
        return f"cover slots are numbered 0 to {SLOT_COUNT - 1}"
    if len(set(slots)) != len(slots):
        return "a slot can hold only one block"
    if len(slots) > MAX_BLOCKS:
        return f"a team can place at most {MAX_BLOCKS} blocks"
    if any(slot >= RAISED and slot - RAISED not in slots for slot in slots):
        return "a raised block needs a block under it"
    return None


class Block:
    """One square cover block that can be damaged and destroyed."""

    def __init__(self, x, y, size=BLOCK_SIZE, max_hp=BLOCK_HP):
        self.x = x              # top-left corner
        self.y = y
        self.size = size
        self.max_hp = max_hp
        self._hp = max_hp       # private: only changed through take_damage() and restore()

    @property
    def hp(self):
        """Current health (read-only from outside the class)."""
        return self._hp

    def is_destroyed(self):
        return self._hp <= 0

    def center(self):
        return (self.x + self.size / 2, self.y + self.size / 2)

    def rect(self):
        """(left, top, width, height) of the block's square."""
        return (self.x, self.y, self.size, self.size)

    def contains(self, px, py):
        """True if the point (px, py) is inside this block's square."""
        return (self.x <= px < self.x + self.size
                and self.y <= py < self.y + self.size)

    def take_damage(self, amount):
        """Lose up to `amount` HP (never below 0). Returns the damage actually dealt."""
        dealt = min(amount, self._hp)
        self._hp -= dealt
        return dealt

    def restore(self, amount):
        """Regain up to `amount` HP (never above max_hp). Returns the HP actually regained.

        A destroyed block stays destroyed: repairs can't bring it back.
        """
        if self.is_destroyed():
            return 0
        gained = min(amount, self.max_hp - self._hp)
        self._hp += gained
        return gained


class Castle:
    """One team's cover: a full block on each slot of its layout.

    layout: the slot numbers (0-7) that get a block, e.g. (0, 1, 4); see layout_problem().
    The blocks are kept in slot order. A rematch builds a new Castle from the same
    layout, so every block starts at full HP again.
    """

    def __init__(self, side, layout=DEFAULT_LAYOUT):
        problem = layout_problem(layout)
        if problem is not None:
            raise ValueError(problem)
        self.side = side
        self.layout = tuple(sorted(layout))
        self._blocks = [Block(*slot_position(side, slot)) for slot in self.layout]
        self.max_hp = sum(block.max_hp for block in self._blocks)

    @property
    def blocks(self):
        """All blocks, including destroyed ones (a tuple, so callers can't add or remove blocks)."""
        return tuple(self._blocks)

    def alive_blocks(self):
        return [block for block in self._blocks if not block.is_destroyed()]

    def block_at(self, px, py):
        """The surviving block that contains point (px, py), or None.

        Destroyed blocks are ignored, so shots fly straight through the gaps they leave.
        """
        for block in self.alive_blocks():
            if block.contains(px, py):
                return block
        return None

    def apply_blast(self, px, py, radius, damage):
        """Damage every surviving block whose centre is within `radius` of (px, py).

        Returns (number of blocks hit, total damage dealt).
        """
        blocks_hit = 0
        total_damage = 0
        for block in self.alive_blocks():
            center_x, center_y = block.center()
            if math.hypot(center_x - px, center_y - py) <= radius:
                blocks_hit += 1
                total_damage += block.take_damage(damage)
        return blocks_hit, total_damage

    def is_damaged(self):
        """True if some surviving block has lost HP, so a repair would do something."""
        return any(block.hp < block.max_hp for block in self.alive_blocks())

    def repair(self, pool):
        """Share out up to `pool` HP among damaged surviving blocks. Returns the HP restored.

        The most damaged block (lowest HP) is repaired first; for equal HP the lower
        slot number goes first (sorted() keeps the slot order for ties), so the two
        sides are repaired alike. HP that no block needs is lost.
        """
        restored = 0
        for block in sorted(self.alive_blocks(), key=lambda b: b.hp):
            if pool <= 0:
                break
            gained = block.restore(pool)
            pool -= gained
            restored += gained
        return restored

    def total_hp(self):
        return sum(block.hp for block in self._blocks)
