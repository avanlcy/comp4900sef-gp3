// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DFCheckpoint.generated.h"

class UBoxComponent;
class UPrimitiveComponent;
class UStaticMeshComponent;
class ADFVehiclePawn;

/**
 * One gate of the race: a box trigger across the road and a pole at each road edge.
 * Index 0 is the start/finish line. A vehicle driving through reports to the GameMode,
 * which decides whether the crossing counts (only the racer's next gate does).
 * Per-level values (extent, pole offset, pole scale) are set on the Blueprint child BP_DFCheckpoint.
 */
UCLASS()
class COMP4900SEF_API ADFCheckpoint : public AActor
{
	GENERATED_BODY()

public:
	ADFCheckpoint();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Checkpoint")
	UBoxComponent* Trigger;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Checkpoint")
	UStaticMeshComponent* LeftPole;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Checkpoint")
	UStaticMeshComponent* RightPole;

	/** Position of this gate in the lap. 0 is the start/finish line. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Checkpoint", meta = (ClampMin = "0"))
	int32 CheckpointIndex;

	/** Half size of the trigger box in cm: X along the road, Y across it, Z up. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Checkpoint")
	FVector TriggerHalfExtent;

	/** Distance in cm from the gate's centre to each pole, along the actor's Y axis. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Checkpoint")
	float PoleOffset;

	/** Relative scale of both poles. The template pole mesh is about 75 cm tall; Z 6 makes the gate visible at speed. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Checkpoint")
	FVector PoleScale;

	/** Height in cm above the gate at which a respawned car is placed. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Checkpoint")
	float RespawnHeightOffset;

	/** Where a racer whose last gate is this one comes back: facing along the road, slightly above it. */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|Checkpoint")
	FTransform GetRespawnTransform() const;

	/**
	 * Reports the vehicle's racer (its controller, or its last driver when parked) to the GameMode.
	 * Returns true when the crossing counted; false when it did not or there is no race GameMode.
	 */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Checkpoint")
	bool NotifyVehicle(ADFVehiclePawn* Vehicle);

	virtual void OnConstruction(const FTransform& Transform) override;

protected:
	virtual void BeginPlay() override;

	UFUNCTION()
	void OnTriggerBeginOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);
};
