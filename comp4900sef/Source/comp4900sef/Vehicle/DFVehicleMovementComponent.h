// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "WheeledVehicleMovementComponent4W.h"
#include "DFVehicleMovementComponent.generated.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

/**
 * The Sedan's PhysX movement with one rule on top: a car with no controller is parked.
 * The engine otherwise keeps driving an unmanned car from the last inputs it received,
 * so a player who got out while holding W would watch the car drive away.
 */
UCLASS()
class COMP4900SEF_API UDFVehicleMovementComponent : public UWheeledVehicleMovementComponent4W
{
	GENERATED_BODY()

public:
	UDFVehicleMovementComponent(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void UpdateState(float DeltaTime) override;
};

PRAGMA_ENABLE_DEPRECATION_WARNINGS
