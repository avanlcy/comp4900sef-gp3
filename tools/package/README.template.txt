DEAD FIRE  (死火)   v{{VERSION}}
{{CONFIG}} build, made {{DATE}} from commit {{COMMIT}}
COMP 4900SEF, Group 3

An action-racing hybrid: race laps, blow up rival cars, and get out of the car on foot
to find items and shortcuts.


HOW TO RUN
----------
1. Unzip the whole folder anywhere (keep the files together).
2. Double-click comp4900sef.exe.
   The first run may install the Unreal Engine 4 prerequisites (Visual C++ runtime);
   allow it. Windows SmartScreen may warn that the app is unrecognised: the build is
   not code-signed. Choose "More info" then "Run anyway".
3. The game starts in the main menu: PLAY, choose a car, choose a track, RACE.

Alt+Enter or F11 toggles fullscreen; SETTINGS also has a display button.


CONTROLS
--------
Action                            Keyboard / mouse        Gamepad
Drive / move                      W A S D, arrows         Left stick, triggers
Handbrake (car) / Jump (on foot)  Space                   Left shoulder / A
Enter / exit vehicle              E                       Y
Fire                              Left mouse              Right trigger
Use selected item (in the car)    Q                       X
Next item                         R, mouse wheel up       D-pad right
Switch camera (car)               Tab                     View
Pause menu                        Escape or P             Menu
Look                              Mouse                   Right stick


HOW A RACE WORKS
----------------
Pass the gates in order: each one adds time to the clock; crossing the start line after
the others completes a lap (+100). Wrecking a rival scores +50. Three lives. When the
clock runs out, reach the track's score to pass it. Passing a track opens the next one;
passing it in first place opens that track's car. Loot crates off the road can only be
picked up on foot (stop, press E, walk into the crate).


SAVED PROGRESS
--------------
Unlocks, best scores and settings are saved next to the game in
  comp4900sef\Saved\SaveGames\DeadFire.sav
Delete that file (or use SETTINGS > RESET PROGRESS) to start over.


KNOWN ISSUES
------------
- The program is named comp4900sef.exe (the project's internal name); the window title
  is "Dead Fire".
- There is no menu music yet.
- Grey-box art: engine template cars, characters and shapes.


TEAM
----
Lee Chun Yin (project manager, integration), Choy Tsz Lok, Fung Ming Chu, Chong Tsz Ho,
Cheung Tsz Hin Anderson, Lau Chun Kit.
