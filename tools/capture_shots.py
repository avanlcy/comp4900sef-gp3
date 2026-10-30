"""Presentation screenshots from the engine (Phase 6): runs the capture "tests" in the open editor and copies their
images to docs/presentation/screenshots/ under descriptive names.

    python tools/capture_shots.py            # all three captures
    python tools/capture_shots.py menu       # one of: menu, race, pause

Every image comes from the engine's own "shot showui" (the game viewport only), never from the screen, and no key or
mouse input is sent. Needs the editor running with Python remote execution, no play session, and no headless test
suite running. For a level's own capture (FT_DFShot_*) the actor is placed in that level for the run and removed
afterwards; FT_DFZZ_Screenshots already lives in the functional-test level.
"""
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
REMOTE = os.path.join(HERE, "ue_remote.py")
LOG = os.path.join(REPO, "comp4900sef", "Saved", "Logs", "comp4900sef.log")
SHOTS = os.path.join(REPO, "comp4900sef", "Saved", "Screenshots", "Windows")
OUT = os.path.join(REPO, "docs", "presentation", "screenshots")

CAPTURES = {
    "menu": ("/Game/DeadFire/Maps/L_MainMenu", "FT_DFShot_Menu", True,
             ["10-menu-main", "11-menu-car-sedan", "12-menu-car-brute-locked", "13-menu-track-proving-ground",
              "14-menu-track-switchback-locked", "15-menu-settings"]),
    "race": ("/Game/DeadFire/Tests/L_DF_FunctionalTests", "FT_DFZZ_Screenshots", False,
             ["20-race-grid", "21-race-rivals", "22-on-foot", "23-summary-unlock"]),
    "pause": ("/Game/DeadFire/Maps/L_TestTrack", "FT_DFShot_Pause", True,
              ["24-race-start-proving-ground", "25-pause-menu"]),
}

EDITOR = r"""
import unreal
ell = unreal.EditorLevelLibrary

def _perf(on):
    p = unreal.get_default_object(unreal.load_class(None, '/Script/UnrealEd.EditorPerformanceSettings'))
    p.set_editor_property('bThrottleCPUWhenNotForeground', bool(on))

def shots_place(map_path, test, place):
    if len(ell.get_pie_worlds(False)) > 0:
        print('SHOTS error: a play session is running'); return
    if not ell.load_level(map_path):
        print('SHOTS error: could not load ' + map_path); return
    _perf(False)
    if place:
        cls = unreal.load_class(None, '/Game/DeadFire/Tests/%s.%s_C' % (test, test))
        a = ell.spawn_actor_from_class(cls, unreal.Vector(0, 0, 200), unreal.Rotator(0, 0, 0))
        a.set_actor_label(test)
        if not ell.save_current_level():
            print('SHOTS error: could not save ' + map_path); return
    print('SHOTS placed')

def shots_end_play():
    if len(ell.get_pie_worlds(False)) > 0:
        ell.editor_end_play()  # takes effect on the next editor tick: the cleanup runs in a later call
    print('SHOTS ending play')

def shots_cleanup(map_path, test, place):
    if len(ell.get_pie_worlds(False)) > 0:
        print('SHOTS error: the play session is still running'); return
    removed, left = 0, []
    if place:
        if not ell.load_level(map_path):
            print('SHOTS error: could not load ' + map_path); return
        for a in ell.get_all_level_actors():
            if isinstance(a, unreal.FunctionalTest):  # a shipped level never keeps a test actor
                ell.destroy_actor(a); removed += 1
        ell.save_current_level()
        left = [a.get_name() for a in ell.get_all_level_actors() if isinstance(a, unreal.FunctionalTest)]
    _perf(True)
    ell.load_level('/Game/DeadFire/Maps/L_TestTrack')
    print('SHOTS cleaned removed=%d left=%s' % (removed, left))
"""


def editor(call):
    code = EDITOR + "\n" + call
    out = subprocess.run([sys.executable, REMOTE, "--code", code], capture_output=True, text=True, timeout=180).stdout
    lines = [l for l in out.splitlines() if "SHOTS" in l]
    return lines[-1] if lines else out[-500:]


def console(cmd):
    subprocess.run([sys.executable, REMOTE, "--console", cmd], capture_output=True, text=True, timeout=60)


def log_size():
    return os.path.getsize(LOG)


def wait_for_result(test, offset, timeout=240):
    pat = re.compile(r"Test Completed\. Result=\{(\w+)\} Name=\{%s\}" % re.escape(test))
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(3)
        with open(LOG, "rb") as f:
            f.seek(offset)
            m = pat.search(f.read().decode("utf-8", "replace"))
        if m:
            return m.group(1)
    return "TIMEOUT"


def capture(key):
    map_path, test, place, names = CAPTURES[key]
    before = set(os.listdir(SHOTS)) if os.path.isdir(SHOTS) else set()
    print("%s: %s" % (key, editor("shots_place(%r, %r, %r)" % (map_path, test, place))))
    offset = log_size()
    console("Automation RunTests Project.Functional Tests.%s.%s" % (map_path, test))
    result = wait_for_result(test, offset)
    time.sleep(2)
    editor("shots_end_play()")
    time.sleep(5)
    cleaned = editor("shots_cleanup(%r, %r, %r)" % (map_path, test, place))
    print("%s: result %s; %s" % (key, result, cleaned))
    if place and "left=[]" not in cleaned:
        raise SystemExit("%s: the capture actor may still be in %s; remove it before packaging" % (key, map_path))
    new = sorted((f for f in os.listdir(SHOTS) if f not in before and f.lower().endswith(".png")),
                 key=lambda f: os.path.getmtime(os.path.join(SHOTS, f)))
    os.makedirs(OUT, exist_ok=True)
    for name, f in zip(names, new):
        shutil.copyfile(os.path.join(SHOTS, f), os.path.join(OUT, name + ".png"))
    print("%s: %d new image(s), copied %d: %s" % (key, len(new), min(len(new), len(names)), ", ".join(names[:len(new)])))
    return result == "Passed" and len(new) >= len(names)


def main():
    keys = sys.argv[1:] or list(CAPTURES)
    ok = all([capture(k) for k in keys])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
