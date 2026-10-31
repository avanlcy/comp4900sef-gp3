"""Online check of the Poly Haven downloader: three 1k maps, a lock entry per file, a tampered lock refused, User-Agent sent.
Downloads into a temporary folder with a temporary lock; never touches art/ or the committed lock (plan Task 2).

    python -I tools/artgen/test_polyhaven.py
"""
import hashlib
import json
import os
import sys
import tempfile
import urllib.request

import numpy as np
from PIL import Image as PILImage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from artgen import polyhaven  # noqa: E402

checks = 0
failures = []


def check(ok, msg):
    global checks
    checks += 1
    if not ok:
        failures.append(msg)


def main():
    seen = []
    real = urllib.request.urlopen

    def spy(req, *a, **k):
        seen.append((req.full_url, req.get_header("User-agent")))
        return real(req, *a, **k)
    urllib.request.urlopen = spy
    try:
        check(polyhaven.USER_AGENT == "DeadFire-artgen/1.0 (COMP4900SEF Group 3)", "USER_AGENT %r" % polyhaven.USER_AGENT)
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "lock.json")
            out = os.path.join(tmp, "out")
            files = polyhaven.fetch_texture("asphalt_02", "1k", out, "Probe", lock_path=lock)
            names = sorted(os.path.basename(f) for f in files)
            check(names == ["T_DF_Probe_BC.png", "T_DF_Probe_N.png", "T_DF_Probe_ORM.png"], "files %s" % names)
            for f in files:
                check(os.path.exists(f) and np.asarray(PILImage.open(f)).shape[:2] == (1024, 1024), "%s is not 1024 x 1024" % f)
            data = json.load(open(lock, encoding="utf-8"))
            check(len(data) == 3, "lock has %d entries" % len(data))
            for k, v in data.items():
                check(v.get("slug") == "asphalt_02" and v.get("url", "").startswith("https://") and len(v.get("sha256", "")) == 64,
                      "lock entry %s: %s" % (k, v))
            by_name = {os.path.basename(k): v for k, v in data.items()}
            for f in files:  # written at 8 bits per channel, and sha256_art is the written file
                raw = open(f, "rb").read()
                check(polyhaven.png_bit_depth(raw) == 8, "%s is %s-bit" % (os.path.basename(f), polyhaven.png_bit_depth(raw)))
                entry = by_name.get(os.path.basename(f), {})
                check(entry.get("sha256_art") == hashlib.sha256(raw).hexdigest(), "%s: sha256_art does not match the file" % os.path.basename(f))
            again = polyhaven.fetch_texture("asphalt_02", "1k", out, "Probe", lock_path=lock)
            check(len(again) == 3, "re-fetch with a matching lock must succeed")
            key = sorted(data)[0]
            data[key]["sha256"] = "0" * 64
            with open(lock, "w", encoding="utf-8") as f:
                json.dump(data, f)
            try:
                polyhaven.fetch_texture("asphalt_02", "1k", out, "Probe", lock_path=lock)
                check(False, "a tampered lock hash must raise RuntimeError")
            except RuntimeError:
                check(True, "")
            info = polyhaven.info("asphalt_02")
            check("name" in info and "authors" in info, "info keys %s" % sorted(info))
    finally:
        urllib.request.urlopen = real
    check(len(seen) >= 8, "only %d requests were seen" % len(seen))
    check(all(ua == polyhaven.USER_AGENT for _, ua in seen), "a request lacked the User-Agent: %s" % [s for s in seen if s[1] != polyhaven.USER_AGENT][:3])
    if failures:
        for f in failures:
            print("FAIL: " + f)
        print("%d of %d checks failed" % (len(failures), checks))
        sys.exit(1)
    print("OK: %d checks, %d requests" % (checks, len(seen)))


if __name__ == "__main__":
    main()
