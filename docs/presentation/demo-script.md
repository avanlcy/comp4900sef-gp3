# Dead Fire — live demo script

A seven-minute run-of-show on the packaged **Development** build (it keeps the console for the shortcut in step 6). One person drives, one person talks; the talker follows the "Say" column, the driver the "Do" column. Every step has a fallback, so nothing that goes wrong on stage stops the demo.

## Before the demo (10 minutes ahead)

- Unzip `DeadFire-v1.0.0-Win64-Development-<date>-<commit>.zip` on the demo machine and run `comp4900sef.exe` once (the first run may install the UE4 prerequisites and SmartScreen may ask; get that out of the way now).
- Fresh progress: delete `comp4900sef\Saved\SaveGames\DeadFire.sav` beside the exe, or SETTINGS > RESET PROGRESS. The footer must read `CARS 1 / 3   TRACKS 1 / 2`.
- SETTINGS: difficulty NORMAL, master volume about 70 %, then BACK.
- Window: Alt+Enter for fullscreen on the projector (or leave it windowed at 1920×1080 if the projector is unreliable).
- Know the console key: `` ` `` (top-left, below Esc). The command in step 6 is `ke * EndRace 1`.
- Gamepad is optional; the script uses keyboard and mouse: W A S D drive, Space handbrake, E get out / in, Q use item, R next item, P or Escape pause, left mouse fire on foot.
- Have the slides open on the second screen with the demo slide next, and the screenshot slides as the backup if the build will not start.

## Run-of-show

| Time | Do | Say | Point at | If it goes wrong |
|---|---|---|---|---|
| 0:00 | Start on the main menu. | "Dead Fire: an action-racing hybrid. A gang called Fire runs an illegal race; you are the undercover cop climbing its ranks." | The title, the three cars on plinths, the footer `CARS 1 / 3   TRACKS 1 / 2`. | Build will not start: switch to the screenshot slides and narrate the same steps. |
| 0:30 | PLAY. On the car page press `>` twice, then `<` twice. | "Three cars that drive differently. The camera moves to each one; the bars come from the same table that tunes the cars." | The stat bars, BRUTE and VIPER reading `LOCKED - FINISH 1ST ON ...`, NEXT greyed on a locked car. | Camera does not move: carry on, the stats still change. |
| 1:00 | On SEDAN press NEXT. On the track page press `>` once, then `<`. | "Two tracks. Passing a track opens the next; winning it opens that track's car." | `PASS 300   CLOCK 120 s   RIVALS 3`, `NOT RACED YET`, SWITCHBACK locked. | — |
| 1:20 | RACE on PROVING GROUND. | "Every level change fades out and in. Three rivals start on the grid behind us." | The fade; `POS 1 / 4`; the rivals in the mirror (press Tab for the in-car camera and back if time allows). | — |
| 1:40 | Drive the first lap. | "Gates must be taken in order; each one adds time to the clock, a lap scores 100. The race ends when the clock runs out, about three minutes at racing pace." | `CHECKPOINT +N s` and the clock jumping; `LAPS 1`, `SCORE 100`. | Off the road for 5 s: the car is put back at the last gate with no life lost — say so, it is a feature. |
| 2:30 | Stop beside an orange crate in the infield, press E, walk into the crate, walk back, press E. | "Leaving the car matters: items are only picked up on foot." | `PICKED UP <ITEM>`, the item row at the bottom. | Crate already taken (it respawns after 30 s): use another; there are six. |
| 3:00 | Drive to the parked target car near the start; with RPG selected (R cycles) press Q twice. | "Items are used from the car: boost, shield, bomb, gun, rocket. Two rockets wreck a car." | The explosion, hop and smoke; `KILLS 1`, `SCORE +50`. | No rocket in the row: use GUN (Q repeatedly) or a BOMB beside it; or skip to the next step. |
| 3:30 | Optional: fire a rocket at the dark block on the shortcut road just after gate 1, drive through. | "Some of the track is destructible: only explosives open the shortcut." | The block exploding; no `RETURN TO TRACK` on the shortcut. | Out of explosives: point at the block and move on. |
| 3:50 | Press P (or Escape). Then RESUME. | "The world freezes under the pause menu." | `PAUSED`, the four buttons. | — |
| 4:10 | Once `SCORE` is 300 or more and you are 1st, open the console (`` ` ``), type `ke * EndRace 1`, Enter. | "The full race runs about three minutes; for time we end it here." | Summary `RACE COMPLETE`, `Place 1 of 4`, `NEW CAR UNLOCKED: BRUTE   NEXT TRACK UNLOCKED: SWITCHBACK`, RETRY / NEXT / MENU. | Not 1st: the line shows only `NEXT TRACK UNLOCKED`; say the car needs first place. Under 300: keep driving one more lap, or end anyway and show `TIME UP`. |
| 4:40 | NEXT. | "SWITCHBACK: longer, five gates, four rivals, a two-and-a-half-minute clock, and a hairpin the shortcut cuts." | `POS 1 / 5`, the clock at `2:30`. | — |
| 5:10 | P, MAIN MENU. On the car page press `>` to BRUTE, NEXT, RACE on PROVING GROUND. | "Back on the car page, where the flowchart sends you. BRUTE is open now." | BRUTE no longer locked; in the race the grey car, `CAR 160 / 160`, slower off the line and capped at 120 km/h. | — |
| 5:50 | P, MAIN MENU, BACK to the main page, SETTINGS. Move MASTER VOLUME, set difficulty HARD. | "Settings are saved: volume, difficulty — HARD brings five faster, better-armed rivals — and the display mode." | The percentage label, the difficulty hint line. | — |
| 6:30 | BACK, QUIT. | "Every number in the game comes from one table the team tunes, and 78 automated tests guard the rules." | The game closing cleanly. | — |

## After the demo

- SETTINGS > RESET PROGRESS (or delete the save) so the next run starts locked again.
- If anything misbehaved, the Development build's log is `comp4900sef\Saved\Logs\comp4900sef.log`; keep it for the bug list.
