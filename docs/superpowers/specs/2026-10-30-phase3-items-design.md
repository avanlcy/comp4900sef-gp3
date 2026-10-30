# Dead Fire — Phase 3 (Items & Damage) Design Addendum

Date: 2026-10-30
Extends: `2026-10-20-dead-fire-design.md` (§3 core loop, §4 rules, §6 architecture, §7 phase table) and `2026-10-21-phase2-race-flow-design.md` (race rules, HUD). This document only adds what Phase 3 needs; nothing in the earlier designs changes unless stated.
Status: the project manager asked the agent to continue with the phase plan without a question round, so every decision below that the proposal, flowchart and paper prototype do not settle is an implementer's call, marked **[call]**. The team can overturn any of them in the generator modules (`tools/bpgen/graphs/`) or by changing an Instance Editable value in the level.

## 1. What Phase 3 delivers

Proposal weeks 10–11: "items, inventory, damage, destructible shortcuts". Concretely:

1. **Loot boxes** placed off the road. Only a character **on foot** can collect one; a car driving over it gets nothing. A collected box disappears and comes back later.
2. An **inventory** on the racer (three slots, stackable charges, one selected slot) shown on the HUD, kept across respawns and car changes.
3. **Item use from the car** with one key: **Boost**, **Shield**, **Bomb**, **Gun**, **RPG**. Another key cycles the selected slot.
4. **Explosions** as a shared rule: radial body damage, a blown tire on every car caught in the blast, a physics kick, particle and sound. Bombs, rockets and wrecks all use it.
5. **Vehicle destruction feel**: a wreck explodes, hops, and smokes until it is cleaned up by the respawn.
6. A **destructible rock** that blocks a **shortcut road**, opened only by explosives. The test track gets the shortcut and the rock.
7. Functional tests for every rule, the level builder additions, the new input mapping, README and playtest checklist updates.

Out of scope (later phases): NPC drivers picking up or using items (4; the inventory lives on the racer component precisely so an AI controller can own one), balance passes on damage and charges (6), menus and the vehicle/level unlocks (5), camera shake and screen effects (5; the `OnExplosion` hook is here).

## 2. Items

| Item | What it does from the car | Charges per box | Cap per racer |
|---|---|---|---|
| **Boost** | An instant forward kick of +12 m/s plus 2 s of extra acceleration (25 m/s², mass-independent). | 1 | 3 |
| **Shield** | 6 s during which the car's body and tires ignore all damage. | 1 | 2 |
| **Bomb** | Dropped 4 m behind the car onto the ground. Arms after 1 s, then detonates when any car touches it, or after 8 s, whichever comes first. Explosion: 60 damage, 5 m radius. | 1 | 3 |
| **Gun** | One hitscan shot per press from the front bumper along the car's forward direction: 15 damage, 100 m range, 0.2 s cooldown. | 8 | 24 |
| **RPG** | Fires a rocket forward at 60 m/s (4 s life). On hitting anything it explodes: 80 damage, 6 m radius. | 1 | 2 |

All values are **[call]**; they are Instance Editable on the Blueprint that owns them (§8).

- The proposal's "bomb/trap" is one item, **Bomb**, that works both ways: left on the road it is a trap for 8 s; dropped beside a rock and driven away from, it opens the shortcut. **[call]**
- Picking up a type you already hold adds charges up to the cap; a pickup that would add nothing (full stack, or three other types already held) is **refused and the box stays**. **[call]**
- Using an item consumes one charge of the selected slot; a slot at 0 charges is removed and the selection moves to the first slot. With an empty inventory the use key does nothing.
- Items are used **only from a car being driven** (the use key reaches the possessed pawn). On foot the inventory is still shown and can be cycled, not used. A wrecked car cannot use items.
- Boost and Shield can be stacked in time by using another charge (Boost restarts its 2 s, Shield restarts its 6 s). **[call]**
- Explosive damage can hurt the user's own car (an RPG fired into a wall next to you, your own bomb once armed). A self-kill counts the death but credits no kill (the existing Phase 2 rule: a killer equal to the victim earns nothing). **[call]**
- Kills made with items are credited through the existing damage path (`Instigator` = the controller of the car that used the item), so the Phase 2 kill score (+50) applies unchanged.

## 3. Loot boxes

- `BP_DFLootBox` is an actor with a visible crate (overlap-only: a car drives through it, it is never an obstacle **[call]**) and a sphere trigger. It holds one `ItemType` and a `Charges` count, both Instance Editable so the level designer places specific contents (`Charges` 0, the default, means "that type's box charges" from `GetItemInfo`); with `bRandom` on it rolls a type from Boost..RPG each time it appears. **[call]**
- **Only a `BP_DFCharacter` that is alive, not stowed in a car, and owned by a controller collects it**, on touch (no key press: the Interact key is already "enter vehicle" and the two would conflict next to a parked car). **[call]** The item goes to that controller's racer through the GameMode (`GrantItem`), which logs `DF: pickup <type> x<n> by <racer>` and stamps the racer for the HUD flash.
- After a successful pickup the box hides, stops colliding and comes back after `RespawnSeconds` (30 s **[call]**) unless `bRespawns` is off.
- The test track gets six boxes **[call]**: Boost, Shield, Bomb, Gun, RPG and one random, all at least 15 m from the centre line of every road (beyond the 7 m half-width plus the 5 m off-track margin), three in the infield and three outside the loop, so reaching one on four wheels costs the off-track timer and reaching it on foot is free.
- The test track also gets one **parked, driverless `BP_DFVehicle`** (`TargetCar`) on the infield verge 30 m past the start line, so the destruction items have something to hit in a playtest. It behaves like any other car: it can be entered, wrecking it credits a kill, and its wreck stays until the level reloads. **[call]**

## 4. Inventory (on `BPC_DFRacer`)

- `S_DFItemStack { Type: E_DFItemType, Charges: int }`; `E_DFItemType = { None, Boost, Shield, Bomb, Gun, RPG }`.
- `Inventory: array<S_DFItemStack>` (at most `MaxSlots` = 3 **[call]**), `SelectedSlot: int`.
- `AddItem(Type, Charges) -> bool` (stack or new slot, capped; false when nothing was added), `GetSelected() -> Type, Charges`, `ConsumeSelected() -> Type` (None when empty), `CycleSelected()`, `ClearInventory()`.
- Item names and the per-type charge numbers live in one GameMode function, `GetItemInfo(Type) -> Name, BoxCharges, MaxCharges`, so the loot box, the vehicle and the HUD agree. **[call]**
- `RestartRace` clears the inventory, the active effects of the player's car, and removes every bomb and rocket still in the level (the tests share one play session; a leftover armed bomb must not reach the next test). **[call]** A respawn keeps the inventory (it is on the controller) and clears the effects on the car it puts the player in.

## 5. Explosions (on `BP_DFRaceGameMode`)

`SpawnExplosion(Location, Damage, Radius, InstigatedBy, Causer, bBlowTires)`:

