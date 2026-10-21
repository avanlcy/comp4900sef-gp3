// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "DFRaceGameMode.generated.h"

class ADFCharacter;
class ADFVehiclePawn;
class ADFRaceGameState;
class UDFRacerComponent;

/**
 * Rules of one race: the clock, scoring for laps and kills, and the end of the race.
 * Spawns the player's vehicle and stows an on-foot character inside it.
 * Per-level values (time limit, score requirement) are set on the Blueprint child BP_DFRaceGameMode.
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

	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|Race")
	int32 MaxDeaths;

	/** Score the player needs when time runs out to pass the level. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|Race")
	int32 ScoreRequirement;

	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void AddScore(AController* Racer, int32 Points);

	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void NotifyLapCompleted(AController* Racer);

	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void NotifyCheckpointPassed(AController* Racer);

	/** Credits the killer and counts the victim's death. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void NotifyVehicleDestroyed(ADFVehiclePawn* Victim, AController* Killer);

	/** All racers (player and NPC) best first: score, then laps, then track distance. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	TArray<UDFRacerComponent*> GetRankedRacers() const;

	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void EndRace();

	/** Fired once when the clock reaches zero. bPassed is true when the player met ScoreRequirement. */
	UFUNCTION(BlueprintImplementableEvent, Category = "Dead Fire|Events")
	void OnRaceEnded(bool bPassed);

	virtual void HandleStartingNewPlayer_Implementation(APlayerController* NewPlayer) override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

	ADFRaceGameState* GetRaceState() const;
	void SpawnOnFootCharacterFor(APlayerController* Player);
};
