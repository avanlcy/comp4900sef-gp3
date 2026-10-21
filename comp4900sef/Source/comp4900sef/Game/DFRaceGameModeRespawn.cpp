// Dead Fire - COMP 4900SEF Group 3
// ADFRaceGameMode, continued: deaths and respawns. The other race rules are in DFRaceGameMode.cpp.

#include "Game/DFRaceGameMode.h"
#include "Character/DFCharacter.h"
#include "Game/DFRacerComponent.h"
#include "Player/DFPlayerController.h"
#include "Track/DFCheckpoint.h"
#include "Vehicle/DFVehiclePawn.h"
#include "comp4900sef.h"
#include "Engine/World.h"
#include "TimerManager.h"
#include "WheeledVehicleMovementComponent.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

void ADFRaceGameMode::NotifyVehicleDestroyed(ADFVehiclePawn* Victim, AController* Killer)
{
	if (!Victim || IsRaceOver())
	{
		return;
	}
	// A parked car still belongs to whoever last drove it.
	AController* VictimController = Victim->GetController() ? Victim->GetController() : Victim->LastDriver;
	if (Killer && Killer != VictimController)
	{
		if (UDFRacerComponent* KillerState = UDFRacerComponent::FindOn(Killer))
		{
			KillerState->Kills += 1;
			AddScore(Killer, PointsPerKill);
		}
	}
	// One incident, one life: a racer already waiting to respawn (say, killed on foot before its parked
	// car was wrecked) loses no second life. The kill above still counts.
	if (PendingRespawns.Contains(VictimController))
	{
		return;
	}
	if (UDFRacerComponent* VictimState = UDFRacerComponent::FindOn(VictimController))
	{
		VictimState->Deaths += 1;
	}
	HandleRacerDeath(VictimController);
}

void ADFRaceGameMode::NotifyCharacterDied(ADFCharacter* Character)
{
	if (!Character || IsRaceOver())
	{
		return;
	}
	AController* Racer = Character->GetController();
	// One incident, one life (see NotifyVehicleDestroyed).
	if (PendingRespawns.Contains(Racer))
	{
		return;
	}
	if (UDFRacerComponent* RacerState = UDFRacerComponent::FindOn(Racer))
	{
		RacerState->Deaths += 1;
	}
	HandleRacerDeath(Racer);
}

void ADFRaceGameMode::HandleRacerDeath(AController* Racer)
{
	const UDFRacerComponent* RacerState = UDFRacerComponent::FindOn(Racer);
	// NPC racers only have their deaths counted: the lives limit is the player's, and NPC respawn is Phase 4.
	if (!RacerState || IsRaceOver() || !Racer->IsPlayerController())
	{
		return;
	}
	UE_LOG(LogDeadFire, Log, TEXT("%s died (%d of %d)"), *Racer->GetName(), RacerState->Deaths, MaxDeaths);
	if (RacerState->Deaths >= MaxDeaths)
	{
		// No lives left: the last death is not respawned.
		EndRace(EDFRaceEndReason::DeathLimit);
		return;
	}
	// Always through the timer, never from inside the call that reported the death: the respawn replaces
	// and destroys the car whose damage handling may still be on the stack. The map entry is what keeps
	// a second report of the same incident from costing another life until the respawn has run.
	const TWeakObjectPtr<AController> WeakRacer(Racer);
	const FTimerDelegate Respawn = FTimerDelegate::CreateWeakLambda(this, [this, WeakRacer]()
	{
		if (AController* PendingRacer = WeakRacer.Get())
		{
			RespawnRacer(PendingRacer);
		}
	});
	FTimerHandle& Handle = PendingRespawns.FindOrAdd(Racer);
	if (RespawnDelay <= 0.f)
	{
		// The timer manager never fires a zero-length timer: the next tick is the shortest wait.
		GetWorldTimerManager().ClearTimer(Handle);
		Handle = GetWorldTimerManager().SetTimerForNextTick(Respawn);
	}
	else
	{
		GetWorldTimerManager().SetTimer(Handle, Respawn, RespawnDelay, false);
	}
}

