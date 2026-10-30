# Dead Fire — final presentation outline

Fifteen slides, about twelve minutes plus the live demo (`demo-script.md`, seven minutes, after slide 9). The structure follows the proposal's sections, then what was built, how it was tested and shipped, and what was learned. Images are in `screenshots/`; numbers come from `docs/superpowers/balance-2026-10-30.md` and the Phase 6 build. The draft deck of these slides is a Claude Slides artifact owned by the project manager, https://claude.ai/artifact/CEdogffpwcYHuZFU7Sup8S (private until shared from its Share menu; it downloads as .pptx or PDF for the team to restyle).

---

### 1. Dead Fire (死火)
- Action racing with third-person shooting, built in Unreal Engine 4.27
- COMP 4900SEF, Group 3
- Lau Chun Kit · Chong Tsz Ho · Fung Ming Chu · Choy Tsz Lok · Lee Chun Yin · Cheung Tsz Hin Anderson

Image: `01-main-menu-packaged.png`

Notes: "This is the packaged game, running without the editor. Everything you see today is in the build we are handing in."

### 2. The pitch
- A gang called Fire runs an illegal race to show off its power; you are the undercover cop climbing its ranks
- Race laps, blow up rival cars, and get out of the car to find items the track hides
- Our selling point from the proposal: checkpoint scoring + item-based interference + leaving the car to explore

Image: `21-race-rivals.png`

Notes: Keep it to the three ideas; the demo shows each one.

### 3. What we built on
- Super Mario Kart (1992): items that add uncertainty to racing
- GTA Online race mode: get out of the car to grab power-ups and weapons
- Blur (2010): hardcore combat racing (82 Metascore)
- The genre is alive: Mario Kart 8 Deluxe has sold 71.53 million copies
- Our twist: the best items are off the road and only reachable on foot

Notes: Sources as in the proposal (shmuplations 2016, Gallegos 2012, Metacritic 2010, Nintendo 2026).

### 4. The core loop
- Main menu → choose a car (stats) → choose a track → race → summary
- During the race: gates in order add time, a lap scores 100, wrecking a rival scores 50, three lives
- Passing a track opens the next one; winning it opens that track's car; then back to the car page
- Exactly the flowchart in the proposal

Image: `23-summary-unlock.png`

Notes: Point at `NEW CAR UNLOCKED: BRUTE   NEXT TRACK UNLOCKED: SWITCHBACK`: that line is the flowchart's unlock rule.

### 5. Race rules
- Clock 120 s (PROVING GROUND) / 150 s (SWITCHBACK); every gate adds 3 s / 2 s
- Score 300 / 400 to pass; +100 per lap, +50 per wreck
- Three lives; a wreck or a death respawns you at your last gate after 2 s
- Off the road for 5 s: put back on track with no life lost
- Every rival has the same rules: its own laps, kills, deaths and respawns; live place `POS 2 / 4`

Image: `20-race-grid.png`

### 6. Leaving the car
- Six loot crates per track, off the road: only collected on foot
- Three inventory slots, used from the car: boost, shield, bomb, gun, rocket
- Explosions damage everything in range, blow the nearest tire, and shove the cars
- A rock only explosives can clear hides a shortcut road
- On foot: walk, jump, shoot; get back in with E

Image: `22-on-foot.png`

### 7. The rivals
- Drive the track's spline on their own lanes; slow for corners; overtake around cars and obstacles
- Reverse out when stuck, reset when flipped, respawn at their last gate when wrecked
- Handed an item every 20 s; use it with simple rules: shield when hurt, rocket or gun at a car ahead (the player first), bomb for a car behind, boost on a straight
- Difficulty: EASY 2 slower rivals, NORMAL 3, HARD 5 faster, better armed

Image: `24-race-start-proving-ground.png`

### 8. Menus, cars and progress
- Three cars that drive differently: SEDAN (balanced), BRUTE (160 armour, capped at 120 km/h, heavy), VIPER (fragile, fastest, longer boost)
- Two tracks; progress saved: unlocks, best score and place per track, settings
- Pause menu (Escape), settings (volume, difficulty, fullscreen, reset), a fade on every level change

