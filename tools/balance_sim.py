"""Balance simulation (Phase 6 spec section 3.2): runs a race in the open editor's Simulate mode (NPCs only), samples
every racer, and prints the field's pace, wrecks and the checkpoint time bonus that gives a target race length.

    python tools/balance_sim.py /Game/DeadFire/Maps/L_TestTrack --difficulty 1 --seconds 200 --target-laps 6
    python tools/balance_sim.py /Game/DeadFire/Maps/L_Switchback --target-laps 4 --out docs/superpowers/balance-2026-10-30.md

Needs the editor running with Python remote execution and no play session. The editor side is
comp4900sef/Script/df_balance_sim.py. The difficulty comes from a save in the slot DeadFireBalance; the developer's
DeadFire.sav is not used.

Lap time P is measured from progress, not from lap events: each NPC's DistanceAlongTrack is unwrapped over the
samples (a drop of more than half a lap is a pass of the start line), giving its mean speed along the track; P is
the track length over that speed, and the field's P is the median. Only a player's gates add time and Simulate has
no player, so the race always ends at its clock C; the race length a driver at pace would get is computed:
laps = C / (P - G * bonus), length = laps * P, with G gates.
"""
import argparse
import datetime
import json
import os
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
EDITOR_SCRIPT = os.path.join(REPO, "comp4900sef", "Script", "df_balance_sim.py").replace("\\", "/")
REMOTE = os.path.join(HERE, "ue_remote.py")


def remote(call):
    """Runs one df_balance_sim function in the editor and returns its JSON line as a dict."""
    code = "exec(open(r'%s').read()); %s" % (EDITOR_SCRIPT, call)
    out = subprocess.run([sys.executable, REMOTE, "--code", code], capture_output=True, text=True, timeout=120).stdout
    for line in out.splitlines():
        body = line.split("] ", 1)[1] if line.startswith("[") and "] " in line else line
        if body.startswith("{"):
            return json.loads(body)
    raise SystemExit("no JSON from the editor for %s:\n%s" % (call, out[-1500:]))


def round_half(x):
    return round(x * 2.0) / 2.0


def analyse(samples, track_cm, target_laps=None):
    first, last = samples[0], samples[-1]
    span = last["t"] - first["t"]
    names = sorted({r["name"] for s in samples for r in s["racers"]})
    rows = []
    for name in names:
        series = [(s["t"], r) for s in samples for r in s["racers"] if r["name"] == name]
        if len(series) < 2:
            continue
        travelled, prev = 0.0, series[0][1]["dist"]
        for _, r in series[1:]:
            step = r["dist"] - prev
            if step < -track_cm / 2:
                step += track_cm  # passed the start line
            elif step > track_cm / 2:
                step -= track_cm
            travelled += step
            prev = r["dist"]
        t = series[-1][0] - series[0][0]
        speed = travelled / t if t > 0 else 0.0  # cm/s along the track
        end = series[-1][1]
        rows.append({"name": name, "laps": end["laps"], "kills": end["kills"], "deaths": end["deaths"],
                     "kph": speed * 0.036, "lap_s": track_cm / speed if speed > 0 else float("inf")})
    laps = [r["lap_s"] for r in rows if r["lap_s"] != float("inf")]
    p = statistics.median(laps) if laps else float("inf")
    c, g, bonus_now = first["limit"], first["gates"], first["bonus"]
    minutes = span / 60.0 if span > 0 else 1.0
    wreck_rate = (sum(r["deaths"] for r in rows) / len(rows) / minutes) if rows else 0.0

    def length(bonus):
        drain = p - g * bonus
        return float("inf") if drain <= 0 else c / drain * p

    result = {"npcs": len(rows), "span_s": span, "P": p, "C": c, "G": g, "bonus_now": bonus_now, "length_now": length(bonus_now),
              "wrecks_per_npc_min": wreck_rate, "rows": rows, "npc_scale": first.get("npc_scale"), "item_interval": first.get("item_interval")}
    if target_laps:
        raw = (target_laps * p - c) / (target_laps * g)
        bonus = min(8.0, max(2.0, round_half(raw)))
        result.update({"target_laps": target_laps, "bonus": bonus, "length": length(bonus),
                       "wrecks_per_npc_race": wreck_rate * length(bonus) / 60.0})
    return result


def fmt(x, digits=1):
    return "inf" if x == float("inf") else ("%.*f" % (digits, x))


def report(map_path, difficulty, res, argv):
    lines = ["", "### %s, difficulty %d (%s)" % (map_path.rsplit("/", 1)[1], difficulty, datetime.date.today().isoformat()), "",
             "`python tools/balance_sim.py %s`" % " ".join(argv), "",
             "| NPC | laps | kills | wrecks | mean speed (km/h) | lap time (s) |", "|---|---|---|---|---|---|"]
    for r in res["rows"]:
        lines.append("| %s | %d | %d | %d | %s | %s |" % (r["name"], r["laps"], r["kills"], r["deaths"], fmt(r["kph"]), fmt(r["lap_s"])))
    lines += ["", "- sampled %s s of race time; clock C = %s s; gates G = %d; NPC speed scale %s; NPC item interval %s s"
              % (fmt(res["span_s"], 0), fmt(res["C"], 0), res["G"], res["npc_scale"], res["item_interval"]),
              "- median lap time P = %s s; wrecks %s per NPC per minute" % (fmt(res["P"]), fmt(res["wrecks_per_npc_min"], 2)),
              "- with the current bonus %s s a driver at pace would race %s s" % (fmt(res["bonus_now"]), fmt(res["length_now"], 0))]
    if "bonus" in res:
        lines.append("- for %d laps at pace: bonus %s s per gate, race length %s s, %s wrecks per NPC per race"
                     % (res["target_laps"], fmt(res["bonus"]), fmt(res["length"], 0), fmt(res["wrecks_per_npc_race"], 2)))
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("map")
    ap.add_argument("--difficulty", type=int, default=1)
    ap.add_argument("--seconds", type=float, default=200.0, help="wall-clock limit for the run")
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--target-laps", type=int)
    ap.add_argument("--out")
    args = ap.parse_args()
    if "/Game/" in args.map:
        args.map = args.map[args.map.index("/Game/"):]  # Git Bash rewrites a leading /Game/... into a Windows path

    samples = []
    try:
        start = remote("balance_start(%r, %d)" % (args.map, args.difficulty))
        if "error" in start:
            raise SystemExit("balance_start: " + start["error"])
        deadline = time.time() + args.seconds
        time.sleep(2.0)
        while time.time() < deadline:
            s = remote("balance_sample()")
            if "error" in s:
                raise SystemExit("balance_sample: " + s["error"])
            if not samples and s["slot"] != "DeadFireBalance":
                raise SystemExit("the GameInstance reads slot %r, not DeadFireBalance: the difficulty would not apply" % s["slot"])
            samples.append(s)
            print("t=%6.1f remaining=%6.1f active=%s npcs=%d" % (s["t"], s["remaining"], s["active"], len(s["racers"])), flush=True)
            if not s["active"]:
                break
            time.sleep(args.interval)
    finally:
        stop = remote("balance_stop()")
        print("stopped; overrides now %s" % stop.get("overrides"))
    if len(samples) < 2:
        raise SystemExit("not enough samples")
    res = analyse(samples, start["track_cm"], args.target_laps)
    text = report(args.map, args.difficulty, res, [args.map if "/Game/" in a else a for a in sys.argv[1:]])
    print(text)
    if args.out:
        with open(os.path.join(REPO, args.out) if not os.path.isabs(args.out) else args.out, "a", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
