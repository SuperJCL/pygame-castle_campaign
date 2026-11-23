"""Convert Battle events into battle-log text and the previous-shot display."""
from battle import other_side


# M6.2: the result of a shot, by where it landed (the "kind" of Battle's explosion event).
IMPACT_TITLES = {
    "character": "DIRECT HIT",
    "block": "COVER HIT",
    "ground": "GROUND IMPACT",
}

LANDING_WORDS = (
    ("character", "direct"),
    ("block", "cover"),
    ("ground", "ground"),
    ("out", "out"),
)


def describe_event(event):
    """Turn one battle event into combat-log lines (an empty list if it isn't worth logging)."""
    kind = event["type"]
    if kind == "action" and event["action"] != "special":
        verb = "attacks" if event["action"] == "attack" else "defends"
        return [f"{event['side'].upper()} {event['name']} {verb}."]
    if kind == "special":
        return [f"{event['side'].upper()} {event['message']}"]
    if kind == "explosion":
        lines = []
        if event["blocks_hit"]:
            plural = "s" if event["blocks_hit"] != 1 else ""
            lines.append(
                f"Explosion: {event['blocks_hit']} cover block{plural}, "
                f"{event['damage']} damage."
            )
            if event.get("guarded"):
                lines.append("Cover Guard halved the damage to the blocks.")
        target_side = other_side(event["side"]).upper()
        for name in event["covered"]:
            lines.append(f"{target_side} {name} was shielded by cover.")
        for hit in event["characters_hit"]:
            ending = " and is defeated!" if hit["defeated"] else "."
            lines.append(
                f"{target_side} {hit['name']} takes {hit['damage']} damage{ending}"
            )
        return lines or ["Explosion: nothing was close enough."]
    if kind == "miss":
        return ["The shot flew off the battlefield."]
    if kind == "split":
        return [f"Airburst: the shell splits into {event['shells']}."]
    if kind == "exp":
        if event["levels"] == 0:
            return [f"{event['name']} gains {event['amount']} EXP."]
        return [f"{event['name']} gains {event['amount']} EXP and levels up!"]
    if kind == "round":
        return [f"--- Round {event['number']} ---"]
    if kind == "invalid":
        return [f"Not allowed: {event['reason']}."]
    if kind == "guard_granted":
        return [
            f"{event['side'].upper()} {event['name']}: Guarded Strike next turn (+25% ATK)."
        ]
    if kind == "guard_used":
        return [
            f"{event['side'].upper()} {event['name']} uses Guarded Strike: ATK x1.25."
        ]
    if kind == "guard_expired":
        return [
            f"{event['side'].upper()} {event['name']}'s Guarded Strike expired unused."
        ]
    if kind == "game_over":
        lines = []
        if event["reason"] == "timeout":
            lines.append("Round limit reached: no team was eliminated.")
        if event["winner"] == "draw":
            return lines + ["It's a draw!"]
        return lines + [f"{event['winner'].upper()} wins!"]
    return []  # "fire" and "turn" are shown by the HUD instead


def impact_summary(event, destroyed=0):
    """One short line on what a shot did (M6.2), from its "explosion" or "miss" event: where it
    landed (DIRECT HIT, COVER HIT, GROUND IMPACT or OUT OF FIELD), then what that did. Several hurt
    characters are only counted here; the log names them. `destroyed`: blocks the shot destroyed
    (the event only counts the blocks it reached), so "block destroyed, Archer shielded" can be said."""
    if event["type"] == "miss":
        return "OUT OF FIELD · no damage"
    parts = []
    if destroyed:
        parts.append(f"{destroyed} block{'s' if destroyed > 1 else ''} destroyed")
    hits = event["characters_hit"]
    if len(hits) == 1:
        hit = hits[0]
        parts.append(
            f"{hit['name']} -{hit['damage']} HP"
            + (", defeated" if hit["defeated"] else "")
        )
    elif hits:
        defeated = sum(1 for hit in hits if hit["defeated"])
        parts.append(
            f"{len(hits)} hit, -{sum(hit['damage'] for hit in hits)} HP"
            + (f", {defeated} defeated" if defeated else "")
        )
    covered = event["covered"]
    if covered:
        parts.append(
            f"{covered[0]} shielded"
            if len(covered) == 1
            else f"{len(covered)} shielded"
        )
    if not parts and event["blocks_hit"]:  # only cover was hit: how much in all
        blocks = event["blocks_hit"]
        parts.append(
            f"{blocks} block{'s' if blocks > 1 else ''}, -{event['damage']} HP"
        )
    return f"{IMPACT_TITLES[event['kind']]} · {', '.join(parts) or 'no damage'}"


