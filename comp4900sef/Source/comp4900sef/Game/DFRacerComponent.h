// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "DFRacerComponent.generated.h"

class AController;

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

	/** Index of the next checkpoint this racer has to pass (Phase 2). */
	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Race")
	int32 NextCheckpointIndex;

	/** Progress along the main track in cm, used as a ranking tie-breaker. */
	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Race")
	float DistanceAlongTrack;

	/** The racer component on a controller, or null. */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|Race")
	static UDFRacerComponent* FindOn(AController* Controller);
};
