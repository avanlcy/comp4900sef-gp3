"""Balance time-step keeper (Phase 7 Task 23): runs a command, normally tools/balance_sim.py, with the open editor's play
world held at about 1/60 s of game time per frame, then always turns the keeper off.

    python tools/balance_timestep.py -- python tools/balance_sim.py /Game/DeadFire/Maps/L_TestTrack --difficulty 1 --seconds 2700 --target-laps 6
    python tools/balance_timestep.py <log-out> -- python tools/balance_sim.py /Game/DeadFire/Maps/L_Switchback --difficulty 1 --seconds 2700 --target-laps 4

Why: the project substeps physics at 1/60 s with at most 6 substeps, so a frame advances physics by at most 0.1 s. Below
about 10 fps the cars fall behind the game clock that balance_sim measures lap times in, and P comes out too long (a 4 fps
Simulate on SWITCHBACK gave P 98 s; at 60-110 fps it is 41-44 s). A busy machine can drop the editor that low, so the
balance runs of docs/superpowers/balance-2026-10-31.md were all taken through this wrapper.

What: the editor side (comp4900sef/Script/df_balance_timestep.py) sets the play world's time dilation every frame to
(1/60) / (the last real frame time), at most 1. At 60 fps or more it stays 1: the wrapper then changes nothing. Between
runs (no play world) it does nothing. The printed stats give the run's real fps, mean game step and the frames whose game
step went over 2 substeps and over the 0.1 s physics budget (the first frames of a Simulate always do).

<log-out>, if given, receives the editor log written during the command (for respawn counts and the log's frame rate).
Needs the editor running with Python remote execution, as balance_sim does.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE).replace("\\", "/")
REMOTE = os.path.join(HERE, "ue_remote.py")
EDITOR_SCRIPT = REPO + "/comp4900sef/Script/df_balance_timestep.py"
LOG = REPO + "/comp4900sef/Saved/Logs/comp4900sef.log"
TARGET = 1.0 / 60.0


def remote(code):
    out = subprocess.run([sys.executable, REMOTE, "--code", code], capture_output=True, text=True, timeout=120).stdout
    for line in out.splitlines():
        body = line.split("] ", 1)[1] if line.startswith("[") and "] " in line else line
        if body.startswith("{"):
            return json.loads(body)
    raise SystemExit(out[-800:])


def ts(call):
    return remote("exec(open(r'%s').read()); %s" % (EDITOR_SCRIPT, call))


def main():
    if "--" not in sys.argv:
        raise SystemExit(__doc__)
    cmd = sys.argv[sys.argv.index("--") + 1:]
    log_out = sys.argv[1] if sys.argv[1] != "--" else None
    print("keeper", ts("timestep_on(%r)" % TARGET), flush=True)
    try:
        log_start = os.path.getsize(LOG)
        print("running", cmd, flush=True)
        rc = subprocess.run(cmd, cwd=REPO).returncode
        print("command exit", rc, flush=True)
        print("stats", ts("timestep_stats()"), flush=True)
        if log_out:
            with open(LOG, "rb") as f:
                f.seek(log_start)
                text = f.read().decode("utf-8", "replace")
            with open(log_out, "w", encoding="utf-8") as f:
                f.write(text)
            print("log slice", len(text), "bytes ->", log_out, flush=True)
    finally:
        print("keeper off", ts("timestep_off()"), flush=True)


if __name__ == "__main__":
    main()
