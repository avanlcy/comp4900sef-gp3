// Dead Fire - COMP 4900SEF Group 3

#include "Game/DFRacerComponent.h"
#include "GameFramework/Controller.h"

UDFRacerComponent::UDFRacerComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
	RacerName = NSLOCTEXT("DeadFire", "DefaultRacerName", "Racer");
	Score = 0;
	LapsCompleted = 0;
	Kills = 0;
	Deaths = 0;
	// Every racer starts on the start line (index 0), so gate 1 is the first one due.
	NextCheckpointIndex = 1;
	LastCheckpoint = nullptr;
	OffTrackSeconds = 0.f;
	LastCheckpointTime = -1.f;
	DistanceAlongTrack = 0.f;
}

UDFRacerComponent* UDFRacerComponent::FindOn(AController* Controller)
{
	return Controller ? Controller->FindComponentByClass<UDFRacerComponent>() : nullptr;
}
