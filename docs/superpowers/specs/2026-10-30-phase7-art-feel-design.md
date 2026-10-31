# Dead Fire Phase 7 — Own Look, Own Feel (design)

Date: 2026-10-30
Status: written at the project manager's request ("plan all the above"; the question round was skipped). Every open decision is an implementer's **[call]**; the team can overturn any of them. Plan: `docs/superpowers/plans/2026-10-30-phase7-art-feel.md`.
Revised 2026-10-31 (the project manager's decisions): Blender 5.2.3 LTS at `C:\Program Files\Blender Foundation\Blender 5.2`; the live Blender MCP is used for previewing and inspecting models (§4.7); downloads from Poly Haven are allowed where needed (§4.6).
Builds on: `2026-10-20-dead-fire-design.md` (§2 non-goal "Final art. Grey-box and engine template assets are acceptable until polish": this phase is that polish) and the Phase 3–6 specs.

---

## 1. Why

The project manager's description of the game as it plays: no custom assets, stock UE4-template driving, no items or shooting, stock textures, no custom terrain.

What the project contains (checked 2026-10-30, commit `617e940`):

- **Items and shooting exist** (Phase 3, covered by the 78 functional tests): crates, a three-slot inventory, Boost / Shield / Bomb / Gun / RPG used from the car, on-foot hitscan, explosions, the destructible rock, AI item use. **Nothing a player perceives says so:**
  - The car's gun shot has no visual and no sound (`BPC_DFWeapon` on the car: `bDebugTrace False`, nothing else).
  - The on-foot shot draws a debug line. The character holds no weapon, and the crosshair is a `+` text.
  - Crates are 80 cm Starter Content cubes at least 15 m off the road, with no marker, so a driver never sees one.
  - The HUD item row is text. Explosions and wreck smoke are Starter Content particles. The bomb is a red sphere; the rocket is a sphere with `P_Fire`.
- **Driving** is the Sedan template's `WheeledVehicleMovement` plus only a throttle scale and speed limiter; the camera is the template SpringArm.
- **World**: a 500 m grey cube with VehicleAdv's `LandscapeNoHole` as the ground, the road is the engine cube with `BlackGrid`, VehicleAdv arena ramps and poles, StarterContent shapes for items.

So the work is: make the existing mechanics visible, audible and felt; give the cars their own handling; replace every visible stock asset with Dead Fire's own; build terrain.

## 2. Goals, non-goals, anti-goals

**Goals**
- **G1** Driving that is Dead Fire's own: arcade assists (speed-sensitive steering, grip assist, handbrake drift with a drift boost, downforce, air control, reset), a chase camera that sells speed, engine and tyre sound.
- **G2** Items and shooting that a first-time player notices: every shot shows a muzzle flash, a tracer and an impact, and makes a sound; crates are visible from the road; the HUD shows item icons; explosions, boost and shield have their own effects.
- **G3** Every asset a player sees or hears in a shipped level is made or chosen for Dead Fire: cars, character gear, weapons, items, props, road, gates, terrain, textures, materials, effects, sounds, HUD art. Our scripts generate them, except where a generated one does not hold up and a CC0 Poly Haven asset replaces it (§4.6). Allowed stock exceptions are in §4.4.
- **G4** Custom terrain for both tracks and the menu, with dressing, dusk lighting and post-processing.
- **G5** Nothing regresses: the 78 functional tests stay green (the few whose visual contract moved are updated, §9), balance is re-measured, the packaged build ships and holds 60 fps.

**Non-goals** **[call]**
- A custom character body or animations. The UE4 mannequin skeleton and animations stay; the character gets Dead Fire materials and attached gear (helmet, vest, rifle). Rigging and animating a new body is beyond scripted modelling and the schedule.
- Particle systems (Cascade / Niagara). UE 4.27 Python cannot author them; effects are meshes and materials driven by Blueprints (§7.1).
- Music.
- New items, weapons, game modes, tracks or rules. Drift boost and car reset are handling features, not items.
- Changing track layouts: road shapes, gates, crates and the shortcut stay where `LAYOUTS` puts them.
- Photorealism.

**Anti-goals**
- Driving that feels worse than today: more flips, twitchier, slower to recover.
- Art that hurts readability. Crates, gates, rivals, shots and items must be easier to spot than in grey-box.
- Broken tests, or AI pace changed without re-balancing.
- A packaged Development build below 60 fps average at 1920×1080 on the dev PC with 3 rivals.
- A pipeline only the agent can run. Every generator has one documented command, and teammates can use the committed imported assets without Blender.

## 3. Art direction **[call]**

**Dusk in a burnt-out wasteland.** Chunky low-poly shapes (bevelled, readable silhouettes) with textured PBR surfaces; a warm low sun and orange haze; ash-grey and umber ground, rust, scorched concrete.

| Role | Colour |
|---|---|
| Player car (undercover cop), SEDAN paint | navy `#1B2A4A`, white trim `#E6E6E6`, blue light bar |
| BRUTE / VIPER paint | gunmetal `#3C4148` / teal `#149E9E`, white trim |
| Fire syndicate rivals | black `#151515`, flame-orange trim `#FF5A1F` |
| Boost / Shield / Bomb / Gun / RPG / random crate | `#00D9FF` / `#3DFF7A` / `#FF3030` / `#FFD21F` / `#FF7A1A` / `#D24BFF` |
| Gates | flame orange; the player's next gate bright, the others dim |
| Ground | ash `#4A4540`, umber dirt `#6B5440`, dry grass `#8A7A4E`, rock `#5E5A55`, sand `#B49A72` |
| Sky / fog | sun `#FFB27A`, fog inscattering `#C8693A` |

Item colours are used on the crate stripe, its icon and beacon, the HUD slot and the loot burst.

UI typeface: **Russo One** (SIL OFL) **[call]**; its licence is committed beside it. The only other third-party assets allowed are CC0 Poly Haven assets under §4.6. The wordmark "DEAD FIRE 死火" is rendered to an image.

## 4. Production pipeline **[call]**

### 4.1 Tools
- **`tools/artgen/`** (Python 3.11 with numpy 1.24 and Pillow 9.3, already installed) generates textures, normal maps, icons, the logo, heightmaps, splat maps and sounds (numpy synthesis), plus the catalogue. Everything is deterministic from seeds.
- **Blender 5.2 LTS** (supported until July 2028), installed at `C:\Program Files\Blender Foundation\Blender 5.2` (5.2.3) (the `DF_BLENDER` environment variable overrides it; not in the repo). One script per mesh under `tools/artgen/blender/meshes/`, run headless by `tools/artgen/build_meshes.py`, exported as FBX with a JSON stats file per mesh.
- **Editor side** (`comp4900sef/Script/`):
  - `df_import_art.py`: imports and reimports textures, meshes and sounds, assigns materials, applies settings.
  - `df_build_materials.py`: master materials through `MaterialEditingLibrary`, instances from the catalogue.
  - `df_verify_art.py`: catalogue against assets, budgets, texture settings, and an audit of stock references.
  - `df_export_dims.py` and `df_export_tracks.py`: measurements the generators need.
- **DF Blueprint Authoring plugin** gains `SetComponentSocket`, `CreateLandscapeFromRaw` and `SetFontFace`.
- **Blender MCP** ("MCP for Blender" add-on in the person's open Blender, 127.0.0.1:9876; Claude Code server `uvx mcp-for-blender`): the live preview and inspection loop for models and the Poly Haven search (§4.6, §4.7).
- **`tools/artgen/polyhaven.py`**: downloads pinned Poly Haven assets through the public API (§4.6).

### 4.2 Catalogue
`tools/artgen/catalog.py` is the single list of every Dead Fire art asset: name, kind, recipe, seed, size or budget, material slots, import settings. `build_all.py` writes `art/catalog.json` for the editor scripts.

### 4.3 Where things live
- Generator sources are committed.
- Generated files go under `art/` (git-ignored, rebuilt by `python -I tools/artgen/build_all.py`).
- Imported assets go under `/Game/DeadFire/Art/{Textures,Materials,Meshes,Sounds,UI,Fx,Terrain}` and are committed; teammates without Blender use them as they are.
- Name prefixes: `T_DF_`, `M_DF_`, `MI_DF_`, `SM_DF_`, `SW_DF_`, `SA_DF_`, `F_DF_`; Blueprints `BP_DFFx*`, `BP_DFShake*`, `BP_DFScatter`, `BP_DFDebris`. Poly Haven assets take the same `DF` names; their origin is recorded in the catalogue, not in the name.
- Third-party records (committed): `tools/artgen/THIRD_PARTY.md` lists every third-party asset (name, source URL, licence, author, date fetched) and is generated by `build_all.py`; `tools/artgen/polyhaven.lock.json` pins each downloaded file's URL and SHA-256.

### 4.4 Allowed stock
These form the physics and animation backbone; the player never sees them as stock art:
- The Sedan skeletal mesh, physics asset, anim Blueprint and wheel Blueprints (hidden, §6.1).
- The mannequin mesh, skeleton and animations (with new materials, §6.2).
- Engine content under `/Engine` used for function, not looks.
- The functional-test level (not shipped).

No shipped map or `/Game/DeadFire` asset references `/Game/StarterContent`, `/Game/VehicleAdv`, `/Game/Geometry` or `/Game/Vehicle/Meshes`. The stock audit (§9) enforces this.

### 4.5 Budgets
| Asset | Budget |
|---|---|
| Car body | ≤ 8,000 triangles |
| Wheel | ≤ 1,000 |
| Gear or weapon | ≤ 2,000 |
| Prop | ≤ 3,000 |
| Rock | ≤ 1,500 |
| Effect shell | ≤ 500 |
| Textures | 1024² (icons 256², splat 1024², logo 1024×256) |
| New content in `/Game/DeadFire/Art` | ≤ 250 MB on disk |

Poly Haven assets follow the same budgets: textures at 1k (2k only for the four terrain sets and asphalt), and models decimated to budget.

### 4.6 Poly Haven ("if necessary")
The project manager allowed downloads from Poly Haven where needed (2026-10-31). Every Poly Haven asset is CC0 and needs no attribution. Poly Haven's API terms ask for an identifying User-Agent, and the credit line in the README is a courtesy.
- **When:** only for natural or photographic surfaces and natural scatter props. Surfaces: asphalt, concrete, dirt, ash ground, dry grass, rock, sand, rust and painted metal, wood. Props: rocks, dead trees, debris. Only after the generated version fails the look-dev review (§9 visual review), with the reason recorded in the catalogue entry.
  - Never for the cars, character gear, weapons, items, gates, the road mesh, UI, effects or sounds. Their shapes are tied to gameplay dimensions and the art direction.
- **How:**
  1. Find candidates with the MCP `search_assets` (source `polyhaven`) and preview them in the live Blender (`import_asset` onto a test plane or into the preview scene, then `look`).
  2. Pin the chosen slug and resolution in the catalogue (`source="polyhaven:<slug>"`).
  3. Download it with `tools/artgen/polyhaven.py` (API `https://api.polyhaven.com/files/<slug>`, User-Agent `DeadFire-artgen/1.0 (COMP4900SEF Group 3)`). The MCP import is only a preview; the build always uses the scripted download.
- **Texture maps:** `Diffuse` → `_BC`, `nor_dx` → `_N`, `arm` (AO, roughness, metal) → `_ORM`, all as PNG at the pinned resolution.
- **Models** (gltf) are imported, decimated to the §4.5 budget, given our material slots and exported by a headless Blender script, just like the generated meshes. They must pass the same mesh checks.
- **Not used:** Sketchfab, Poly Pizza, and the add-on's AI generators (`generate_3d`). They are off in the add-on, and anything not CC0 is refused.

### 4.7 Live Blender (MCP)
- **Builds stay headless.** Every FBX that reaches Unreal is built by `tools/artgen/build_meshes.py` running Blender in the background (`--factory-startup`) from a committed script. So any teammate can rebuild without the MCP, and the person's open Blender never affects a build.
- **The MCP is the review loop.** Before a mesh is called done, the implementer builds it into the live Blender through `execute_blender_code`, in a scene of its own named `DF_Preview`. It then looks at it with `look` (mode `angles`, plus the viewport) and fixes the script until it reads right. `get_scene_info` checks dimensions and counts.
- **Safety rules for the person's session:**
  - Work only in the `DF_Preview` scene.
  - Never save or close their file, and never delete outside `DF_Preview`.
  - Clear `DF_Preview` before each build.
  - Switch the window back to the scene they were on when done.
- **Fallback:** when the MCP is not connected (Blender closed, or the session did not connect), `tools/artgen/blender/preview.py` renders the same four views headless (Workbench) to `art/previews/`, and the implementer reads those images instead.

## 5. Driving **[call]**

### 5.1 How
An arcade layer sits on top of the template's `WheeledVehicleMovement` in `BP_DFVehicle`. Its physics assists (grip, downforce, stability, drift, air) apply every tick to player and AI cars alike, so the AI keeps racing on equal terms. Steering smoothing and speed scaling apply to the player's input only, because the AI controller already computes its own steering **[call]**. Forces and torques use `AddForce` / `AddTorqueInDegrees` with `bAccelChange` (mass-independent). The template movement (engine, gears, suspension, wheels) stays. Per-car values are new `VEHICLES` columns.

### 5.2 Rules
| Assist | Rule | SEDAN / BRUTE / VIPER |
|---|---|---|
| Steering smoothing | the applied steer moves toward the input at `SteerRiseRate` 4 /s when moving away from 0 and `SteerReturnRate` 7 /s when moving toward 0 or across it | same |
| Speed-sensitive steering | applied steer × lerp(1, `SteerAtSpeed`, clamp(speed / 150 km/h)) | 0.45 / 0.50 / 0.38 |
| Grip assist | grounded: lateral acceleration = −lateral speed × `GripAssist` (1/s); × `DriftGrip` 0.3 while drifting | 3.0 / 3.5 / 2.5 |
| Downforce | grounded: downward acceleration = `DownforceG` × 980 × (speed / 100 km/h)² cm/s², capped at 1960 | 0.25 / 0.20 / 0.35 |
| Stability | grounded, \|steer\| < 0.1, not drifting: yaw acceleration = −yaw rate × 2.0 /s | same |
| Centre of mass | Z offset −25 cm, set at BeginPlay | same |
| Drift | **starts** with handbrake + \|steer\| ≥ 0.3 + speed ≥ 40 km/h + grounded; yaw acceleration = steer × 120 deg/s²; **ends** when the handbrake is released, speed < 25 km/h, or airborne | same |
| Drift boost | a drift of at least 1.0 s that ends by releasing the handbrake gives one forward velocity change of 500 cm/s; the HUD flashes DRIFT | same |
| Air control | airborne > 0.25 s: pitch and roll rates damped at 1.5 /s; levelling acceleration 180 deg/s² × (up × world up); throttle pitches and steer rolls at 90 deg/s² | same |
| Grounded | a line trace 150 cm down from the actor origin hits | — |
| Reset | action `ResetCar` (Backspace, gamepad face-right). Below 15 km/h, with a 3 s cooldown: the car is lifted 150 cm, pitch and roll zeroed, velocities zeroed. No death, no position gain. | — |

### 5.3 Camera
- Chase FOV 90 + 15 × clamp(speed / 160 km/h), interpolated at 4 /s, +8 while boosting.
- SpringArm camera lag speed 10, rotation lag speed 8.
- `LookBack` (C, right-stick click) shows the rear view while held.
- Camera shakes:
  - `BP_DFShakeLight`: landing after more than 0.5 s airborne, a crash, a tyre pop, a hit taken.
  - `BP_DFShakeHeavy`: an explosion within 25 m, scaled by distance.
- On foot nothing changes except the shake on hits.

### 5.4 Sound
- `EngineAudio` plays a per-car loop (`SW_DF_EngineSedan` / `Brute` / `Viper`). Pitch = 0.6 + 1.4 × RPM / MaxRPM; volume = 0.35 + 0.65 × |throttle|.
- `SkidAudio` volume = clamp((|lateral speed| − 300) / 700) while grounded.
- `SW_DF_Crash` plays on hits whose normal impulse is above `CrashImpulse` (set from the first logged run), with a 0.5 s cooldown.

### 5.5 Tyre smoke
`BP_DFFxPuff` spawns at both rear wheels every 0.08 s while drifting or while |lateral speed| > 500 cm/s.

### 5.6 Unchanged
Top speed (within ±5 % of the measured Phase 6 value, per car), throttle scale, the speed limiter, boost and shield rules, tyre-blow rules, enter/exit speed.

### 5.7 AI
The layer applies to AI cars, so `bAIHandbrake` can make an AI car drift. That is acceptable if the AI suite stays green and the balance re-run (§10) shows pace within 5 %. Otherwise drift is skipped for `bAIControlled` cars (decided in plan Task 9).

**Decided in plan Task 9 (2026-10-31): drift stays on for AI cars.** No `FT_DFAI_*` test failed with the layer on (all 16 green in the 89-test suite), and the AI cannot start a drift: it applies the handbrake only to park, with steering 0, below the drift rule's |steer| ≥ 0.3. The §10 balance re-run (7F) still checks the pace; if it moves more than 5 %, add `NOT bAIControlled` to the drift start rule then.

## 6. Cars, character, weapons

### 6.1 Cars **[call]**
Physics stays on the template Sedan skeletal mesh. It is hidden: `Visible` false, with `VisibilityBasedAnimTickOption` set to `AlwaysTickPoseAndRefreshBones` so the wheel bones keep turning. The visuals are static meshes attached to it:
- `Body` on the Mesh component.
- `WheelFL` / `WheelFR` / `WheelRL` / `WheelRR` at sockets named after the wheel bones (`Wheel_Front_Left`, …).
- `LightBar` (SEDAN only), `RoofWeapon`, `ShieldBubble`, and `BoostFlameL` / `BoostFlameR` at the exhaust sockets.

Why: wheel bones, tyre-by-bone hits, the physics asset, the exit spots and every test keep working, and three distinct bodies need no rigging.

**Bodies** are built to the Sedan's measured dimensions, exported to `tools/artgen/data/dims.json`: wheel-arch centres within 2 cm of the wheel bones, and the body within the physics asset's box plus 15 cm.
- `SM_DF_Car_Sedan`: an "interceptor", four doors, push bar, light bar.
- `SM_DF_Car_Brute`: an armoured pickup with plates, roll cage and bull bar; taller.
- `SM_DF_Car_Viper`: a low wedge with a rear wing.
- Material slots: 0 Paint, 1 Trim, 2 Glass, 3 Dark (grilles, undertray), 4 Lights (emissive).
- Sockets: `Roof`, `Muzzle`, `Exhaust_L`, `Exhaust_R`.

**Wheels**: `SM_DF_Wheel` (tyre and rim; radius and width from the wheel classes) and `SM_DF_WheelRim` (rim only, shown when that tyre is blown). The right-side wheels are yawed 180°.

**Paint**:
- `PaintMaterial` now goes on `Body` slot `PaintSlot`, which defaults to 0.
- Each car has a default paint: `MI_DF_Paint_Sedan` / `Brute` / `Viper`.
- NPCs get `MI_DF_Paint_Gang` from `SpawnNPCs`.
- A wreck swaps slots 0 and 1 to `MI_DF_Paint_Charred`.

**RoofWeapon**: shows `SM_DF_RoofGun` while the racer holds a Gun and `SM_DF_RoofLauncher` while it holds an RPG (RPG wins when both are held); hidden otherwise. Its `Muzzle` socket is where tracers and rockets visually start; the gameplay origin `GetMuzzleLocation` is unchanged.

### 6.2 Character
- The mannequin's two slots get `MI_DF_Mannequin_Body` (navy) and `MI_DF_Mannequin_Trim` (grey).
- Gear: `SM_DF_Helmet` on `head`, `SM_DF_Vest` on `spine_03`, `SM_DF_Rifle` on `hand_r`. The rifle has a `Muzzle` socket.
- Shots still trace from the camera (rules unchanged). The tracer starts at the rifle muzzle, and `bDebugTrace` is off.

## 7. Items and shooting feedback

### 7.1 Effects **[call]**
`BP_DFFx` is a short-lived actor. Its static mesh components tagged `FxShell` grow from `StartScale` to `EndScale` and fade: the material parameter `Fade` goes from 1 to 0, raised to `FadeExponent`. An optional point light `Flash` fades with them. The actor destroys itself after `Lifetime`.

| Child | Lifetime | Used for |
|---|---|---|
| `BP_DFFxMuzzle` | 0.06 s | every shot |
| `BP_DFFxTracer` | 0.08 s | every hitscan shot; `SetEnds(Start, End)` |
| `BP_DFFxImpact` | 0.3 s | hitscan hits (sparks on vehicles, dust otherwise) |
| `BP_DFFxExplosion` | 1.2 s | `SpawnExplosion` (replaces `P_Explosion`) |
| `BP_DFFxPuff` | 1.2 s | rocket trail, tyre smoke, wreck smoke (replaces `P_Smoke`) |
| `BP_DFFxLootBurst` | 0.6 s | crate opened; tinted with the item colour |
| `BP_DFFxSparks` | 0.25 s | tyre pop, car-on-car crashes |

Long-lived effects are components instead: boost flames, the shield bubble (fresnel; flashes on a blocked hit), rocket exhaust (replaces `P_Fire`), wreck fire on the body, and the crate beacon.

### 7.2 Weapons
- On every `Fire`, `BPC_DFWeapon` itself spawns the muzzle flash, tracer and impact and plays its fire and impact sounds.
- New variables on it: `MuzzleFxClass`, `TracerFxClass`, `ImpactFxClass`, `FireSound`, `ImpactSound`, and `VisualOrigin` (a scene component; the tracer starts there, else at the trace origin).
- The car's weapon: `SW_DF_CarGun`, with `VisualOrigin` = `RoofWeapon`.
- The character's weapon: `SW_DF_Rifle`, with `VisualOrigin` = `Rifle`.
- The on-foot crosshair becomes an image. It turns red and grows for 0.15 s on a hit (the hit marker).

### 7.3 Explosions
- `BP_DFFxExplosion` with `SW_DF_Explosion`.
- A scorch decal (`M_DF_Scorch`, 4 m) that fades over 20 s.
- `BP_DFShakeHeavy` for the player, through `PlayWorldCameraShake` with inner radius 5 m and outer radius 25 m.

### 7.4 Crates (`BP_DFLootBox`)
- Meshes: `SM_DF_Crate` with `SM_DF_CrateLid`. An emissive stripe takes the item colour (the stripe slot's dynamic material parameter `EmissiveColor`).
- A floating icon above the crate: a material billboard with `T_DF_Icon_<Item>`, bobbing 20 cm on a 2 s period.
- A beacon pillar 30 m tall in the item colour, visible from the road. It is additive and fades out within 10 m so it does not clutter close up.
- All of it hides while the crate is collected and returns on `Reset`.
- On `Pickup`: the lid pops off, `BP_DFFxLootBurst` spawns, and `SW_DF_LootOpen` plays (`SW_DF_Deny` when the pickup is refused).
- While driving below exit speed within 40 m of an uncollected crate, the HUD prompt reads `CRATE NEARBY - E TO GET OUT`.

### 7.5 Items on the car
| Item | Visual | Sound |
|---|---|---|
| Boost | exhaust flames, FOV kick | `SW_DF_Boost` |
| Shield | shield bubble | `SW_DF_ShieldUp` / `Hit` / `Down` |
| Bomb | `SM_DF_Bomb` with a light that blinks faster as the fuse runs (1 Hz → 6 Hz) | `SW_DF_BombArm`; `SW_DF_BombBeep` on each blink |
| Rocket | `SM_DF_Rocket`, exhaust flame, `BP_DFFxPuff` every 0.05 s | `SW_DF_RocketLaunch` / `SW_DF_RocketLoop` |
| Tyre pop | rim swap, `BP_DFFxSparks` | `SW_DF_TirePop` |

### 7.6 HUD and menus
- The item row shows three icon slots (`T_DF_Icon_*`); the selected slot is framed and the charges show as a number.
- The crosshair is an image.
- A damage vignette shows for 0.3 s when the player's car or character takes damage, and a DRIFT flash on a drift boost.
- `F_DF_Display` (Russo One) is used everywhere, and the main menu shows the wordmark `T_DF_Logo`.
- Buttons play `SW_DF_UIHover` and `SW_DF_UIClick`.
- The player hears `SW_DF_Checkpoint` at gates and `SW_DF_Lap` on each lap.

## 8. Terrain and environment

### 8.1 Terrain **[call]**
- One Landscape per shipped track: 1009 × 1009 vertices at 100 cm (1008 m square; 8 × 8 components of 2 × 2 sections of 63 quads), centred on the track's bounding box, Z scale 100.
- Heights come from `tools/artgen/terrain.py`, using the track's real spline samples exported from the built level (`tools/artgen/data/tracks/<Map>.json`). Let *d* be the distance to the nearest road centre line (main loop or shortcut):
  - *d* ≤ 9 m: −8 cm, just under the road tops (0 and −2 cm).
  - 9–25 m: smoothstep blend into the field.
  - The field is fBm with amplitude 0.5 m up to 60 m from the road, rising smoothly to 6 m at 150 m and 40 m at 300 m.
  - Within 150 m of the landscape edge, a ridge ring rises to 120 m. It closes the horizon and keeps cars in.
  - Pads are flattened to −8 cm: 6 m around crates and the target car, 12 m around gates and props.
- Splat map, 1024² RGBA:
  - R: dirt (road shoulders at *d* ≤ 14 m, and pads).
  - G: ash and dry grass.
  - B: rock (slope > 28°, or height > 30 m).
  - A: sand (noise patches in low ground).
- `M_DF_Terrain` blends four texture sets by the splat map, with a large-scale tint variation. Each track has one instance carrying its splat map and origin.
- `L_MainMenu` reuses the PROVING GROUND terrain, positioned so the plinths sit on flat ground.
- `L_DF_FunctionalTests` keeps its flat Ground cube **[call]**: the test level is not shipped, and its tests should not depend on art.

### 8.2 Track dressing
- **Road**: `SM_DF_RoadSlab`, which keeps the cube's 100 cm unit contract. UVs: U runs along the segment, V across it. `M_DF_Road` has asphalt in world UVs, white edge lines, a dashed centre line (4 dashes per segment) and red-and-white kerb bands at the edges.
- **Barriers**: `SM_DF_Barrier`, a concrete jersey barrier. Barriers stay off by default.
- **Gates**: two `SM_DF_GatePylon` with an `SM_DF_GateBanner` across them. Their glow follows the highlight: `BP_DFCheckpoint.SetHighlighted`, driven by the GameMode's `RefreshGateHighlights`.
- **Ramps and wedges**: `SM_DF_Ramp` and `SM_DF_BumpWedge` match the VehicleAdv originals' bounds within ±2 cm, so the layout and the AI are unchanged.
- **Destructible rock**: `SM_DF_RockWall` (unit contract). It breaks into 8 `BP_DFDebris` chunks (`SM_DF_RockChunk`, physics, 8 s life).

### 8.3 Scatter **[call]**
`BP_DFScatter` is one actor per mesh: a hierarchical instanced static mesh rebuilt in the construction script from an editable `Transforms` array, with a `bBlocking` flag. The level builder places instances with seeded Poisson-disc sampling:
- Minimum distance from any road centre line:
  - ≥ 10 m: debris, no collision.
  - ≥ 14 m: rocks, barrels, tyre stacks, wrecks; blocking.
  - ≥ 25 m: dead trees, containers, billboards, light towers.
- ≥ 10 m from crates, gates, props and the target car.
- Nothing in the start box (60 m past the start line, ±20 m to either side).
- Density rises with distance from the road; at most 500 instances per map.

Meshes: `SM_DF_Rock01`–`04`, `SM_DF_DeadTree01`–`02`, `SM_DF_CarWreck`, `SM_DF_Barrel`, `SM_DF_TyreStack`, `SM_DF_Container`, `SM_DF_ScrapFence`, `SM_DF_Billboard` (Fire syndicate tag), `SM_DF_LightTower` (emissive lamps, no light), `SM_DF_Debris01`–`02`.

### 8.4 Light and post **[call]**
These are starting values in a `LIGHTING` dict in the level builder, tuned on screenshots:
- Sun: pitch −14°, yaw 30°, colour `#FFB27A`, intensity starting from today's builder value.
- Sky light with real-time capture.
- Height fog: density 0.02, inscattering `#C8693A`.
- An unbound PostProcessVolume: bloom 0.8, auto-exposure brightness min 1 / max 1.5, vignette 0.4, saturation 1.05, white balance 5800 K.

### 8.5 Menu
Plinths become `SM_DF_Plinth` turntables, on the terrain, with a few props and the same light preset.

## 9. Tests and checks

- **Updated tests** (their visual contract moved): the `tests_menu.py` paint checks read `Body` instead of `Mesh`; `FT_DFHUD_ItemRowShowsInventory` checks icons instead of text. Every other existing test is unchanged.
- **New functional tests**: `FT_DFDrive_*`, `FT_DFArt_*`, `FT_DFFx_*`, plus new `FT_DFLoot_*`, `FT_DFItem_*`, `FT_DFHUD_*`, `FT_DFCheckpoint_*`, `FT_DFDestructible_*` and `FT_DFScatter_*` (listed in the plan).
- **Offline tests**, run as `python -I tools/artgen/test_*.py`: textures seamless and deterministic, normal maps valid, sounds within peak and length with seamless loops, terrain rules, catalogue consistency, and the mesh stats each Blender run writes (budget, bounds, sockets, slots).
- **Editor check** `ART VERIFY`: catalogue against assets, budgets, texture compression and sRGB, sound looping and attenuation, and the **stock audit** (shipped maps and `/Game/DeadFire` must not reference the stock folders in §4.4).
- **Third-party check**: every catalogue entry with a `polyhaven:` source has a `THIRD_PARTY.md` line and lock entries whose SHA-256 matches the files in `art/`; no other third-party source exists apart from the font.
- **Visual review**:
  - Each mesh is looked at in the live Blender (§4.7) before it is exported.
  - Engine screenshots of a look-dev level and of each map are looked at before a task is called done.
  - A generated surface that fails this review may be replaced under §4.6.
- **Performance**: packaged Development build, PROVING GROUND with 3 rivals, CSV profiler over 1800 frames. The average frame must be ≤ 16.7 ms and the 95th percentile ≤ 20 ms.

## 10. Balance
Handling changes move lap times. After 7E, re-run `tools/balance_sim.py` on both tracks. If the measured NPC lap time moved more than 5 % from `docs/superpowers/balance-2026-10-30.md`, update the `LEVELS` bonus with the Phase 6 formula and write `docs/superpowers/balance-<date>.md`.

## 11. Order
Sub-phases, in order:
1. **7A** pipeline and look-dev.
2. **7B** driving.
3. **7C** cars, character, weapons.
4. **7D** items and shooting feedback.
5. **7E** terrain and environment.
6. **7F** balance and ship.

7B needs only 7A's sounds and could run alongside 7C. Each sub-phase ends with every functional test green.

If time runs short, cut from the end of the list below. Never cut crate visibility, shot feedback, the driving layer or the terrain under the tracks; those are what the project manager named.
1. Scatter density and menu dressing.
2. Scorch decals and crash sounds.
3. The drift boost.

## 12. Acceptance
- `ART VERIFY PASSED` including `STOCK AUDIT PASSED`; every functional test passes (78 plus the new ones); every offline test passes.
- Screenshots reviewed: PROVING GROUND, SWITCHBACK, the menu, a crate, a gunfight, an explosion, a drift.
- Packaged Development and Shipping builds smoke-tested, and the performance target met.
- Phase 7 lines added to `docs/superpowers/playtest-checklist.md` for what tests cannot press: drift feel, camera, readability at speed.

## 13. Risks
| Risk | Mitigation |
|---|---|
| Blender FBX axis or scale errors | the 7A orientation fixture and bounds checks |
| A hidden skeletal mesh stops updating its bones | `AlwaysTickPoseAndRefreshBones`; `FT_DFArt_WheelsFollowBones` checks it while driving |
| `ALandscape::Import` from a plugin | tested on a 64 × 64 landscape before real use |
| Python material authoring is verbose | only nine master materials |
| Procedural sounds can sound synthetic | each sound keeps its asset name, so a recorded file can replace it later with no code change |
| Setting a font face from Python | the plugin's `SetFontFace` |
| The Blender MCP is not connected when a mesh needs review | the headless preview renders (§4.7 fallback) |
| The agent damages the person's open Blender work | §4.7 rules: only the `DF_Preview` scene, never save or close |
| A Poly Haven file changes upstream | the lock file's SHA-256 fails the third-party check, and the file is re-reviewed before the lock is updated |
| Add-on telemetry | the person decides whether to call `disable_telemetry` (asked in Task 1) |
| Uncommitted editor changes to `BP_DFLootBox`, `L_TestTrack` and `WBP_DFRaceHUD` in the working tree (2026-10-30) | the next apply or level rebuild overwrites them; the project manager decides before 7A starts |
