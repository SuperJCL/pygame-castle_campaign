"""Sound effects for Castle Siege (M4.2-A), made in code: there are no sound files.

Each effect is a list of numbers between -1 and 1 (the samples), built from sine waves
(tones) and random noise (bangs), shaped by envelopes that fade them out. SoundBoard turns
them into pygame.mixer.Sound objects once, when the game starts.

The game never depends on sound: if the computer has no audio device, or the mixer can't
be started, SoundBoard is simply silent (available is False) and play() does nothing.
main.py plays a sound when it reads a Battle event (a shot fired, an explosion, a Defend or
Rally, a level-up, the end of the game); nothing here changes a rule.
"""
import array
import functools
import math
import random

import pygame

SAMPLE_RATE = 22050            # samples per second: plenty for short effects
BUFFER = 512                   # mixer buffer: about 23 ms, so a sound starts with no noticeable delay
VOLUME = 0.6
SOUND_NAMES = ("fire", "explosion", "cover_hit", "cover_destroyed", "defend", "level_up", "victory", "defeat",
               "draw")
PEAK = 0.9                     # every effect is scaled to this loudest sample
FADE_OUT = 0.01                # the last 10 ms fade to silence, so no effect ends with a click


def _bang(rate, seconds, noise_decay, noise_smooth, tone_start, tone_end, tone_decay, tone_level, rng):
    """Noise that dies away (the bang), on top of a falling low tone (the thump).

    noise_smooth (0-1): the noise is smoothed by a one-pole low-pass filter; smaller is deeper.
    """
    samples, smoothed, phase = [], 0.0, 0.0
    count = int(rate * seconds)
    for i in range(count):
        t = i / rate
        smoothed += noise_smooth * (rng.uniform(-1, 1) - smoothed)
        frequency = tone_start + (tone_end - tone_start) * i / count
        phase += 2 * math.pi * frequency / rate
        attack = min(1.0, t / 0.004)                     # 4 ms rise, so the start doesn't click
        samples.append(attack * (smoothed * math.exp(-t * noise_decay)
                                 + tone_level * math.sin(phase) * math.exp(-t * tone_decay)))
    return samples


def _crumble(rate, rng):
    """Cover breaking: a few short bursts of rubble one after another, and a low thud."""
    samples, smoothed = [], 0.0
    bursts = (0.0, 0.07, 0.15, 0.24, 0.33)
    for i in range(int(rate * 0.5)):
        t = i / rate
        smoothed += 0.3 * (rng.uniform(-1, 1) - smoothed)
        rubble = sum((0.8 ** n) * math.exp(-(t - start) * 30) for n, start in enumerate(bursts) if t >= start)
        thud = 0.4 * math.sin(2 * math.pi * 110 * t) * math.exp(-t * 8)
        samples.append(min(1.0, t / 0.004) * (smoothed * rubble + thud))
    return samples


def _clang(rate, rng):
    """Defend (M5.2-A): a shield is raised. A short scrape of noise, then a metallic ring: two
    tones that are not whole multiples of each other, which is what makes it sound like metal."""
    samples, smoothed = [], 0.0
    for i in range(int(rate * 0.4)):
        t = i / rate
        smoothed += 0.6 * (rng.uniform(-1, 1) - smoothed)
        scrape = smoothed * math.exp(-t * 40)
        ring = (math.sin(2 * math.pi * 620 * t) + 0.6 * math.sin(2 * math.pi * 1490 * t)) * math.exp(-t * 9)
        samples.append(min(1.0, t / 0.004) * (0.5 * scrape + 0.5 * ring))
    return samples


def _melody(rate, notes, harmonics, decay):
    """Notes one after another: each (frequency in Hz, seconds), a sine plus some overtones."""
    samples = []
    for frequency, seconds in notes:
        count = int(rate * seconds)
        for i in range(count):
            t = i / rate
            envelope = min(1.0, t / 0.008) * math.exp(-t * decay) * min(1.0, (count - i) / (rate * 0.02))
            samples.append(envelope * sum(level * math.sin(2 * math.pi * frequency * n * t)
                                          for n, level in harmonics))
    return samples


