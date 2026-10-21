// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "VehicleWheel.h"
#include "DFWheelRear.generated.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

/** Driven rear wheel for the Sedan; locked by the handbrake. */
UCLASS()
class COMP4900SEF_API UDFWheelRear : public UVehicleWheel
{
	GENERATED_BODY()

public:
	UDFWheelRear();
};

PRAGMA_ENABLE_DEPRECATION_WARNINGS
