"""Presentation screenshots from the engine (Phase 6): runs the capture "tests" in the open editor and copies their
images to docs/presentation/screenshots/ under descriptive names.

    python tools/capture_shots.py            # the six presentation captures (menu, race, pause, switchback, switchback-top, drift)
    python tools/capture_shots.py menu       # one of: menu, race, pause, switchback, switchback-top, drift, lookdev, fx, combat,
                                             # scorch-lookdev, scorch-test, track, points-proving, points-switchback,
                                             # combat-proving, fx-proving

Phase 7 Task 24: every presentation capture runs in a shipped level, so the deck shows the game's terrain and light. race takes
the HUD on the grid, the rivals ahead, on foot, the summary's unlock line and the item looks in L_TestTrack (FT_DFShot_Race);
FT_DFZZ_Screenshots still takes the same images in the functional-test level when run by hand. switchback-top takes SWITCHBACK
from straight above (FT_DFShot_Top). drift (fix round 1) takes the player's car mid-drift with its tyre smoke (FT_DFShot_Drift).

lookdev (Phase 7) is a development capture, not a presentation one: it takes one image per LookDevShot camera of
/Game/DeadFire/Art/L_DF_LookDev (build it first: df_build_test_track.py main(maps=[LOOKDEV_MAP])) and writes them to
art/lookdev/lookdev-NN.png (git-ignored), replacing the previous set. fx (Phase 7 Task 15) takes each BP_DFFx effect at
mid-life in the same level and writes art/lookdev/fx-N-<effect>.png. combat (Phase 7 Task 16) takes the car's gun shot, a rocket
in flight, an explosion and its scorch in the functional-test level (the race GameMode runs them) and writes
art/lookdev/combat-N-<name>.png; there the cleanup removes only its own actor, never the level's tests. points-proving and
points-switchback (Phase 7 Task 22) take a shipped track from the race (the grid, four fixed points along the road, the item looks
and the player on foot) and write art/lookdev/points-<pg|sb>-NN-<name>.png.

Every image comes from the engine's own "shot showui" (the game viewport only), never from the screen, and no key or
mouse input is sent. Phase 7 Task 18: "shot showui" in the new PIE window that "Automation RunTests" opens also takes that
window's Slate frame; each copied image has the frame cropped off (unframe) and must come out 1280 x 720.
Needs the editor running with Python remote execution, no play session, and no headless test
suite running. Each capture actor (FT_DFShot_*) is placed in its level for the run and removed afterwards, and the level is
saved both times.
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
LOOKDEV_OUT = os.path.join(REPO, "art", "lookdev")
# shots.py POINTS_SHOTS (Task 22): the grid, the four fixed road points, the item looks (ITEM_SHOTS), on foot
POINT_NAMES = ["grid", "point-1", "point-2", "point-3", "point-4", "crate-road-40m", "crate-close", "bomb", "shield", "boost", "on-foot"]

CAPTURES = {
    "menu": ("/Game/DeadFire/Maps/L_MainMenu", "FT_DFShot_Menu", True,
             ["10-menu-main", "11-menu-car-sedan", "12-menu-car-brute-locked", "13-menu-track-proving-ground",
              "14-menu-track-switchback-locked", "15-menu-settings"]),
    # Phase 7 Task 24: on PROVING GROUND itself (shots.py race_capture), no longer in the functional-test level
    "race": ("/Game/DeadFire/Maps/L_TestTrack", "FT_DFShot_Race", True,
             ["20-race-grid", "21-race-rivals", "22-on-foot", "23-summary-unlock",
              # Phase 7 Task 17: the item looks (shots.py ITEM_SHOTS, in that order)
              "26-crate-road-40m", "27-crate-close", "28-bomb", "29-shield", "30-boost"]),
    "pause": ("/Game/DeadFire/Maps/L_TestTrack", "FT_DFShot_Pause", True,
              ["24-race-start-proving-ground", "25-pause-menu"]),
    "lookdev": ("/Game/DeadFire/Art/L_DF_LookDev", "FT_DFShot_LookDev", True, None),  # names: one per camera
    # Phase 7 Task 15: each BP_DFFx effect at mid-life (shots.py FX_SHOTS, in that order), also to art/lookdev/
    "fx": ("/Game/DeadFire/Art/L_DF_LookDev", "FT_DFShot_Fx", True,
           ["fx-0-muzzle", "fx-1-tracer", "fx-2-impact", "fx-3-explosion", "fx-4-puff", "fx-5-lootburst", "fx-6-sparks"]),
    # Phase 7 Task 16: shots, rocket, explosion and scorch through their real paths (shots.py COMBAT_SHOTS), also to art/lookdev/
    "combat": ("/Game/DeadFire/Tests/L_DF_FunctionalTests", "FT_DFShot_Combat", True,
               ["combat-0-gunshot", "combat-1-rocket", "combat-2-explosion", "combat-3-scorch"]),
    # Task 16 fix round 1: one scorch decal, lit and in four G-buffer views (shots.py SCORCH_VIEWS), on each level's floor
    "scorch-lookdev": ("/Game/DeadFire/Art/L_DF_LookDev", "FT_DFShot_Scorch", True,
                       ["scorch-lookdev-%d-%s" % (i, v) for i, v in enumerate(["lit", "basecolor", "specular", "roughness", "metallic"])]),
    "scorch-test": ("/Game/DeadFire/Tests/L_DF_FunctionalTests", "FT_DFShot_Scorch", True,
                    ["scorch-test-%d-%s" % (i, v) for i, v in enumerate(["lit", "basecolor", "specular", "roughness", "metallic"])]),
    # Phase 7 Task 21: gate 1 lit and gate 2 dim after a restart, the shortcut's rock whole, breaking and broken (shots.py
    # TRACK_SHOTS, in that order), also to art/lookdev/
    "track": ("/Game/DeadFire/Tests/L_DF_FunctionalTests", "FT_DFShot_Track", True,
              ["track-%d-%s" % (i, v) for i, v in enumerate(["gate-next", "gate-dim", "rock", "rock-broken", "rock-settled"])]),
    # Phase 7 Task 22: the second track's race start and pause menu, as "pause" takes them on PROVING GROUND
    "switchback": ("/Game/DeadFire/Maps/L_Switchback", "FT_DFShot_Pause", True,
                   ["32-race-start-switchback", "33-pause-switchback"]),
    # Phase 7 Task 24: SWITCHBACK from straight above (shots.py top_capture)
    "switchback-top": ("/Game/DeadFire/Maps/L_Switchback", "FT_DFShot_Top", True, ["31-switchback-top"]),
    # Task 24 fix round 1 (spec §12 "a drift"): the player's car mid-drift on PROVING GROUND, from the chase camera with the HUD
    # and from beside the road (shots.py drift_capture)
    "drift": ("/Game/DeadFire/Maps/L_TestTrack", "FT_DFShot_Drift", True, ["34-drift-chase", "35-drift"]),
    # Phase 7 Task 22: each shipped track's terrain, scatter and light from the race (shots.py POINTS_SHOTS, in that order), also to
    # art/lookdev/: the grid, four fixed points along the main road, the item looks and the player on foot
    "points-proving": ("/Game/DeadFire/Maps/L_TestTrack", "FT_DFShot_Points", True, ["points-pg-%02d-%s" % (i, v) for i, v in enumerate(POINT_NAMES)]),
    "points-switchback": ("/Game/DeadFire/Maps/L_Switchback", "FT_DFShot_Points", True, ["points-sb-%02d-%s" % (i, v) for i, v in enumerate(POINT_NAMES)]),
    # Phase 7 Task 22: "combat" on PROVING GROUND's terrain and light (the shipped level runs the race GameMode too), also to art/lookdev/
    "combat-proving": ("/Game/DeadFire/Maps/L_TestTrack", "FT_DFShot_Combat", True,
                       ["combat-pg-0-gunshot", "combat-pg-1-rocket", "combat-pg-2-explosion", "combat-pg-3-scorch"]),
    # Task 22 fix round 1: "fx" on PROVING GROUND's ground and light (FX_SPOT is open terrain there, about 26 cm above the effects'
    # Z 0), also to art/lookdev/
    "fx-proving": ("/Game/DeadFire/Maps/L_TestTrack", "FT_DFShot_Fx", True,
                   ["fx-pg-0-muzzle", "fx-pg-1-tracer", "fx-pg-2-impact", "fx-pg-3-explosion", "fx-pg-4-puff", "fx-pg-5-lootburst",
                    "fx-pg-6-sparks"]),
}
DEFAULT_KEYS = ["menu", "race", "pause", "switchback", "switchback-top", "drift"]
# Phase 7 Task 18 fix round 1: "Automation RunTests" plays in a new window (UEditorEngine::AutomationLoadMap requests a play
# session with no destination viewport), and UEditorEngine::GeneratePIEViewportWindow draws that window's border and title bar
# in Slate (an OS border only for VR preview), so "shot showui", which takes the whole window, includes them: 1290 x 754 for the
# 1280 x 720 viewport. Measured on the 2026-10-31 captures (10-menu-main, 20-race-grid, 22-on-foot, 25-pause-menu): columns 0-4
# and 1285-1289 and rows 0-28 and 749-753 are the frame, the viewport is x 5-1284, y 29-748. The border columns and rows and the
# title bar's last two rows (the window icon reaches row 26) are neutral dark grey, values 21-38. A plain "shot" (the dev
# captures) is already the bare viewport.
VIEWPORT = (1280, 720)
FRAME = (5, 29, 5, 5)  # left, top, right, bottom (px)
FRAME_GREY = (16, 44)   # the frame strips' grey values (measured 21-38), with margin; R = G = B within FRAME_SPREAD
FRAME_SPREAD = 2


def unframe(path):
    """Crops the PIE window frame off a "shot showui" capture in place, after checking that the strips it removes are the
    frame's neutral dark grey, and asserts the image is the 1280 x 720 viewport."""
    from PIL import Image
    im = Image.open(path)
    framed = (VIEWPORT[0] + FRAME[0] + FRAME[2], VIEWPORT[1] + FRAME[1] + FRAME[3])
    if im.size == framed:
        rgb = im.convert("RGB")
        w, h = im.size
        top, bottom = FRAME[1], h - FRAME[3]
        pts = ([(x, y) for x in list(range(1, FRAME[0])) + list(range(w - FRAME[2], w - 1)) for y in range(top, bottom)]
               + [(x, y) for y in list(range(top - 2, top)) + list(range(bottom, h - 1)) for x in range(FRAME[0], w - FRAME[2])])
        for p in pts:
            c = rgb.getpixel(p)
            if max(c) - min(c) > FRAME_SPREAD or not FRAME_GREY[0] <= c[0] <= FRAME_GREY[1]:
                raise SystemExit("%s: pixel %s is %s, not the window frame's grey; not cropping" % (path, p, c))
        im = im.crop((FRAME[0], FRAME[1], FRAME[0] + VIEWPORT[0], FRAME[1] + VIEWPORT[1]))
        im.save(path)
    if im.size != VIEWPORT:
        raise SystemExit("%s is %d x %d, not the %d x %d viewport" % ((path,) + im.size + VIEWPORT))


