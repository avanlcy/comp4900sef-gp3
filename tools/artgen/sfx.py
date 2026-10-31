"""Sounds for Dead Fire: engines, skid, weapons, explosion, item and UI sounds (spec 4.1, plan Task 6).
Each recipe is `recipe(seed, seconds) -> float32 mono array at 44.1 kHz`, peak-normalised and free of DC offset.
Loops are built from whole cycles and circularly filtered noise (so they are periodic), then rotated to the
start point where the first and last samples and the first and last 10 ms agree best.

    python -I tools/artgen/build_all.py --kind sounds      (writes art/sounds/SW_DF_<Name>.wav, 16-bit mono)
"""
import os
import wave

import numpy as np

SR = 44100
PEAK_DB = -3.0
UI_PEAK_DB = -8.0
TWO_PI = 2.0 * np.pi


# --- helpers ----------------------------------------------------------------------------------------
def _n(seconds):
    return int(round(seconds * SR))


def _t(seconds):
    return np.arange(_n(seconds), dtype=np.float64) / SR


def _snap(freq, seconds):
    """The nearest frequency that fits a whole number of cycles in `seconds` (so a loop joins without a step)."""
    return max(1, round(freq * seconds)) / seconds


def _noise(rng, n, lo=None, hi=None, slope=0.0):
    """Unit-variance noise limited to lo..hi Hz with smooth edges, filtered circularly (the result is periodic).
    slope: spectral tilt, amplitude ~ f**slope (negative = darker)."""
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    g = np.ones_like(f)
    if lo:
        g *= 1.0 / (1.0 + (lo / np.maximum(f, 1e-3)) ** 4)
    if hi:
        g *= 1.0 / (1.0 + (np.maximum(f, 1e-3) / hi) ** 4)
    if slope:
        g *= (np.maximum(f, 20.0) / 1000.0) ** slope
    g[0] = 0.0
    x = np.fft.irfft(spec * g, n)
    return x / max(x.std(), 1e-9)


def _band(rng, n, centre, width):
    return _noise(rng, n, max(centre - width / 2, 20.0), centre + width / 2)


def _exp(t, tau):
    return np.exp(-t / tau)


def _attack(t, a):
    return np.minimum(t / a, 1.0) if a > 0 else np.ones_like(t)


def _sweep(t, f0, f1, curve=1.0):
    """Sine whose frequency glides from f0 to f1 over the length of t (curve > 1 bends it late)."""
    u = (t / max(t[-1], 1e-9)) ** curve
    f = f0 + (f1 - f0) * u
    return np.sin(TWO_PI * np.cumsum(f) / SR)


def _saw(phase):
    return 2.0 * (phase % 1.0) - 1.0


def _ping(t, freqs, taus, amps=None):
    """Inharmonic ringing partials."""
    amps = amps or [1.0] * len(freqs)
    return sum(a * np.sin(TWO_PI * f * t) * _exp(t, tau) for f, tau, a in zip(freqs, taus, amps))


def _note(t, t0, freq, tau, overtones=(1.0, 0.35, 0.12), attack=0.004):
    """A bell-like note starting at t0."""
    u = np.clip(t - t0, 0.0, None)
    on = (t >= t0).astype(np.float64)
    return on * _attack(u, attack) * _exp(u, tau) * sum(a * np.sin(TWO_PI * freq * (k + 1) * u) for k, a in enumerate(overtones))


def _finish(x, ui=False, loop=False, fade_ms=2.0):
    x = np.asarray(x, dtype=np.float64)
    x = x - x.mean()
    if not loop:
        k = max(1, int(fade_ms * 1e-3 * SR))
        ramp = np.linspace(0.0, 1.0, k)
        x[:k] *= ramp
        x[-k:] *= ramp[::-1]
        x = x - x.mean()
    x = x * (10 ** ((UI_PEAK_DB if ui else PEAK_DB) / 20.0) / max(np.abs(x).max(), 1e-9))
    if loop:
        x = _seam(x)
    return x.astype(np.float32)


