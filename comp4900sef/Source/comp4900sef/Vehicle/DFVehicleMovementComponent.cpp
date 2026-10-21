// Dead Fire - COMP 4900SEF Group 3

#include "Vehicle/DFVehicleMovementComponent.h"
#include "Vehicle/DFVehiclePawn.h"
#include "GameFramework/Pawn.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

UDFVehicleMovementComponent::UDFVehicleMovementComponent(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

float UDFVehicleMovementComponent::GetThrottleInput() const
{
	return RawThrottleInput;
}

float UDFVehicleMovementComponent::GetSteeringInput() const
{
	return RawSteeringInput;
}

void UDFVehicleMovementComponent::UpdateState(float DeltaTime)
{
	Super::UpdateState(DeltaTime);

	const bool bUnmanned = PawnOwner == nullptr || PawnOwner->GetController() == nullptr;
	// A wreck stays where it died, even while its driver still possesses it.
	const ADFVehiclePawn* Vehicle = Cast<ADFVehiclePawn>(PawnOwner);
	const bool bWrecked = Vehicle != nullptr && Vehicle->bIsDestroyed;
	if (bUnmanned || bWrecked)
	{
		// Override the stale replicated inputs the base class falls back to.
		SteeringInput = 0.f;
		ThrottleInput = 0.f;
		BrakeInput = 1.f;
		HandbrakeInput = 1.f;
	}
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS
