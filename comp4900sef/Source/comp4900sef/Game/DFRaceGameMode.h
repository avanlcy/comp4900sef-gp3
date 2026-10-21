// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "Game/DFRaceGameState.h"
#include "DFRaceGameMode.generated.h"

class ADFCharacter;
class ADFCheckpoint;
class ADFVehiclePawn;
class ADFTrackSpline;
class UDFRacerComponent;

/**
 * Rules of one race: the clock, scoring for laps and kills, deaths and respawns, and the end of the race.
 * Spawns the player's vehicle and stows an on-foot character inside it.
 * Per-level values (time limit, score requirement) are set on the Blueprint child BP_DFRaceGameMode.
 * The class spans two files: the death and respawn functions (NotifyVehicleDestroyed, NotifyCharacterDied,
 * HandleRacerDeath, GetRespawnPoint, SpawnRespawnVehicle, RespawnRacer) are implemented in
 * Game/DFRaceGameModeRespawn.cpp, everything else in Game/DFRaceGameMode.cpp.
 */
UCLASS()
class COMP4900SEF_API ADFRaceGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ADFRaceGameMode();

	/** Class spawned for the player's on-foot character. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Dead Fire|Classes")
	TSubclassOf<ADFCharacter> OnFootCharacterClass;

	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|Race")
	float RaceTimeLimit;

	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|Race")
	float CheckpointTimeBonus;

	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|Race")
	int32 PointsPerLap;

	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|Race")
	int32 PointsPerKill;

	/** The race ends (game over) the moment the player's death count reaches this. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|Race")
	int32 MaxDeaths;

	/** Seconds between a death and the respawn. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|Race")
	float RespawnDelay;

	/** How far (cm) beyond a road's edge a car may go before its off-track timer runs. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|Race")
	float OffTrackMargin;

	/** Seconds a car may stay off every road before it is put back at its last checkpoint (no death counted). */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|Race")
	float OffTrackGraceSeconds;

	/** Score the player needs when time runs out to pass the level. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|Race")
	int32 ScoreRequirement;

	/** Every checkpoint of the level, sorted by CheckpointIndex. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Race")
	TArray<ADFCheckpoint*> Checkpoints;

	/** Every track spline of the level: the main loop and any shortcut roads. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Track")
	TArray<ADFTrackSpline*> Tracks;

	/** The first track with bIsMainTrack set, or null. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Track")
	ADFTrackSpline* MainTrack;

	/** Adds a checkpoint once and keeps Checkpoints sorted by index. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void RegisterCheckpoint(ADFCheckpoint* Checkpoint);

	/**
	 * Registers every checkpoint in the world and collects the track splines. Called from BeginPlay.
	 * Logs a warning for every gate whose CheckpointIndex is not its place in the order (a gap or a repeat).
	 */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void CollectLevelActors();

	UFUNCTION(BlueprintPure, Category = "Dead Fire|Race")
	int32 GetCheckpointCount() const;

	/**
	 * A racer's vehicle reached a checkpoint. While the race runs, only the racer's next gate counts:
	 * the start line (index 0) completes a lap, any other gate advances the racer, and the player
	 * gains CheckpointTimeBonus for both. Returns true when the crossing was credited.
	 */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	bool NotifyCheckpointReached(AController* Racer, ADFCheckpoint* Checkpoint);

	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void AddScore(AController* Racer, int32 Points);

	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void NotifyLapCompleted(AController* Racer);

	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void NotifyCheckpointPassed(AController* Racer);

	/**
	 * Credits the killer and counts the victim's death, then handles that death. A victim already waiting
	 * to respawn loses no second life (the kill still counts). Ignored once the race is over.
	 */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void NotifyVehicleDestroyed(ADFVehiclePawn* Victim, AController* Killer);

	/**
	 * Counts a death for the controller of the killed on-foot character, then handles it, unless that racer
	 * is already waiting to respawn. Ignored once the race is over.
	 */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void NotifyCharacterDied(ADFCharacter* Character);

	/**
	 * Brings the racer back in a car at its last checkpoint (else checkpoint 0, else the player start).
	 * An intact car is moved there and stopped; a wrecked or missing one is replaced by a fresh car.
	 * The player's character is revived if dead, stowed in the car, and the controller drives it.
	 * Does nothing once the race is over.
	 */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void RespawnRacer(AController* Racer);

	/** True within OffTrackMargin beyond the edge of any track (main loop or shortcut road). True in a level without tracks. */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|Track")
	bool IsOnAnyTrack(const FVector& Location) const;

	/**
	 * One frame of one racer, called from Tick for every controller with its pawn. Updates the racer's
	 * progress along the main track and, while it drives an intact car, its off-track timer: after
	 * OffTrackGraceSeconds off every road the racer is put back at its last checkpoint without a death.
	 * On foot, in a wreck or without a pawn the timer is reset. Does nothing once the race is over.
	 */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void TickRacer(AController* Racer, APawn* Pawn, float DeltaSeconds);

	/** All racers (player and NPC) best first: score, then laps, then track distance. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	TArray<UDFRacerComponent*> GetRankedRacers() const;

	/**
	 * Stops the race once: records the player's result on the GameState, cancels pending respawns,
	 * freezes every player's pawn and shows the summary.
	 */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void EndRace(EDFRaceEndReason Reason);

	/** Fired once when the race ends. bPassed is true when time ran out with the player at ScoreRequirement or above. */
	UFUNCTION(BlueprintImplementableEvent, Category = "Dead Fire|Events")
	void OnRaceEnded(bool bPassed);

	/** Fired after a racer was put back in a car. */
	UFUNCTION(BlueprintImplementableEvent, Category = "Dead Fire|Events")
	void OnRacerRespawned(AController* Racer, ADFVehiclePawn* Vehicle);

	virtual void HandleStartingNewPlayer_Implementation(APlayerController* NewPlayer) override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

	ADFRaceGameState* GetRaceState() const;
	void SpawnOnFootCharacterFor(APlayerController* Player);

	/**
	 * After a death has been counted: ends the race when the player has no lives left (MaxDeaths),
	 * otherwise schedules the player's respawn after RespawnDelay. NPC deaths are only counted.
	 */
	void HandleRacerDeath(AController* Racer);

private:
	/** Adds CheckpointTimeBonus to the clock when the racer is the player. */
	void GrantCheckpointTimeBonus(AController* Racer);

	/** True once the race has ended. A GameMode without a race GameState counts as running. */
	bool IsRaceOver() const;

	/** The racer's last checkpoint, else checkpoint 0, else its player start. */
	FTransform GetRespawnPoint(AController* Racer);

	/** A fresh car of DefaultPawnClass at the point, or null when that class is not a Dead Fire vehicle. */
	ADFVehiclePawn* SpawnRespawnVehicle(const FTransform& Point);

	/** Respawn timers still waiting, one per racer. */
	TMap<AController*, FTimerHandle> PendingRespawns;
};