def _seam(x):
    """Rotates a periodic signal to the start whose first and last samples (and 10 ms RMS) agree best."""
    n, w = len(x), int(0.010 * SR)
    step = np.abs(x - np.roll(x, 1))  # step[o] = |x[o] - x[o-1]|: the join when the loop starts at o
    c = np.concatenate([[0.0], np.cumsum(np.tile(x * x, 2))])
    first = np.sqrt((c[w:w + n] - c[:n]) / w)  # RMS of the 10 ms starting at o
    last = np.sqrt((c[n:2 * n] - c[n - w:2 * n - w]) / w)  # RMS of the 10 ms ending at o - 1
    ratio = np.abs(last - first) / np.maximum(first, 1e-9)
    cost = np.maximum(step / 0.006, ratio / 0.06)
    cost[first < 0.3 * np.sqrt(np.mean(x * x))] = np.inf  # not a start in a quiet dip
    return np.roll(x, -int(np.argmin(cost)))


# --- loops ------------------------------------------------------------------------------------------
def _engine(seed, seconds, f0, cylinders, tilt, drive, grit, wobble):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    f0 = _snap(f0, seconds)
    fire = _snap(f0 * cylinders / 4.0, seconds)  # firing-order pulse
    rev = _snap(2.5, seconds)
    phase = TWO_PI * f0 * t + wobble * np.sin(TWO_PI * rev * t)
    x = np.zeros_like(t)
    for k in range(1, 15):
        amp = k ** -tilt * (1.0 + 0.5 * np.sin(k * 1.7 + seed))  # harmonic stack, uneven like an exhaust note
        x += amp * np.sin(k * phase + rng.uniform(0, TWO_PI))
    pulse = 1.0 + 0.40 * np.cos(TWO_PI * fire * t) + 0.18 * np.cos(TWO_PI * 2 * fire * t + 0.9) + 0.10 * np.sin(TWO_PI * rev * t)
    x = np.tanh(drive * x / np.abs(x).max() * pulse)
    x += grit * pulse * _noise(rng, len(t), 40, 600, slope=-0.8) * 0.3
    x += 0.03 * _noise(rng, len(t), 1200, 3500) * np.maximum(pulse - 0.6, 0) * grit
    return _finish(x, loop=True)


def engine_sedan(seed, seconds):
    return _engine(seed, seconds, 55.0, 4, tilt=0.9, drive=1.6, grit=0.6, wobble=0.25)


def engine_brute(seed, seconds):
    return _engine(seed, seconds, 45.0, 8, tilt=0.6, drive=2.4, grit=0.9, wobble=0.35)


def engine_viper(seed, seconds):
    return _engine(seed, seconds, 70.0, 6, tilt=0.5, drive=2.0, grit=0.5, wobble=0.15)


def skid(seed, seconds):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    chatter = 1.0 + 0.25 * np.sin(TWO_PI * _snap(7.0, seconds) * t) + 0.12 * np.sin(TWO_PI * _snap(13.0, seconds) * t + 1.0)
    x = chatter * _band(rng, len(t), 1200, 900)
    x += 0.35 * _band(rng, len(t), 2600, 1200) * (1.0 + 0.5 * np.sin(TWO_PI * _snap(5.0, seconds) * t))
    x += 0.5 * np.sin(TWO_PI * _snap(1150.0, seconds) * t + 0.4 * np.sin(TWO_PI * _snap(3.0, seconds) * t))  # tyre squeal
    return _finish(x, loop=True)