DEV_KEYS = ("lookdev", "fx", "combat", "scorch-lookdev", "scorch-test", "track", "points-proving", "points-switchback",
            "combat-proving", "fx-proving")  # development captures: art/lookdev/, never the presentation folder

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
    cams = [a for a in ell.get_all_level_actors() if isinstance(a, unreal.CameraActor) and any(str(t).startswith('LookDevShot') for t in a.tags)]
    print('SHOTS placed cameras=%d' % len(cams))

def shots_end_play():
    if len(ell.get_pie_worlds(False)) > 0:
        ell.editor_end_play()  # takes effect on the next editor tick: the cleanup runs in a later call
    print('SHOTS ending play')

def _capture_actors(map_path, test):
    # what the cleanup removes: every test actor from a shipped level (it never keeps one); from the functional-test level
    # only the capture's own actor (its tests stay)
    keep_tests = map_path.endswith('/L_DF_FunctionalTests')
    return [a for a in ell.get_all_level_actors() if isinstance(a, unreal.FunctionalTest)
            and (not keep_tests or a.get_class().get_name() == test + '_C')]

def shots_cleanup(map_path, test, place):
    if len(ell.get_pie_worlds(False)) > 0:
        print('SHOTS error: the play session is still running'); return
    removed, left = 0, []
    if place:
        if not ell.load_level(map_path):
            print('SHOTS error: could not load ' + map_path); return
        for a in _capture_actors(map_path, test):
            ell.destroy_actor(a); removed += 1
        ell.save_current_level()
        left = [a.get_name() for a in _capture_actors(map_path, test)]
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
    placed = editor("shots_place(%r, %r, %r)" % (map_path, test, place))
    print("%s: %s" % (key, placed))
    out_dir = LOOKDEV_OUT if key in DEV_KEYS else OUT  # development captures stay out of the presentation
    if names is None:  # lookdev: one image per tagged camera
        m = re.search(r"cameras=(\d+)", placed)
        names = ["lookdev-%02d" % i for i in range(int(m.group(1)) if m else 0)]
        out_dir = LOOKDEV_OUT
        if os.path.isdir(out_dir):
            for f in os.listdir(out_dir):
                if f.startswith("lookdev-") and f.endswith(".png"):
                    os.remove(os.path.join(out_dir, f))
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
    os.makedirs(out_dir, exist_ok=True)
    for name, f in zip(names, new):
        shutil.copyfile(os.path.join(SHOTS, f), os.path.join(out_dir, name + ".png"))
        unframe(os.path.join(out_dir, name + ".png"))
    print("%s: %d new image(s), copied %d to %s: %s" % (key, len(new), min(len(new), len(names)), out_dir, ", ".join(names[:len(new)])))
    return result == "Passed" and len(names) > 0 and len(new) >= len(names)


def main():
    keys = sys.argv[1:] or DEFAULT_KEYS
    ok = all([capture(k) for k in keys])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