Images: `12-menu-car-brute-locked.png`, `14-menu-track-switchback-locked.png`, `15-menu-settings.png`, `25-pause-menu.png`

### 9. SWITCHBACK
- The second track: 787 m, five gates, four rivals, 2:30 on the clock
- An S-bend you must brake for, and a hairpin the shortcut cuts behind its rock

Image: `31-switchback-top.png`

Notes: Then switch to the live demo.

### 10. How it is built
- Blueprint-only, on the engine's Vehicle and Third Person templates, as the proposal planned
- Every Blueprint graph is generated from Python (`tools/bpgen`): 30 game Blueprints and widgets, 5 data types and 81 test assets, reviewable as code and rebuilt identically
- An editor plugin we wrote applies them, checks every node and link, compiles and saves
- Generated graphs are laid out for reading: titled sections, one row per branch, notes on the decisions

Image: `30-generated-graph-bomb.png`

Notes: "The bomb's whole behaviour fits on one screen; every section title is a sentence."

### 11. How it is tested
- 78 automated functional tests run headless in about five minutes: race rules, items, AI, menus, progress, and the ship fixes
- Tests use their own GameMode and their own save slot, so a test run never touches your progress
- A playtest checklist covers what tests cannot press: driving feel, cameras, menus
- The packaging script smoke-tests every build: the game starts, reaches the menu, logs no script errors

Notes: Mention that every bug fixed in the final week was first reproduced by a failing test or by the balance runs.

### 12. Balance with evidence
- Problem: with 8 s per gate, a lap at the rivals' pace earned back almost all of its time: a race never ended
- A simulation runs the rivals for a whole race and measures their pace (PROVING GROUND about 32-35 s a lap, SWITCHBACK 46-56 s)
- From that, 3 s per gate on PROVING GROUND and 2 s on SWITCHBACK: about 3 minutes of racing at the rivals' pace
- Measured wreck rate at NORMAL stays under one per rival per race

Notes: The table in `docs/superpowers/balance-2026-10-30.md` has every run.

### 13. Shipping
- One command builds, smoke-tests and zips the game: `tools/package_game.ps1`
- Packaged Windows build: about 320 MB, 185 MB zipped; Development (console and log) and Shipping
- Final-week fixes: race end with the pause menu up, volume saved on release, no errors when a race level closes, a clean first run, no "lighting needs rebuild" banner, a clean cook

Image: `01-main-menu-packaged.png` (small)

### 14. Challenges and what we learned
- From the proposal's list: vehicle physics tuning, AI that drives and fights, scope control, tire damage, item and score balance
- Driving AI on a shared spline made rivals possible in one week
- Generated Blueprints avoided binary merge conflicts in a six-person team
- Balance needs numbers: the clock problem only showed up when we measured it

### 15. Thank you
- Questions?
- Next steps we would take: art and audio passes (the menu music actor is waiting for a track), a third track (one row in the track table), tuning HARD from real playtests

---

## Images

| File | Shows |
|---|---|
| `01-main-menu-packaged.png` | the packaged game's main menu |
| `10-menu-main.png` | the main menu (editor play, fresh progress) |
| `11-menu-car-sedan.png`, `12-menu-car-brute-locked.png` | the car page |
| `13-menu-track-proving-ground.png`, `14-menu-track-switchback-locked.png` | the track page |
| `15-menu-settings.png` | settings |
| `20-race-grid.png`, `21-race-rivals.png` | the race HUD with the item row; rivals ahead |
| `22-on-foot.png` | on foot beside the car |
| `23-summary-unlock.png` | the summary with the unlock line |
| `24-race-start-proving-ground.png`, `25-pause-menu.png` | a race with three rivals; the pause menu |
| `30-generated-graph-bomb.png` | a generated Blueprint graph |
| `31-switchback-top.png` | SWITCHBACK from above |

Recapture with `python tools/capture_shots.py` (editor open, no tests running); every image comes from the engine's own screenshot of the game view.
