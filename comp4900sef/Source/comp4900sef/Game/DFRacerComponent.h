// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "DFRacerComponent.generated.h"

class AController;
class ADFCheckpoint;

/**
 * Race progress and score for one racer. Lives on the controller (player or AI)
 * so it survives vehicle respawns and lets the GameMode rank NPCs against the player.
 */
UCLASS(ClassGroup = (DeadFire), meta = (BlueprintSpawnableComponent))
class COMP4900SEF_API UDFRacerComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UDFRacerComponent();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Race")
	FText RacerName;

	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Race")
	int32 Score;

	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Race")
	int32 LapsCompleted;

	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Race")
	int32 Kills;

	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Race")
	int32 Deaths;

	/** Index of the next checkpoint this racer has to pass. Starts at 1: every racer starts on the line (index 0). */
	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Race")
	int32 NextCheckpointIndex;

	/** The last checkpoint credited to this racer, where it respawns. Null before the first one. */
	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Race")
	ADFCheckpoint* LastCheckpoint;

	/** Seconds the racer's car has stayed off every road (off-track timer). */
	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Race")
	float OffTrackSeconds;

	/** World time in seconds when the last checkpoint was credited; -1 before the first one. */
	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Race")
	float LastCheckpointTime;

	/** Progress along the main track in cm, used as a ranking tie-breaker. */
	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Race")
	float DistanceAlongTrack;

	/** The racer component on a controller, or null. */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|Race")
	static UDFRacerComponent* FindOn(AController* Controller);
};