@functools.lru_cache(maxsize=None)
def synthesize(name, rate):
    """The samples of the effect `name` at `rate` samples per second, as a tuple of numbers
    from -1 to 1. Always the same for the same name (the noise has a fixed seed). Made once
    per run (cached), because it is pure Python arithmetic."""
    rng = random.Random(name)
    if name == "fire":                    # the cannon: a sharp bang with a short low thump
        samples = _bang(rate, 0.32, 25, 0.35, 95, 45, 11, 0.9, rng)
    elif name == "explosion":             # the impact: deeper and longer
        samples = _bang(rate, 0.7, 5.5, 0.12, 60, 35, 6, 0.6, rng)
    elif name == "cover_hit":             # a block is hit: a short "thock"
        samples = _bang(rate, 0.16, 40, 0.5, 220, 140, 30, 0.8, rng)
    elif name == "cover_destroyed":       # a block breaks: rubble
        samples = _crumble(rate, rng)
    elif name == "defend":                # Defend or Rally: a metal shield rings
        samples = _clang(rate, rng)
    elif name == "level_up":              # three quick rising notes
        samples = _melody(rate, ((784, 0.12), (988, 0.12), (1319, 0.2)), ((1, 1.0), (2, 0.3)), 6)
    elif name == "victory":               # C - E - G - high C
        samples = _melody(rate, ((523.25, 0.15), (659.25, 0.15), (783.99, 0.15), (1046.5, 0.5)),
                          ((1, 1.0), (2, 0.35), (3, 0.15)), 3)
    elif name == "defeat":                # G - E flat - C, falling and slower
        samples = _melody(rate, ((392.0, 0.25), (311.13, 0.25), (261.63, 0.45)),
                          ((1, 1.0), (3, 0.3)), 2.5)
    elif name == "draw":                  # two neutral notes, D then A
        samples = _melody(rate, ((587.33, 0.25), (440.0, 0.45)), ((1, 1.0), (2, 0.2)), 3)
    else:
        raise ValueError(f"no sound called {name!r}")
    loudest = max(abs(s) for s in samples)
    fade = int(rate * FADE_OUT)
    count = len(samples)
    return tuple(PEAK * s / loudest * min(1.0, (count - 1 - i) / fade) for i, s in enumerate(samples))


def to_bytes(samples, size, channels):
    """Samples as the raw bytes pygame.mixer.Sound(buffer=...) expects for the mixer's format:
    size -16 (signed 16-bit) or 32 (32-bit float), repeated for each channel. Other formats
    raise ValueError (then the game is silent)."""
    if size == -16:
        data = array.array("h", (round(s * 32767) for s in samples for _ in range(channels)))
    elif size == 32:
        data = array.array("f", (s for s in samples for _ in range(channels)))
    else:
        raise ValueError(f"unsupported mixer sample size {size}")
    return data.tobytes()


class SoundBoard:
    """The game's sound effects, ready to play. Silent (available False) without a mixer."""

    def __init__(self):
        self.sounds = {}
        self.muted = False
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(SAMPLE_RATE, -16, 1, BUFFER)
            rate, size, channels = pygame.mixer.get_init()
            for name in SOUND_NAMES:
                effect = pygame.mixer.Sound(buffer=to_bytes(synthesize(name, rate), size, channels))
                effect.set_volume(VOLUME)
                self.sounds[name] = effect
        except (pygame.error, ValueError, TypeError):
            self.sounds = {}              # no audio device, or a format we can't fill: stay silent
        self.available = bool(self.sounds)

    def play(self, name):
        """Start the effect `name` (it plays alongside any others). Nothing if muted or silent."""
        if self.available and not self.muted:
            self.sounds[name].play()

    def stop(self):
        """Stop every sound now (a rematch, new teams, quitting), so nothing old keeps playing."""
        if self.available:
            pygame.mixer.stop()

    def toggle_mute(self):
        """M: sound off (stopping what plays) or back on."""
        self.muted = not self.muted
        if self.muted:
            self.stop()