def rocket_loop(seed, seconds):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    flutter = 1.0 + 0.3 * np.sin(TWO_PI * _snap(23.0, seconds) * t) + 0.15 * np.sin(TWO_PI * _snap(41.0, seconds) * t + 2.0)
    x = flutter * _noise(rng, len(t), 80, 1800, slope=-0.6)
    x += 0.22 * _noise(rng, len(t), 2500, 6000) * flutter
    x += 0.6 * np.sin(TWO_PI * _snap(95.0, seconds) * t) + 0.3 * np.sin(TWO_PI * _snap(190.0, seconds) * t + 1.3)
    return _finish(x, loop=True)


# --- shots, hits, explosions ------------------------------------------------------------------------
def crash(seed, seconds):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    x = _noise(rng, len(t), 60, 7000, slope=-0.4) * _exp(t, 0.05) * _attack(t, 0.0008)
    x += 0.45 * _ping(t, [310, 770, 1480, 2630], [0.18, 0.12, 0.09, 0.06], [1.0, 0.7, 0.5, 0.35])
    x += 1.2 * _sweep(t, 110, 45) * _exp(t, 0.10)
    x += 0.5 * _noise(rng, len(t), 200, 2500) * _exp(t, 0.22) * (rng.random(len(t)) < 0.02)  # scattered debris ticks
    return _finish(x)


def car_gun(seed, seconds):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    burst = _noise(rng, len(t), 400, 9000) * _exp(t, 0.030) * _attack(t, 0.0004)
    thump = _sweep(t, 140, 60, 0.7) * _exp(t, 0.055)
    x = 0.9 * burst + 1.3 * thump + 0.25 * _noise(rng, len(t), 100, 1500) * _exp(t, 0.09)
    return _finish(x)


def rifle(seed, seconds):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    crack = _noise(rng, len(t), 1500, 14000) * _exp(t, 0.012) * _attack(t, 0.0002)
    body = _noise(rng, len(t), 200, 3000) * _exp(t, 0.045)
    thump = _sweep(t, 110, 50, 0.6) * _exp(t, 0.07)
    tail = _noise(rng, len(t), 150, 1200, slope=-0.8) * _exp(t, 0.14) * 0.35
    return _finish(1.0 * crack + 0.7 * body + 1.4 * thump + tail)


def rocket_launch(seed, seconds):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    rise = _attack(t, 0.12) * _exp(t, 0.55)
    x = _noise(rng, len(t), 120, 2500, slope=-0.4) * rise
    x += 0.6 * _noise(rng, len(t), 3000, 9000) * _attack(t, 0.05) * _exp(t, 0.25)  # ignition hiss
    x += 1.1 * _sweep(t, 55, 110, 0.5) * rise
    x += 0.8 * _noise(rng, len(t), 300, 5000) * _exp(t, 0.012) * _attack(t, 0.0005)  # the pop of release
    return _finish(x)


def explosion(seed, seconds):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    n = len(t)
    blast = _noise(rng, n, 50, 4000, slope=-0.8) * _exp(t, 0.16) * _attack(t, 0.0006)
    rumble = _noise(rng, n, 25, 140) * _exp(t, 0.80) * _attack(t, 0.01)
    sub = _sweep(t, 62, 28, 0.6) * _exp(t, 0.55) * _attack(t, 0.006)
    mid = _noise(rng, n, 150, 1400, slope=-0.7) * _exp(t, 0.40) * _attack(t, 0.004)
    # crackle: sparse impulses whose density falls with time
    ticks = (rng.random(n) < 0.0035 * _exp(t, 0.9)).astype(np.float64) * rng.uniform(0.4, 1.0, n)
    k = np.arange(0, int(0.012 * SR))
    kernel = np.exp(-k / (0.002 * SR)) * np.sin(TWO_PI * 2200 * k / SR)
    crackle = np.convolve(ticks, kernel)[:n] * _attack(t, 0.08)
    x = 1.0 * blast + 1.7 * rumble + 1.5 * sub + 0.6 * mid + 2.2 * crackle
    return _finish(x * np.minimum(1.0, (seconds - t) / 0.4))


