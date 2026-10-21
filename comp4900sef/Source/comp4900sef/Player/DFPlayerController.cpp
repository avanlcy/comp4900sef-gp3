// Dead Fire - COMP 4900SEF Group 3

#include "Player/DFPlayerController.h"
#include "Character/DFCharacter.h"
#include "Game/DFRacerComponent.h"
#include "Vehicle/DFVehiclePawn.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

ADFPlayerController::ADFPlayerController()
{
	Racer = CreateDefaultSubobject<UDFRacerComponent>(TEXT("Racer"));
	Racer->RacerName = NSLOCTEXT("DeadFire", "PlayerRacerName", "Player");
	OnFootCharacter = nullptr;
	CurrentVehicle = nullptr;
}

void ADFPlayerController::SwitchToPawn(APawn* NewPawn)
{
	if (NewPawn && NewPawn != GetPawn())
	{
		Possess(NewPawn);
	}
}

void ADFPlayerController::OnPossess(APawn* InPawn)
{
	Super::OnPossess(InPawn);
	if (ADFVehiclePawn* Vehicle = Cast<ADFVehiclePawn>(InPawn))
	{
		// A parked car belongs to its last driver only until they take another car: the one left
		// behind is nobody's now, so its wreck or gate crossing is never charged to this player.
		if (CurrentVehicle && CurrentVehicle != Vehicle)
		{
			CurrentVehicle->LastDriver = nullptr;
		}
		CurrentVehicle = Vehicle;
	}
	else if (ADFCharacter* OnFoot = Cast<ADFCharacter>(InPawn))
	{
		OnFootCharacter = OnFoot;
	}
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS
