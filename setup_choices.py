"""Keep the roster and cover choices made before a Castle Siege match."""
from battle import MAX_TEAM_SIZE
from castle import DEFAULT_LAYOUT, layout_problem, place_block, remove_block


AIM_MODES = (
    "classic",
    "reflex",
)  # M6.1: how a person aims (Reflex Aim is experimental)

# M6.2: two cover layouts to start from. Both are legal, both use 6 blocks, both stay editable.
COVER_PRESETS = {"Inner Wall": (0, 1, 2, 3, 4, 5), "Outer Wall": (0, 1, 2, 3, 6, 7)}
PRESET_NOTES = {
    "Inner Wall": "High wall near the team",
    "Outer Wall": "High wall near the cannon",
}


class TeamSelection:
    """The choices made on the team-selection screen. (No drawing happens here.)

    Each team picks `team_size` different roles. The order of the picks is the
    slot order: the first pick stands at the front, behind the team's cover. Against the
    computer (vs_ai) only the LEFT team is picked here; the AI builds its own.
    """

    def __init__(self):
        self.vs_ai = True  # Player vs AI is the main mode
        self.difficulty = "normal"
        self.team_size = 1
        self.picks = {"left": [], "right": []}
        self.aim_mode = (
            "classic"  # M6.1: "classic" (arrow keys) or "reflex" (the barrel swings)
        )

    def set_mode(self, vs_ai):
        self.vs_ai = vs_ai

    def set_aim_mode(self, aim_mode):
        if aim_mode not in AIM_MODES:
            raise ValueError(
                f"the aim mode must be one of {AIM_MODES}, not {aim_mode!r}"
            )
        self.aim_mode = aim_mode

    def set_team_size(self, size):
        if not 1 <= size <= MAX_TEAM_SIZE:
            raise ValueError(f"team size must be 1 to {MAX_TEAM_SIZE}")
        self.team_size = size
        for picks in self.picks.values():
            del picks[size:]  # a smaller team keeps its first picks

    def toggle(self, side, role):
        """Add `role` to the team, or remove it if it is already there.

        Returns None, or a message if the pick is refused (the team is full, or it
        is the computer's team). A role can't be picked twice, so there are never duplicates.
        """
        if side == "right" and self.vs_ai:
            return "The computer picks the RIGHT team when the battle starts."
        picks = self.picks[side]
        if role in picks:
            picks.remove(role)
            return None
        if len(picks) >= self.team_size:
            return (
                f"{side.upper()} team already has {self.team_size} - "
                f"click a chosen character to remove it first."
            )
        picks.append(role)
        return None

    def is_complete(self):
        """True when every team picked here has exactly team_size characters."""
        sides = ["left"] if self.vs_ai else ["left", "right"]
        return all(len(self.picks[side]) == self.team_size for side in sides)

    def roster(self):
        """The picks in the form Battle(roster=...) expects."""
        return {side: list(picks) for side, picks in self.picks.items()}


class CoverSetup:
    """The cover layouts chosen on the placement screens (no drawing happens here).

    Each side keeps its own layout: a tuple of slot numbers, so the two sides can never
    share one list. Both start as DEFAULT_LAYOUT. Clicks go through castle.place_block()
    and castle.remove_block(), which check with castle.layout_problem(), so a layout
    stays legal and no rule is repeated here. Cover slots never depend on the team size
    or roles (no character stands on one), so the layouts are kept when teams change.
    """

    def __init__(self):
        self.layouts = {"left": DEFAULT_LAYOUT, "right": DEFAULT_LAYOUT}

    def click_slot(self, side, slot):
        """A click on cover slot `slot` of `side`: place a block on an empty slot, or remove
        the block on an occupied one. Returns a short message for the status line."""
        layout = self.layouts[side]
        if slot in layout:
            self.layouts[side], removed = remove_block(layout, slot)
            if len(removed) > 1:
                return (
                    "Block removed, and the raised block on top of it too "
                    "(a raised block needs a block under it)."
                )
            return "Block removed."
        self.layouts[side], problem = place_block(layout, slot)
        if problem is not None:
            return f"No block there: {problem}."
        return "Block placed."

    def apply_preset(self, side, name):
        """Give `side` one of the COVER_PRESETS (M6.2). It is checked with layout_problem() like
        any layout, and it stays editable slot by slot. Returns a short message."""
        layout = COVER_PRESETS[name]
        problem = layout_problem(layout)
        if problem is not None:  # both presets are legal; this is a safety net
            return f"{name} can't be used: {problem}."
        self.layouts[side] = layout
        return f"{name} ({PRESET_NOTES[name]}). Click blocks to change it."