def attack_summary(events, destroyed=0, name=None):
    """The short result of a whole attack (M6.3), from the "explosion" and "miss" events of its shells.
    A one-shell attack (name None) reads as before (impact_summary). For a Triple Volley or Airburst
    (name: "TRIPLE VOLLEY" or "AIRBURST"): where its shells landed, then what they did together: each
    hurt character's total, who was shielded and never hit, and the blocks destroyed (or else the
    damage to the cover). `destroyed`: the blocks the whole attack destroyed."""
    if name is None:
        return impact_summary(events[-1], destroyed)
    places = landing_places(events)
    damage, defeated = {}, set()
    for event in events:
        for hit in event.get("characters_hit", ()):
            damage[hit["name"]] = damage.get(hit["name"], 0) + hit["damage"]
            if hit["defeated"]:
                defeated.add(hit["name"])
    parts = [
        f"{who} -{hp} HP" + (", defeated" if who in defeated else "")
        for who, hp in damage.items()
    ]
    shielded = [
        who for event in events for who in event.get("covered", ()) if who not in damage
    ]
    if shielded:
        parts.append(f"{', '.join(dict.fromkeys(shielded))} shielded")
    if destroyed:
        parts.append(f"{destroyed} block{'s' if destroyed > 1 else ''} destroyed")
    cover_damage = sum(event.get("damage", 0) for event in events)
    if not parts and cover_damage:
        parts.append(f"cover -{cover_damage} HP")
    return f"{name} · {places} · {', '.join(parts) or 'no damage'}"


def landing_places(events):
    """Where the shells of one attack landed, counted (M6.3), from their "explosion" and "miss"
    events: "2 direct, 1 out". (M6.4: the last-shot line uses it too.)"""
    landed = ["out" if event["type"] == "miss" else event["kind"] for event in events]
    return ", ".join(
        f"{landed.count(kind)} {word}" for kind, word in LANDING_WORDS if kind in landed
    )


class ShotRecord:
    """M6.4: one team's last shot that has landed, so that team can see it on its next turn.

    It keeps the aim the shot was fired with (the cannon's own aim: for a Triple Volley or an
    Airburst, the aim of the center shell) and the "explosion" and "miss" events of its shells.
    It is only read: nothing is aimed or fired from it.
    """

    def __init__(self, side, angle, power):
        self.side = side
        self.angle = angle
        self.power = power
        self.landings = []  # the "explosion" and "miss" events of its shells, in landing order

    def text(self):
        """The panel line, e.g. "Last shot · 45° / 83 · COVER HIT". With several shells: where
        they landed, counted ("2 direct, 1 ground")."""
        if len(self.landings) == 1:
            landing = self.landings[0]
            if landing["type"] == "miss":
                result = "OUT OF FIELD"
            else:
                result = IMPACT_TITLES[landing["kind"]]
        else:
            result = landing_places(self.landings)
        return f"Last shot · {self.angle}° / {self.power} · {result}"

    def mark(self):
        """Where the center shell landed (Battle marks that shell's event), or None: that shell
        left the field (words only), or no landing is known to be the center shell's."""
        for landing in self.landings:
            if landing.get("center") and landing["type"] == "explosion":
                return landing["x"], landing["y"]
        return None
