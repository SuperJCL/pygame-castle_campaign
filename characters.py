"""Characters for Castle Siege: the Character base class and the Knight, Archer
and Engineer subclasses (M2.1).

The base class holds every rule the three roles share: health, damage, defending,
the special-ability cooldown, EXP and levels. Each subclass only sets its own
starting numbers and its own special ability. This module uses only the Python
standard library (no Pygame), so it can be tested without a window.
"""

MAX_LEVEL = 5
EXP_PER_LEVEL = 30          # EXP needed for the next level = 30 x current level
LEVEL_UP_HP = 10            # each level-up: +10 max HP and +10 HP
LEVEL_UP_ATK = 3            #                +3 ATK
LEVEL_UP_DEF = 1            #                +1 DEF


def calculate_damage(attack, defense, defending):
    """Damage one hit does to a character.

        damage = attack - defense, but at least 1
        if the target is defending: damage = damage // 2, but still at least 1

    The minimum of 1 means a hit that connects always hurts a little, even when
    DEF is higher than ATK. Halving uses whole numbers and rounds down (21 -> 10).
    """
    damage = max(1, attack - defense)
    if defending:
        damage = max(1, damage // 2)
    return damage


class Character:
    """A fighter with HP, ATK, DEF, EXP and a level.

    Create a Knight, Archer or Engineer rather than a plain Character: the
    subclasses supply the starting numbers and the special ability.
    """

    # Set by each subclass.
    BASE_HP = None
    BASE_ATK = None
    BASE_DEF = None
    SPECIAL_NAME = None
    SPECIAL_COOLDOWN = 0        # rounds to wait after using the special

    def __init__(self, name, side):
        self.name = name
        self.side = side                       # "left" or "right"
        # Private values (leading underscore). Other code reads them through the
        # read-only properties below and changes them only through methods, so
        # they can't be set to impossible values such as negative HP.
        self._max_hp = self.BASE_HP
        self._hp = self.BASE_HP
        self._atk = self.BASE_ATK
        self._defense = self.BASE_DEF          # "def" is a Python keyword, so: defense
        self._level = 1
        self._exp = 0
        self._is_defending = False
        self._special_cooldown = 0             # 0 means the special is ready

    # ----- read-only properties ------------------------------------------------

    @property
    def hp(self):
        return self._hp

    @property
    def max_hp(self):
        return self._max_hp

    @property
    def atk(self):
        return self._atk

    @property
    def defense(self):
        return self._defense

    @property
    def level(self):
        return self._level

    @property
    def exp(self):
        return self._exp

    @property
    def is_defending(self):
        return self._is_defending

    @property
    def special_cooldown(self):
        """Rounds left until the special can be used again (0 = ready)."""
        return self._special_cooldown

    # ----- health and damage ---------------------------------------------------

    def is_alive(self):
        return self._hp > 0

    def take_damage(self, amount):
        """Lose `amount` HP, never going below 0. Returns the HP actually lost."""
        if amount < 0:
            raise ValueError("damage cannot be negative")
        lost = min(amount, self._hp)
        self._hp -= lost
        return lost

    def take_hit(self, attacker):
        """Be hit by `attacker`: work out the damage with calculate_damage(), then take it."""
        damage = calculate_damage(attacker.atk, self._defense, self._is_defending)
        return self.take_damage(damage)

    # ----- defending -----------------------------------------------------------

    def defend(self):
        self._is_defending = True

    def clear_defend(self):
        self._is_defending = False

    # ----- special ability cooldown ----------------------------------------------

    def special_ready(self):
        return self._special_cooldown == 0

    def start_cooldown(self):
        """Call when the special is used. It can be used again after SPECIAL_COOLDOWN round starts."""
        self._special_cooldown = self.SPECIAL_COOLDOWN

    def tick_cooldown(self):
        """Call once at the start of every round: one round less to wait (never below 0)."""
        self._special_cooldown = max(0, self._special_cooldown - 1)

    def use_special(self):
        """Use this character's special ability. Every subclass replaces this method.

        In M2.1 it only describes the ability; its effect on the battle comes in M2.2.
        """
        raise NotImplementedError(f"{type(self).__name__} has no special ability")

    # ----- EXP and levels ----------------------------------------------------------

    def exp_to_next_level(self):
        """EXP needed to go from the current level to the next: 30, 60, 90, 120."""
        return EXP_PER_LEVEL * self._level

    def gain_exp(self, amount):
        """Add EXP and level up as many times as it allows. Returns the number of levels gained.

        A defeated character gains nothing (and so is never revived by a level-up),
        and a character at MAX_LEVEL has nothing left to earn.
        """
        if amount < 0:
            raise ValueError("EXP cannot be negative")
        if not self.is_alive() or self._level == MAX_LEVEL:
            return 0
        self._exp += amount
        levels_gained = 0
        # One big award can be enough for several levels, so keep checking.
        # Leftover EXP carries over to the next level.
        while self._level < MAX_LEVEL and self._exp >= self.exp_to_next_level():
            self._exp -= self.exp_to_next_level()
            self._level_up()
            levels_gained += 1
        if self._level == MAX_LEVEL:
            self._exp = 0                      # nothing more to earn at the top level
        return levels_gained

    def _level_up(self):
        """Private: only gain_exp() calls this, so EXP is the only way to level up."""
        self._level += 1
        self._max_hp += LEVEL_UP_HP
        self._hp += LEVEL_UP_HP                # heals by the same amount, so HP stays <= max HP
        self._atk += LEVEL_UP_ATK
        self._defense += LEVEL_UP_DEF


class Knight(Character):
    """Defensive role: lots of HP and DEF."""
    BASE_HP = 140
    BASE_ATK = 30
    BASE_DEF = 12
    SPECIAL_NAME = "Rally"
    SPECIAL_COOLDOWN = 4

    def use_special(self):
        return f"{self.name} uses Rally: every living ally defends until the team's next turn."


class Archer(Character):
    """Offensive role: the highest ATK, but little HP and DEF."""
    BASE_HP = 90
    BASE_ATK = 40
    BASE_DEF = 4
    SPECIAL_NAME = "Power Shot"
    SPECIAL_COOLDOWN = 3

    def use_special(self):
        return f"{self.name} uses Power Shot: an aimed shot with 1.5x damage that ignores DEF."


class Engineer(Character):
    """Support role: balanced stats, can repair the castle."""
    BASE_HP = 110
    BASE_ATK = 34
    BASE_DEF = 8
    SPECIAL_NAME = "Repair"
    SPECIAL_COOLDOWN = 4

    def use_special(self):
        return f"{self.name} uses Repair: the castle regains up to 75 HP."