1. Spawns the explosion particle and plays the explosion sound at the location (Starter Content `P_Explosion`, `Explosion_Cue` **[call]**). Phase 3 is the first time a committed Blueprint references the git-ignored Starter Content pack, so the exact assets used and their dependency closure (particles, sounds, shapes, materials, textures) are **force-added to git**; a fresh clone then has them before the pack is re-inserted on first open, and the headless test run never sees a null effect. **[call]**
2. If `Damage > 0`: `ApplyRadialDamage` with the explosive damage type, the instigator's own car excluded from the line-of-sight test (a blast that starts inside your own hull would otherwise shield every other victim) and given its self-damage directly when it is inside the radius, (`BP_DFExplosiveDamage`, a `DamageType` child with no logic), **full damage anywhere inside the radius** (no falloff: one bomb is always one bomb, and a 4 m rock would otherwise be under-damaged by a rocket exploding on its face **[call]**), line of sight checked on the Visibility channel, and `InstigatedBy` as the instigator so kills are credited. Radial damage only reaches *dynamic* objects, so every damageable actor's collision uses a dynamic profile (the rock's mesh is `BlockAllDynamic`).
   **The on-foot character is immune to explosive damage** (`BP_DFCharacter` ignores damage of the explosive type): the base design's anti-goal is that leaving the car must not be a death trap, and a player standing next to their own armed bomb or a Phase 4 rocket should lose a car, not a life. The team can flip this in one branch. **[call]**
3. For every `BP_DFVehicle` within the radius (other than the causer): a radial impulse (velocity change `ExplosionImpulse`, 8 m/s at the origin falling off to the edge **[call]**) and, when `bBlowTires`, `TireBlastDamage` (30 = one blown tire **[call]**) applied to the tire nearest the explosion. This is Phase 3's "tire penalty": a bomb under your car costs a tire as well as body health.
4. Fires `OnExplosion(Location, Radius)`.

A wreck calls it with `Damage = 0` (effects only; wrecks do not chain-react **[call]**), hops with a small upward impulse, and gets a smoke emitter attached until the actor is removed.

## 6. Bomb, rocket, destructible

- `BP_DFBomb`: a dark sphere placed on the ground by a short downward trace from the drop point. Variables `ArmDelay` 1 s, `FuseSeconds` 8 s, `Damage` 60, `Radius` 500, `InstigatorController` (set by the car that drops it). Ticks its two timers; an armed bomb touched by any `BP_DFVehicle` detonates; `Arm()` and `Detonate()` are callable (tests arm it at once). Detonation is once, then the actor is destroyed.
- `BP_DFProjectile`: fired from 3 m ahead of the car's centre, or 25 cm short of whatever already blocks that line (a point-blank shot at a rock explodes on the rock instead of spawning inside it); a small sphere with a `ProjectileMovementComponent` (initial and max speed 6000 cm/s, 5 % gravity, rotation follows velocity, no bounce) and a fire trail. Variables `Damage` 80, `Radius` 600, `LifeSeconds` 4, `InstigatorController`. On BeginPlay it sets its lifespan and ignores its owner (the firing car) when moving; on **Event Hit** it explodes once and destroys itself. It spawns 3 m ahead of the car's centre and 0.8 m up **[call]**.
- `BP_DFDestructible`: a static mesh with collision. Starter Content's `SM_Rock` has no simple collision, so it is a **dark block** (`Shape_Cube` with the committed `BlackGrid` instance; the Starter Content materials and their textures would have added 65 MB to the repository) that the level builder scales to 4 × 16 × 4 m across the road **[call]**; `Health` 60 **[call]**, `bExplosivesOnly` true. On **Event AnyDamage** it ignores damage whose type is not `BP_DFExplosiveDamage` when explosives-only, otherwise loses health; at 0 it plays the explosion effect, hides, stops colliding, fires `OnDestructibleDestroyed` and logs. One RPG or one bomb (adjacent) clears it; the pistol never does.

## 7. Shortcut road

- A level may already contain several `BP_DFTrackSpline` actors (base design §6.3). The test track gets a second one, **`Shortcut`**, `bIsMainTrack` off, an **open** spline (closed loop off) that leaves the main road about 15 m after gate 1 and rejoins about 15 m before gate 2 through one interior point pulled slightly toward the centre of the loop, so it skips no gate; between those junctions the geometry allows about 18 m of saving (a straight chord saves 19 m), and the builder refuses a shortcut that saves less than 10 m. **[call]** Its slab top sits 2 cm below the main road so the junctions do not flicker.
- The rock sits across the shortcut 10 m or more in from its entrance (the builder moves it inward until every corner clears the main road by 2 m), visible from the main road. Driving the shortcut is "on track" for the off-track timer because `IsOnAnyTrack` already checks every track actor.
- `RebuildTrack` owns the loop state (`bClosedTrack`, Instance Editable, default on) and sets it on the spline before measuring, so an open shortcut is laid as one piece per `PieceLength` of its open length; a functional test pins the piece count and the saving.

## 8. Rules summary (tunables; owner in brackets)

| Rule | Value |
|---|---|
| Inventory slots [racer `MaxSlots`] | 3 |
| Box charges / cap: Boost, Shield, Bomb, Gun, RPG [GameMode `GetItemInfo`] | 1/3, 1/2, 1/3, 8/24, 1/2 |
| Loot box respawn [`BP_DFLootBox`] | 30 s |
| Boost kick / acceleration / duration [vehicle] | 1200 cm/s, 2500 cm/s², 2 s |
| Shield duration [vehicle] | 6 s |
| Bomb drop offset / arm delay / fuse / damage / radius | 400 cm, 1 s, 8 s, 60, 500 cm |
| Vehicle gun damage / range / cooldown [vehicle `Weapon`] | 15, 10000 cm, 0.2 s |
| Muzzle offset forward / up [vehicle] | 300 cm, 80 cm |
| Rocket speed / life / damage / radius | 6000 cm/s, 4 s, 80, 600 cm |
| Explosion impulse / tire blast damage [GameMode] | 800 cm/s, 30 |
| Wreck hop impulse [vehicle] | 600 cm/s |
| Destructible health | 60 |
| Pickup flash on the HUD | 1.5 s |

## 9. Input and HUD

- Input: `UseItem` (Q / gamepad X) already exists in `DefaultInput.ini`; add **`NextItem`** = R, mouse wheel up, gamepad D-pad right **[call]**. Both are handled on `BP_DFVehicle`; `NextItem` also on `BP_DFCharacter`.
- HUD additions (`WBP_DFRaceHUD`) **[call]**: an item row at the bottom centre with three slot labels (`BOOST x1`, `SHIELD x2`, `-`), the selected one in amber; above it an effect line (`BOOST`, `SHIELD 4.2`) while an effect runs; below it the hint `[Q] USE   [R] NEXT` while in a car. The warning line gains `PICKED UP SHIELD` for 1.5 s after a pickup, below the checkpoint flash in priority (WRECKED > YOU DIED > RETURN TO TRACK > CHECKPOINT > PICKED UP).

## 10. Hooks left for later phases

- Phase 4: an AI controller with a `BPC_DFRacer` can receive items through `GrantItem` and use them with the vehicle's `UseSelectedItem` / `ApplyItem(Type)`; `FireGun`, `FireRPG`, `DropBomb`, `ActivateBoost`, `ActivateShield` are plain functions on the vehicle.
- Phase 5: `OnExplosion`, `OnItemPickedUp`, `OnDestructibleDestroyed`, `OnLootCollected` for camera shake, sound and UI; the item names come from `GetItemInfo` for menus and tooltips.
- Phase 6: every number in §8 is one default away.

## 11. Phase 3 acceptance

- `tools/run_tests.ps1` green with the new `FT_DF*` tests (inventory stack and cap; loot box on foot only, and respawn; use consumes and refuses when empty; boost kicks the car; shield blocks body and tire damage; armed bomb damages and blows a tire; fuse detonates; rocket explodes on hit and a lethal rocket credits the shooter; gun shot hits the car ahead; destructible is explosives-only and opens; shortcut is an open spline counted as track; restart clears items, effects and leftover bombs; HUD item row shows the inventory). `df_verify_blueprints.py` VERIFY PASSED.
- Playing `L_TestTrack`: six crates visible off the road; a crate collected on foot shows in the HUD row and flashes `PICKED UP ...`; Q uses the selected item from the car, R cycles; the bomb, gun and rocket damage the parked `TargetCar` (§3) and wrecking it scores a kill; a rocket or bomb at the rock opens the shortcut; a wreck explodes and smokes; standing next to a bomb on foot costs no health.

## 12. Left to the builder

Crate, bomb and rocket meshes and materials; particle scales and the smoke emitter choice; exact HUD positions and fonts; log line wording; where the drop trace starts and ends; how the level builder computes the shortcut's interior point and the rock's scale; test world set-up details; the order of the new generator modules.
