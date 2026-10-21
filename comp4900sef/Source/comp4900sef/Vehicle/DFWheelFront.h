// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "VehicleWheel.h"
#include "DFWheelFront.generated.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

/** Steering wheel for the Sedan. Tunables live on the Blueprint child of the vehicle. */
UCLASS()
class COMP4900SEF_API UDFWheelFront : public UVehicleWheel
{
	GENERATED_BODY()

public:
	UDFWheelFront();
};

PRAGMA_ENABLE_DEPRECATION_WARNINGS