FTransform ADFRaceGameMode::GetRespawnPoint(AController* Racer)
{
	const UDFRacerComponent* RacerState = UDFRacerComponent::FindOn(Racer);
	if (RacerState && IsValid(RacerState->LastCheckpoint))
	{
		return RacerState->LastCheckpoint->GetRespawnTransform();
	}
	if (Checkpoints.Num() > 0 && IsValid(Checkpoints[0]))
	{
		return Checkpoints[0]->GetRespawnTransform();
	}
	// Location and rotation only: a scaled player start must not scale the car.
	const AActor* Start = FindPlayerStart(Racer);
	return Start ? FTransform(Start->GetActorRotation(), Start->GetActorLocation()) : FTransform::Identity;
}

ADFVehiclePawn* ADFRaceGameMode::SpawnRespawnVehicle(const FTransform& Point)
{
	UClass* VehicleClass = DefaultPawnClass;
	if (!VehicleClass || !VehicleClass->IsChildOf(ADFVehiclePawn::StaticClass()))
	{
		UE_LOG(LogDeadFire, Warning, TEXT("Cannot respawn: the default pawn class is not a Dead Fire vehicle"));
		return nullptr;
	}
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ADFVehiclePawn* Vehicle = GetWorld()->SpawnActor<ADFVehiclePawn>(VehicleClass, Point, Params);
	if (Vehicle)
	{
		Vehicle->ResetHealth();
	}
	return Vehicle;
}

void ADFRaceGameMode::RespawnRacer(AController* Racer)
{
	if (!Racer || IsRaceOver())
	{
		return;
	}
	// Respawning now settles any respawn still waiting for this racer.
	if (FTimerHandle* Pending = PendingRespawns.Find(Racer))
	{
		GetWorldTimerManager().ClearTimer(*Pending);
		PendingRespawns.Remove(Racer);
	}

	ADFPlayerController* DFPlayer = Cast<ADFPlayerController>(Racer);
	ADFVehiclePawn* Vehicle = DFPlayer ? DFPlayer->CurrentVehicle : Cast<ADFVehiclePawn>(Racer->GetPawn());
	ADFCharacter* Character = DFPlayer ? DFPlayer->OnFootCharacter : nullptr;
	const FTransform Point = GetRespawnPoint(Racer);

	ADFVehiclePawn* Wreck = nullptr;
	if (IsValid(Vehicle) && !Vehicle->bIsDestroyed)
	{
		// Intact (for example after leaving the road): the same car, put down at the point at rest.
		Vehicle->TeleportAndStop(Point);
		// The racer drives on at once, so take off the handbrake the stop pulled (EnterVehicle does the same
		// for a character that gets in; one already inside does not get in again).
		if (UWheeledVehicleMovementComponent* Movement = Vehicle->GetVehicleMovementComponent())
		{
			Movement->SetHandbrakeInput(false);
		}
	}
	else
	{
		// Wrecked or gone: a fresh car takes its place.
		Wreck = IsValid(Vehicle) ? Vehicle : nullptr;
		Vehicle = SpawnRespawnVehicle(Point);
		if (!Vehicle)
		{
			return;
		}
		if (Wreck)
		{
			Wreck->EjectOccupant();
		}
	}

	if (IsValid(Character))
	{
		if (Character->IsDead())
		{
			Character->Revive();
		}
		// Wherever the character was (on foot, or pulled out of the wreck above), it rides in the respawned car.
		if (Character->CurrentVehicle != Vehicle)
		{
			if (Character->CurrentVehicle)
			{
				Character->CurrentVehicle->EjectOccupant();
			}
			if (!Vehicle->EnterVehicle(Character))
			{
				UE_LOG(LogDeadFire, Warning, TEXT("Respawn: %s could not take %s on board"), *Vehicle->GetName(), *Character->GetName());
			}
		}
	}

	if (Racer->GetPawn() != Vehicle)
	{
		Racer->Possess(Vehicle);
	}
	// Removed only once the controller has left it: destroying a possessed pawn unpossesses its
	// controller (and destroys one that has no PlayerState).
	if (Wreck)
	{
		Wreck->Destroy();
	}

	if (UDFRacerComponent* RacerState = UDFRacerComponent::FindOn(Racer))
	{
		RacerState->OffTrackSeconds = 0.f;
	}
	if (DFPlayer)
	{
		DFPlayer->CurrentVehicle = Vehicle;
	}
	UE_LOG(LogDeadFire, Log, TEXT("%s respawned in %s at %s"), *Racer->GetName(), *Vehicle->GetName(), *Point.GetLocation().ToString());
	OnRacerRespawned(Racer, Vehicle);
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS
