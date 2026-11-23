"""Characters for Castle Siege: the Character base class and its six roles, Knight, Archer,
Engineer and (M6.3) Gunner, Bombardier and Medic.

The base class holds every rule the roles share: health, damage, healing, defending,
the special-ability cooldown, EXP and levels. Each subclass only sets its own
numbers and its own special ability. Characters never manage the whole battle:
battle.py decides whose turn it is and fires the cannon. This module uses only
the Python standard library (no Pygame), so it can be tested without a window.
"""

MAX_LEVEL = 5
EXP_PER_LEVEL = 30          # EXP needed for the next level = 30 x current level
LEVEL_UP_HP = 10            # each level-up: +10 max HP and +10 HP
LEVEL_UP_ATK = 3            #                +3 ATK
LEVEL_UP_DEF = 1            #                +1 DEF
# Guarded Strike (M4.2-B): a basic Defend makes the defender's normal Attack in its team's next
# turn use ATK x 1.25 (then DEF, as usual). Battle decides when it is granted, ready and dropped.
GUARDED_STRIKE_MULTIPLIER = 1.25


def calculate_damage(attack, defense, defending, multiplier=1.0, ignores_def=False):
    """Damage one hit does to a character.

        damage = attack x multiplier (rounded down), minus defense unless ignores_def
        damage = at least 1
        if the target is defending: damage = damage // 2, but still at least 1

    A normal Attack uses multiplier 1.0, so it is simply ATK - DEF. Archer's Power
    Shot uses multiplier 1.5 and ignores DEF. The minimum of 1 means a hit that
    connects always hurts a little. Halving rounds down (21 -> 10).

    The instructor's reference formula is ATK - DEF + a random number from -5 to 10.
    We leave out the random part on purpose: the same hit always does the same
    damage, so it can be tested with exact numbers. (On average the reference
    formula does 2.5 more damage per hit.)
    """
    damage = int(attack * multiplier)
    if not ignores_def:
        damage -= defense
    damage = max(1, damage)
    if defending:
        damage = max(1, damage // 2)
    return damage


class ShotDamage:
    """How hard one cannon shot hits: damage to each cover block in the blast, and
    how its damage to characters is worked out (see calculate_damage).

    M6.3 adds how many shells one shot is (every shell hits this hard):
      blast_radius  the blast of each shell in px; None = the normal blast (battle.BLAST_RADIUS)
      spread        one (angle change, power change) per shell fired at once, from the
                    cannon's aim; a normal shot is the one shell ((0, 0),)
      split         None, or the horizontal speed factors of the small shells each shell
                    splits into when it starts to come down (Airburst)
    """

    def __init__(self, block_damage, multiplier=1.0, ignores_def=False, blast_radius=None,
                 spread=((0, 0),), split=None):
        self.block_damage = block_damage
        self.multiplier = multiplier
        self.ignores_def = ignores_def
        self.blast_radius = blast_radius
        self.spread = spread
        self.split = split


class Character:
    """A fighter with HP, ATK, DEF, EXP and a level.

    Create a Knight, Archer or Engineer rather than a plain Character: the
    subclasses supply the starting numbers and the special ability.
    """

    # Set by each subclass.
    BASE_HP = None
    BASE_ATK = None
    BASE_DEF = None
    BLOCK_DAMAGE = None         # damage to each cover block hit by this character's Attack
    SPECIAL_NAME = None
    SPECIAL_COOLDOWN = 0        # rounds to wait after using the special
    SPECIAL_SHELLS = 0          # M6.3: shells the special fires (0 = it fires nothing: it happens at once)

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
        # Guarded Strike (M4.2-B): None, "pending" (it defended this turn) or "ready" (its
        # team's turn after the Defend: this turn's Attack is stronger).
        self._guarded_strike = None

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

    def take_hit(self, attacker, multiplier=1.0, ignores_def=False):
        """Be hit by `attacker`: work out the damage with calculate_damage(), then take it.

        The attacker's current ATK is used, so a level-up makes later hits stronger.
        """
        damage = calculate_damage(attacker.atk, self._defense, self._is_defending,
                                  multiplier, ignores_def)
        return self.take_damage(damage)

    def heal(self, amount):
        """Regain up to `amount` HP, never above max HP (M6.3, Field Dressing). Returns the HP
        actually regained. A defeated character regains nothing: healing never revives."""
        if amount < 0:
            raise ValueError("healing cannot be negative")
        if not self.is_alive():
            return 0
        gained = min(amount, self._max_hp - self._hp)
        self._hp += gained
        return gained

    def attack_shot(self):
        """The cannon shot this character fires with a normal Attack: ATK x 1.25 while its
        Guarded Strike is ready (M4.2-B). Block damage never changes."""
        if self.guarded_strike_ready:
            return ShotDamage(self.BLOCK_DAMAGE, GUARDED_STRIKE_MULTIPLIER)
        return ShotDamage(self.BLOCK_DAMAGE)

    # ----- Guarded Strike (M4.2-B) -----------------------------------------------------

    @property
    def guarded_strike_pending(self):
        """True from its Defend until its team's next turn starts."""
        return self._guarded_strike == "pending"

    @property
    def guarded_strike_ready(self):
        """True during its team's next turn after the Defend: its Attack is stronger."""
        return self._guarded_strike == "ready"

    def grant_guarded_strike(self):
        """A basic Defend: the bonus waits for the team's next turn. Never more than one."""
        self._guarded_strike = "pending"

    def arm_guarded_strike(self):
        """The team's next turn starts: a waiting bonus can be used now."""
        if self._guarded_strike == "pending":
            self._guarded_strike = "ready"

    def use_guarded_strike(self):
        """Its stronger Attack has been fired: the bonus is used up."""
        self._guarded_strike = None

    def expire_guarded_strike(self):
        """The end of a turn: a ready bonus that wasn't used is dropped (returns True then).
        One granted this turn waits for the next."""
        if self._guarded_strike == "ready":
            self._guarded_strike = None
            return True
        return False

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

    def special_blocked_reason(self, team):
        """None if the special may be used now, otherwise a short reason why not.

        Here only the cooldown matters; a subclass can add its own conditions.
        """
        if self._special_cooldown > 0:
            rounds = self._special_cooldown
            plural = "s" if rounds != 1 else ""
            return f"{self.SPECIAL_NAME} is recharging: ready in {rounds} round{plural}"
        return None

    def can_use_special(self, team):
        """True if the special may be used now."""
        return self.special_blocked_reason(team) is None

    def use_special(self, team):
        """Use this character's special ability for `team`. Every subclass replaces this.

        Returns (message, shot): a sentence for the combat log, and a ShotDamage if
        the battle should fire the cannon for this special (None if nothing is fired).
        The battle checks can_use_special() first and starts the cooldown.
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
    BLOCK_DAMAGE = 50
    SPECIAL_NAME = "Rally"
    SPECIAL_COOLDOWN = 4
    SPECIAL_DESCRIPTION = "All living allies defend until your next turn."

    def use_special(self, team):
        """Rally: every living ally, the Knight included, defends. Nothing is fired."""
        allies = team.alive_characters()
        for ally in allies:
            ally.defend()
        return f"{self.name} uses Rally: {len(allies)} allies are defending.", None


class Archer(Character):
    """Offensive role: the highest ATK, but little HP and DEF."""
    BASE_HP = 90
    BASE_ATK = 40
    BASE_DEF = 4
    BLOCK_DAMAGE = 50
    SPECIAL_NAME = "Power Shot"
    SPECIAL_COOLDOWN = 3
    SPECIAL_SHELLS = 1
    SPECIAL_DESCRIPTION = "Aimed shot: 1.5x ATK, ignores DEF, 75 per block."
    POWER_SHOT_MULTIPLIER = 1.5          # character damage = ATK x 1.5, ignoring DEF
    POWER_SHOT_BLOCK_DAMAGE = 75

    def use_special(self, team):
        """Power Shot: an aimed cannon shot that hits harder. The battle fires it."""
        shot = ShotDamage(self.POWER_SHOT_BLOCK_DAMAGE, self.POWER_SHOT_MULTIPLIER, ignores_def=True)
        return f"{self.name} uses Power Shot!", shot


class Engineer(Character):
    """Support role: balanced stats, can repair the team's cover blocks."""
    BASE_HP = 110
    BASE_ATK = 34
    BASE_DEF = 8
    BLOCK_DAMAGE = 60
    SPECIAL_NAME = "Repair"
    SPECIAL_COOLDOWN = 4
    SPECIAL_DESCRIPTION = "Restores up to 150 HP to damaged cover blocks, most damaged first."
    REPAIR_POOL = 150                    # block HP restored by one Repair, at most
                                         # (75 until M3.2, see docs/M3.2_balance_report.md)

    def special_blocked_reason(self, team):
        """Repair also needs something to repair (a damaged block that still stands)."""
        reason = super().special_blocked_reason(team)
        if reason is None and not team.castle.is_damaged():
            reason = "Repair: nothing to repair (no standing cover block is damaged)"
        return reason

    def use_special(self, team):
        """Repair: up to REPAIR_POOL HP back for the team's damaged blocks (destroyed blocks
        stay destroyed). Nothing is fired."""
        restored = team.castle.repair(self.REPAIR_POOL)
        return f"{self.name} uses Repair: the cover regains {restored} HP.", None


# ----- M6.3: three more roles (docs/M6.3_six_role_design.md, first-round numbers) ---------------

class Gunner(Character):
    """Offensive role: Triple Volley fires three lighter shells at once in a fixed fan, a wider
    chance to hit for less damage per shell."""
    BASE_HP = 115
    BASE_ATK = 35
    BASE_DEF = 7
    BLOCK_DAMAGE = 50
    SPECIAL_NAME = "Triple Volley"
    SPECIAL_COOLDOWN = 3
    SPECIAL_SHELLS = 3
    SPECIAL_DESCRIPTION = "Three shells in a fixed fan: 0.6x ATK, 18 per block each."
    VOLLEY_SPREAD = ((-6, -4), (0, 0), (6, 4))   # (angle, power) change of each shell from the aim
    VOLLEY_MULTIPLIER = 0.60
    VOLLEY_BLOCK_DAMAGE = 18
    VOLLEY_BLAST_RADIUS = 32

    def use_special(self, team):
        """Triple Volley: one shot of three shells, each hitting like a light Attack. The battle fires it."""
        shot = ShotDamage(self.VOLLEY_BLOCK_DAMAGE, self.VOLLEY_MULTIPLIER,
                          blast_radius=self.VOLLEY_BLAST_RADIUS, spread=self.VOLLEY_SPREAD)
        return f"{self.name} uses Triple Volley!", shot


class Bombardier(Character):
    """Offensive role: Airburst fires one marked shell that splits into five small ones at the top
    of its arc, so it can pass over a wall and then spread over the enemy."""
    BASE_HP = 100
    BASE_ATK = 32
    BASE_DEF = 6
    BLOCK_DAMAGE = 50
    SPECIAL_NAME = "Airburst"
    SPECIAL_COOLDOWN = 4
    SPECIAL_SHELLS = 5
    SPECIAL_DESCRIPTION = "Splits into 5 shells at the top: 0.45x ATK, 16 per block each."
    AIRBURST_SPLIT = (0.76, 0.88, 1.00, 1.12, 1.24)   # horizontal speed factor of each small shell
    AIRBURST_MULTIPLIER = 0.45
    AIRBURST_BLOCK_DAMAGE = 16
    AIRBURST_BLAST_RADIUS = 24

    def use_special(self, team):
        """Airburst: one shell that splits; it and each small shell hit like a small shell."""
        shot = ShotDamage(self.AIRBURST_BLOCK_DAMAGE, self.AIRBURST_MULTIPLIER,
                          blast_radius=self.AIRBURST_BLAST_RADIUS, split=self.AIRBURST_SPLIT)
        return f"{self.name} uses Airburst!", shot


class Medic(Character):
    """Support role: Field Dressing heals the living teammate who gains the most HP. The Engineer
    saves the cover; the Medic saves the people."""
    BASE_HP = 105
    BASE_ATK = 28
    BASE_DEF = 6
    BLOCK_DAMAGE = 45
    SPECIAL_NAME = "Field Dressing"
    SPECIAL_COOLDOWN = 4
    SPECIAL_DESCRIPTION = "Heals the ally who gains most: up to 32 HP (24 on itself)."
    ALLY_HEAL = 32                       # HP another living teammate regains, at most
    SELF_HEAL = 24                       # HP the Medic regains when it treats itself, at most

    def heal_amount(self, character):
        """HP `character` would really regain from Field Dressing now (0 if full or defeated)."""
        if not character.is_alive():
            return 0
        limit = self.SELF_HEAL if character is self else self.ALLY_HEAL
        return min(limit, character.max_hp - character.hp)

    def heal_target(self, team):
        """(character, HP it would regain) for the living teammate who would regain the most,
        or None if nobody would regain anything. On a tie another teammate goes before the Medic
        itself, then the earlier slot. The preview (main.py) and the heal use this same choice."""
        best, best_amount = None, 0
        for character in team.characters:              # slot order: on a tie the first one stays ...
            amount = self.heal_amount(character)
            if amount > best_amount or (amount == best_amount and amount > 0 and best is self):
                best, best_amount = character, amount   # ... unless the one kept is the Medic itself
        return None if best is None else (best, best_amount)

    def special_blocked_reason(self, team):
        """Field Dressing also needs someone to heal (a living teammate below full HP)."""
        reason = super().special_blocked_reason(team)
        if reason is None and self.heal_target(team) is None:
            reason = "Field Dressing: nothing to heal (every living ally is at full HP)"
        return reason

    def use_special(self, team):
        """Field Dressing: heal heal_target() by its amount. Nothing is fired. (The battle never
        calls it with nobody to heal, but like Repair it then simply does nothing.)"""
        choice = self.heal_target(team)
        if choice is None:
            return f"{self.name} uses Field Dressing: nobody needs it.", None
        target, amount = choice
        gained = target.heal(amount)
        return f"{self.name} uses Field Dressing: {target.name} +{gained} HP.", None


# The six roles, in the order the team-selection screen shows them.
ARCHETYPES = [Knight, Archer, Engineer, Gunner, Bombardier, Medic]
