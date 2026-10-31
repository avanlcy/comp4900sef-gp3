"""Checks the generated sounds (plan Task 6): duration, peak level, DC offset, seamless loops, determinism, and that
the written WAV is 16-bit mono 44.1 kHz. `-v` prints each file's spectral centroid and RMS envelope (the agent cannot
listen, so these numbers are the record; a person listens to the set in the playtest checklist).

    python -I tools/artgen/test_sounds.py [-v]
"""
import os
import sys
import tempfile
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from artgen import catalog, sfx  # noqa: E402

SR = 44100
checks = 0
failures = []


def check(ok, msg):
    global checks
    checks += 1
    if not ok:
        failures.append(msg)


def db(v):
    return 20 * np.log10(max(float(v), 1e-9))


def rms(x):
    return float(np.sqrt(np.mean(np.square(x.astype(np.float64)))))


def read_wav(path):
    with wave.open(path, "rb") as w:
        params = (w.getnchannels(), w.getsampwidth(), w.getframerate())
        raw = w.readframes(w.getnframes())
    return params, np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def centroid(x):
    spec = np.abs(np.fft.rfft(x.astype(np.float64)))
    freqs = np.fft.rfftfreq(len(x), 1.0 / SR)
    return float((spec * freqs).sum() / max(spec.sum(), 1e-12))


def envelope(x, bins=8):
    return [db(rms(c)) for c in np.array_split(x, bins)]


def test_catalogue():
    check(len(catalog.SOUNDS) == 26, "26 sounds in the catalogue, got %d" % len(catalog.SOUNDS))
    for s in catalog.SOUNDS:
        check(s.recipe != "todo", "%s: recipe is still todo" % s.name)
        check(s.recipe in sfx.RECIPES, "%s: recipe %s not in sfx.RECIPES" % (s.name, s.recipe))
    check(set(s.recipe for s in catalog.SOUNDS) == set(sfx.RECIPES), "RECIPES and the catalogue disagree")


def test_sounds(verbose):
    out_dir = tempfile.mkdtemp(prefix="dfsfx_")
    for s in catalog.SOUNDS:
        if s.recipe not in sfx.RECIPES:
            continue
        x = sfx.RECIPES[s.recipe](s.seed, s.seconds)
        check(x.dtype == np.float32 and x.ndim == 1, "%s: float32 mono expected, got %s %s" % (s.name, x.dtype, x.shape))
        check(abs(len(x) / SR - s.seconds) <= 0.001, "%s: %.4f s, want %.3f" % (s.name, len(x) / SR, s.seconds))
        peak = float(np.abs(x).max())
        check(-12.0 <= db(peak) <= -1.0, "%s: peak %.1f dBFS outside -12..-1" % (s.name, db(peak)))
        check(abs(float(x.mean())) < 0.01, "%s: DC offset %.4f" % (s.name, float(x.mean())))
        check(np.isfinite(x).all(), "%s: not finite" % s.name)
        if s.loop:
            step = abs(float(x[0]) - float(x[-1]))
            n10 = int(0.010 * SR)
            r0, r1 = rms(x[:n10]), rms(x[-n10:])
            check(step < 0.02, "%s: loop step |x[0]-x[-1]| = %.4f" % (s.name, step))
            check(r0 > 1e-4 and abs(r1 - r0) <= 0.2 * r0, "%s: loop ends RMS %.4f vs %.4f" % (s.name, r0, r1))
        check(np.array_equal(x, sfx.RECIPES[s.recipe](s.seed, s.seconds)), "%s: not deterministic" % s.name)
        # the written file
        path = sfx.build(s, out_dir)
        check(os.path.basename(path) == s.name + ".wav", "%s: written as %s" % (s.name, os.path.basename(path)))
        params, y = read_wav(path)
        check(params == (1, 2, SR), "%s: WAV format %s, want mono 16-bit 44100" % (s.name, params))
        check(len(y) == len(x) and float(np.abs(y - x).max()) < 2.0 / 32768, "%s: WAV differs from the recipe output" % s.name)
        if verbose:
            print("%-22s %5.2fs %s centroid %6.0f Hz  peak %5.1f dBFS  rms env (dBFS, 8 slices): %s"
                  % (s.name, s.seconds, "loop" if s.loop else "    ", centroid(y), db(np.abs(y).max()),
                     " ".join("%5.1f" % v for v in envelope(y))))
    # seed matters for the noise based sounds
    a, b = sfx.RECIPES["explosion"](1, 2.5), sfx.RECIPES["explosion"](2, 2.5)
    check(not np.array_equal(a, b), "explosion: the seed changes nothing")


def main():
    test_catalogue()
    test_sounds("-v" in sys.argv[1:])
    if failures:
        print("FAILED: %d of %d checks\n%s" % (len(failures), checks, "\n".join(failures[:30])))
        sys.exit(1)
    print("OK: %d checks" % checks)


if __name__ == "__main__":
    main()