def tire_pop(seed, seconds):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    bang = _noise(rng, len(t), 300, 10000) * _exp(t, 0.012) * _attack(t, 0.0003)
    hiss = _noise(rng, len(t), 3500, 9500) * _exp(t, 0.16) * _attack(t, 0.01) * 0.45
    thump = _sweep(t, 130, 70, 0.6) * _exp(t, 0.06)
    return _finish(1.0 * bang + hiss + 1.1 * thump)


def impact_metal(seed, seconds):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    x = _noise(rng, len(t), 1000, 10000) * _exp(t, 0.008) * _attack(t, 0.0002)
    x += 0.8 * _ping(t, [420, 1130, 2370, 3900], [0.10, 0.07, 0.05, 0.03], [1.0, 0.6, 0.4, 0.25])
    return _finish(x)


def impact_dirt(seed, seconds):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    x = _noise(rng, len(t), 60, 700, slope=-0.5) * _exp(t, 0.055) * _attack(t, 0.0015)
    x += 0.8 * _noise(rng, len(t), 800, 3500) * _exp(t, 0.02) * _attack(t, 0.001)  # grit
    x += 0.9 * _sweep(t, 95, 50, 0.6) * _exp(t, 0.06)
    return _finish(x)


# --- bombs, items, shield, boost --------------------------------------------------------------------
def bomb_arm(seed, seconds):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    click = _noise(rng, len(t), 1200, 8000) * _exp(t, 0.006)
    click2 = np.roll(click, int(0.11 * SR)) * 0.8  # a second latch
    u = np.clip(t - 0.12, 0.0, None)
    rise = _sweep(t, 700, 1900, 1.4) * (t >= 0.12) * _attack(u, 0.02) * _exp(u, 0.2)
    return _finish(click + click2 + 0.7 * rise)


def bomb_beep(seed, seconds):
    t = _t(seconds)
    env = np.sin(np.pi * np.clip(t / seconds, 0, 1)) ** 0.5 * np.minimum(1.0, (seconds - t) / 0.006)
    return _finish(np.sin(TWO_PI * 2000 * t) * env, ui=True)


def loot_open(seed, seconds):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    thunk = _sweep(t, 160, 90, 0.7) * _exp(t, 0.07)
    creak = _band(rng, len(t), 700, 500) * _exp(t, 0.12) * _attack(t, 0.01) * 0.35
    sparkle = sum(_note(t, 0.10 + 0.07 * i, f, 0.20) for i, f in enumerate([784, 988, 1175, 1568]))
    return _finish(1.0 * thunk + creak + 0.5 * sparkle)


def pickup(seed, seconds):
    t = _t(seconds)
    return _finish(sum(_note(t, 0.085 * i, f, 0.14) for i, f in enumerate([523.25, 659.25, 783.99, 1046.5])))


def deny(seed, seconds):
    t = _t(seconds)
    f = 240 - 110 * np.clip(t / seconds, 0, 1)
    phase = np.cumsum(f) / SR
    buzz = 0.6 * _saw(phase) + 0.2 * np.sign(np.sin(TWO_PI * phase))
    buzz *= 1.0 + 0.3 * np.sin(TWO_PI * 38 * t)
    return _finish(buzz * _attack(t, 0.006) * _exp(t, 0.30) * np.minimum(1.0, (seconds - t) / 0.03))


def boost(seed, seconds):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    n = len(t)
    x = np.zeros(n)
    centres = np.geomspace(300, 5000, 9)
    for i, c in enumerate(centres):  # a bright band moves up through the noise
        peak = 0.2 + 0.55 * i / (len(centres) - 1)
        env = np.exp(-0.5 * ((t - peak * seconds) / (0.16 * seconds)) ** 2)
        x += _band(rng, n, c, c * 0.8) * env
    x *= _attack(t, 0.04) * np.minimum(1.0, (seconds - t) / 0.35)
    x += 0.7 * _sweep(t, 90, 260, 1.2) * _attack(t, 0.05) * np.minimum(1.0, (seconds - t) / 0.4)
    return _finish(x)


