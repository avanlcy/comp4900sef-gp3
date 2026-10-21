// Dead Fire - COMP 4900SEF Group 3

#include "Vehicle/DFVehicleMovementComponent.h"
#include "GameFramework/Pawn.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

UDFVehicleMovementComponent::UDFVehicleMovementComponent(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void UDFVehicleMovementComponent::UpdateState(float DeltaTime)
{
	Super::UpdateState(DeltaTime);

	const bool bUnmanned = PawnOwner == nullptr || PawnOwner->GetController() == nullptr;
	if (bUnmanned)
	{
		// Override the stale replicated inputs the base class falls back to.
		SteeringInput = 0.f;
		ThrottleInput = 0.f;
		BrakeInput = 1.f;
		HandbrakeInput = 1.f;
	}
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS
