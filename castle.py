"""Castle blocks and castles for Castle Siege.

This module uses only the Python standard library, so it can be tested without
opening a Pygame window. Screen coordinates are used throughout: x grows to the
right and y grows DOWN, so a smaller y means higher on the screen.
"""
import math

GROUND_Y = 560          # y of the ground surface
BLOCK_SIZE = 32         # blocks are 32 x 32 pixel squares
BLOCK_HP = 100          # health of a brand-new block
LOSS_PERCENT = 60       # a castle with at least this much destruction has fallen

# x of the left edge of each castle. The castles are mirror images around x = 640.
CASTLE_X = {"left": 200, "right": 888}

# The left castle, top row first. '#' is a block, '.' is empty space.
# The tall tower on the right faces the enemy. The right castle uses each row
# reversed, so its tower faces left.
TEMPLATE = [
    "....##",
    "....##",
    "....##",
    "...###",
    "######",
]


class Block:
    """One square piece of a castle wall that can be damaged and destroyed."""

    def __init__(self, x, y, size=BLOCK_SIZE, max_hp=BLOCK_HP):
        self.x = x              # top-left corner
        self.y = y
        self.size = size
        self.max_hp = max_hp
        self._hp = max_hp       # private: only changed through take_damage()

    @property
    def hp(self):
        """Current health (read-only from outside the class)."""
        return self._hp

    def is_destroyed(self):
        return self._hp <= 0

    def center(self):
        return (self.x + self.size / 2, self.y + self.size / 2)

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
    """A castle made of blocks, built from TEMPLATE for the "left" or "right" side."""

    def __init__(self, side):
        self.side = side
        self._blocks = self._build_blocks()
        self.max_hp = sum(block.max_hp for block in self._blocks)

    def _build_blocks(self):
        blocks = []
        row_count = len(TEMPLATE)
        for row_index, row in enumerate(TEMPLATE):
            if self.side == "right":
                row = row[::-1]                 # mirror the row
            # The bottom row sits on the ground, the row above it 32 px higher, etc.
            y = GROUND_Y - (row_count - row_index) * BLOCK_SIZE
            for column_index, cell in enumerate(row):
                if cell == "#":
                    x = CASTLE_X[self.side] + column_index * BLOCK_SIZE
                    blocks.append(Block(x, y))
        return blocks

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

        The most damaged block (lowest HP) is repaired first; for equal HP the
        leftmost, then the highest block goes first. HP that no block needs is lost.
        """
        restored = 0
        for block in sorted(self.alive_blocks(), key=lambda b: (b.hp, b.x, b.y)):
            if pool <= 0:
                break
            gained = block.restore(pool)
            pool -= gained
            restored += gained
        return restored

    def total_hp(self):
        return sum(block.hp for block in self._blocks)

    def destruction_percent(self):
        """How much of the castle's total HP has been lost, from 0.0 to 100.0."""
        return 100 * (self.max_hp - self.total_hp()) / self.max_hp

    def has_fallen(self):
        """True once destruction reaches LOSS_PERCENT.

        Compared with whole numbers (lost * 100 >= 60 * max) so that exactly 60 %
        can't be missed because of floating-point rounding.
        """
        lost = self.max_hp - self.total_hp()
        return lost * 100 >= LOSS_PERCENT * self.max_hp

    def hp_before_falling(self):
        """How much more HP must be lost for the castle to fall (0 once it has fallen).

        900 for a new castle (60 % of 1500). The AI uses it to judge how close a castle is to falling.
        """
        hp_lost_when_fallen = (LOSS_PERCENT * self.max_hp + 99) // 100    # rounded up, whole HP
        lost = self.max_hp - self.total_hp()
        return max(0, hp_lost_when_fallen - lost)