def shield_up(seed, seconds):
    t = _t(seconds)
    f = 300 + 900 * (t / seconds) ** 1.3
    ph = np.cumsum(f) / SR
    x = np.sin(TWO_PI * ph + 1.5 * np.sin(TWO_PI * 18 * t)) + 0.4 * np.sin(TWO_PI * 2 * ph)
    return _finish(x * _attack(t, 0.03) * np.minimum(1.0, (seconds - t) / 0.12))


def shield_hit(seed, seconds):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    x = _ping(t, [880, 1320, 2110, 3170], [0.12, 0.09, 0.06, 0.04], [1.0, 0.7, 0.45, 0.3])
    x = x * (1.0 + 0.4 * np.sin(TWO_PI * 30 * t))
    x += 0.5 * _noise(rng, len(t), 800, 8000) * _exp(t, 0.01)
    return _finish(x)


def shield_down(seed, seconds):
    t = _t(seconds)
    f = 900 * np.exp(-3.0 * t / seconds) + 120
    ph = np.cumsum(f) / SR
    x = (np.sin(TWO_PI * ph) + 0.3 * np.sin(TWO_PI * 3 * ph)) * (1.0 + 0.5 * np.sin(TWO_PI * 24 * t))
    return _finish(x * _attack(t, 0.01) * _exp(t, 0.25) * np.minimum(1.0, (seconds - t) / 0.08))


def checkpoint(seed, seconds):
    t = _t(seconds)
    return _finish(_note(t, 0.0, 880.0, 0.12) + _note(t, 0.11, 1318.5, 0.17))


def lap(seed, seconds):
    t = _t(seconds)
    x = _note(t, 0.0, 523.25, 0.16) + _note(t, 0.14, 659.25, 0.16) + _note(t, 0.28, 783.99, 0.16)
    x += _note(t, 0.42, 1046.5, 0.45) + 0.7 * _note(t, 0.42, 523.25, 0.45) + 0.6 * _note(t, 0.42, 659.25, 0.45)
    return _finish(x)


def ui_click(seed, seconds):
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    x = _noise(rng, len(t), 1500, 9000) * _exp(t, 0.006) * 0.6 + np.sin(TWO_PI * 1300 * t) * _exp(t, 0.011)
    return _finish(x, ui=True, fade_ms=1.0)


def ui_hover(seed, seconds):
    t = _t(seconds)
    env = np.sin(np.pi * np.clip(t / seconds, 0, 1)) ** 2
    return _finish((np.sin(TWO_PI * 950 * t) + 0.3 * np.sin(TWO_PI * 1900 * t)) * env, ui=True)


RECIPES = {
    "engine_sedan": engine_sedan, "engine_brute": engine_brute, "engine_viper": engine_viper,
    "skid": skid, "crash": crash, "car_gun": car_gun, "rifle": rifle,
    "rocket_launch": rocket_launch, "rocket_loop": rocket_loop, "explosion": explosion,
    "bomb_arm": bomb_arm, "bomb_beep": bomb_beep, "loot_open": loot_open, "pickup": pickup, "deny": deny,
    "boost": boost, "shield_up": shield_up, "shield_hit": shield_hit, "shield_down": shield_down,
    "tire_pop": tire_pop, "impact_metal": impact_metal, "impact_dirt": impact_dirt,
    "checkpoint": checkpoint, "lap": lap, "ui_click": ui_click, "ui_hover": ui_hover,
}


def write_wav(path, x):
    pcm = np.round(np.clip(x, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def build(spec, out_dir):
    """Writes <out_dir>/<spec.name>.wav (16-bit mono 44.1 kHz) from the spec's recipe and returns the path."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, spec.name + ".wav")
    write_wav(path, RECIPES[spec.recipe](spec.seed, spec.seconds))
    return path
