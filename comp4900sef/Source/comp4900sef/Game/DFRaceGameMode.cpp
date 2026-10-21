// Dead Fire - COMP 4900SEF Group 3

#include "Game/DFRaceGameMode.h"
#include "Character/DFCharacter.h"
#include "Game/DFRaceGameState.h"
#include "Game/DFRacerComponent.h"
#include "Player/DFPlayerController.h"
#include "UI/DFHUD.h"
#include "Vehicle/DFVehiclePawn.h"
#include "comp4900sef.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "UObject/ConstructorHelpers.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

ADFRaceGameMode::ADFRaceGameMode()
{
	PrimaryActorTick.bCanEverTick = true;

	DefaultPawnClass = ADFVehiclePawn::StaticClass();
	OnFootCharacterClass = ADFCharacter::StaticClass();
	PlayerControllerClass = ADFPlayerController::StaticClass();
	GameStateClass = ADFRaceGameState::StaticClass();
	HUDClass = ADFHUD::StaticClass();

	// Prefer the Blueprint children when they exist so artists tune the Blueprints, never C++.
	// (Same pattern as the engine templates; the C++ classes above remain the fallback.)
	static ConstructorHelpers::FClassFinder<ADFVehiclePawn> VehicleBP(TEXT("/Game/DeadFire/Blueprints/BP_DFVehicle"));
	static ConstructorHelpers::FClassFinder<ADFCharacter> CharacterBP(TEXT("/Game/DeadFire/Blueprints/BP_DFCharacter"));
	static ConstructorHelpers::FClassFinder<ADFPlayerController> ControllerBP(TEXT("/Game/DeadFire/Blueprints/BP_DFPlayerController"));
	static ConstructorHelpers::FClassFinder<ADFHUD> HUDBP(TEXT("/Game/DeadFire/Blueprints/BP_DFHUD"));
	if (VehicleBP.Succeeded())
	{
		DefaultPawnClass = VehicleBP.Class;
	}
	if (CharacterBP.Succeeded())
	{
		OnFootCharacterClass = CharacterBP.Class;
	}
	if (ControllerBP.Succeeded())
	{
		PlayerControllerClass = ControllerBP.Class;
	}
	if (HUDBP.Succeeded())
	{
		HUDClass = HUDBP.Class;
	}

	// Spec section 4.
	RaceTimeLimit = 120.f;
	CheckpointTimeBonus = 8.f;
	PointsPerLap = 100;
	PointsPerKill = 50;
	MaxDeaths = 3;
	ScoreRequirement = 300;
}

ADFRaceGameState* ADFRaceGameMode::GetRaceState() const
{
	return GetGameState<ADFRaceGameState>();
}

void ADFRaceGameMode::BeginPlay()
{
	Super::BeginPlay();
	if (ADFRaceGameState* State = GetRaceState())
	{
		State->RemainingTime = RaceTimeLimit;
		State->bRaceActive = true;
	}
}

void ADFRaceGameMode::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	ADFRaceGameState* State = GetRaceState();
	if (State && State->bRaceActive)
	{
		State->AddTime(-DeltaSeconds);
		if (State->RemainingTime <= 0.f)
		{
			EndRace();
		}
	}
}

void ADFRaceGameMode::HandleStartingNewPlayer_Implementation(APlayerController* NewPlayer)
{
	Super::HandleStartingNewPlayer_Implementation(NewPlayer);
	SpawnOnFootCharacterFor(NewPlayer);
}

void ADFRaceGameMode::SpawnOnFootCharacterFor(APlayerController* Player)
{
	if (!Player || !OnFootCharacterClass)
	{
		return;
	}
	ADFVehiclePawn* Vehicle = Cast<ADFVehiclePawn>(Player->GetPawn());
	if (!Vehicle)
	{
		return;
	}

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	const FVector SpawnLocation = Vehicle->GetActorLocation() - Vehicle->GetActorRightVector() * 300.f + FVector(0.f, 0.f, 100.f);
	const FRotator SpawnRotation(0.f, Vehicle->GetActorRotation().Yaw, 0.f);
	ADFCharacter* Character = GetWorld()->SpawnActor<ADFCharacter>(OnFootCharacterClass, SpawnLocation, SpawnRotation, Params);
	if (!Character)
	{
		UE_LOG(LogDeadFire, Warning, TEXT("Could not spawn the on-foot character for %s"), *Player->GetName());
		return;
	}

	if (ADFPlayerController* DFPlayer = Cast<ADFPlayerController>(Player))
	{
		DFPlayer->OnFootCharacter = Character;
		DFPlayer->CurrentVehicle = Vehicle;
	}
	// The player already drives the car; the character has no controller, so this only stows it.
	Vehicle->EnterVehicle(Character);
}

void ADFRaceGameMode::AddScore(AController* Racer, int32 Points)
{
	if (UDFRacerComponent* RacerState = UDFRacerComponent::FindOn(Racer))
	{
		RacerState->Score += Points;
	}
}

void ADFRaceGameMode::NotifyLapCompleted(AController* Racer)
{
	if (UDFRacerComponent* RacerState = UDFRacerComponent::FindOn(Racer))
	{
		RacerState->LapsCompleted += 1;
		RacerState->NextCheckpointIndex = 0;
		AddScore(Racer, PointsPerLap);
	}
}

void ADFRaceGameMode::NotifyCheckpointPassed(AController* Racer)
{
	if (UDFRacerComponent* RacerState = UDFRacerComponent::FindOn(Racer))
	{
		RacerState->NextCheckpointIndex += 1;
	}
	// The clock is the player's; NPC progress must not extend it.
	if (Racer && Racer->IsPlayerController())
	{
		if (ADFRaceGameState* State = GetRaceState())
		{
			State->AddTime(CheckpointTimeBonus);
		}
	}
}

void ADFRaceGameMode::NotifyVehicleDestroyed(ADFVehiclePawn* Victim, AController* Killer)
{
	if (!Victim)
	{
		return;
	}
	// A parked car still belongs to whoever last drove it.
	AController* VictimController = Victim->GetController() ? Victim->GetController() : Victim->LastDriver;
	if (UDFRacerComponent* VictimState = UDFRacerComponent::FindOn(VictimController))
	{
		VictimState->Deaths += 1;
	}
	if (Killer && Killer != VictimController)
	{
		if (UDFRacerComponent* KillerState = UDFRacerComponent::FindOn(Killer))
		{
			KillerState->Kills += 1;
			AddScore(Killer, PointsPerKill);
		}
	}
}

TArray<UDFRacerComponent*> ADFRaceGameMode::GetRankedRacers() const
{
	TArray<UDFRacerComponent*> Racers;
	if (UWorld* World = GetWorld())
	{
		// Actor iteration rather than the controller list: it covers player and AI
		// controllers alike and also works in editor worlds (automation tests).
		for (TActorIterator<AController> It(World); It; ++It)
		{
			if (UDFRacerComponent* RacerState = UDFRacerComponent::FindOn(*It))
			{
				Racers.Add(RacerState);
			}
		}
	}
	Racers.Sort([](const UDFRacerComponent& A, const UDFRacerComponent& B)
	{
		if (A.Score != B.Score)
		{
			return A.Score > B.Score;
		}
		if (A.LapsCompleted != B.LapsCompleted)
		{
			return A.LapsCompleted > B.LapsCompleted;
		}
		return A.DistanceAlongTrack > B.DistanceAlongTrack;
	});
	return Racers;
}

void ADFRaceGameMode::EndRace()
{
	ADFRaceGameState* State = GetRaceState();
	if (State)
	{
		if (!State->bRaceActive)
		{
			return;
		}
		State->bRaceActive = false;
		State->RemainingTime = 0.f;
	}

	bool bPassed = false;
	if (UWorld* World = GetWorld())
	{
		for (TActorIterator<APlayerController> It(World); It; ++It)
		{
			if (UDFRacerComponent* RacerState = UDFRacerComponent::FindOn(*It))
			{
				bPassed = bPassed || RacerState->Score >= ScoreRequirement;
			}
		}
	}
	UE_LOG(LogDeadFire, Log, TEXT("Race ended. Passed: %s"), bPassed ? TEXT("yes") : TEXT("no"));
	OnRaceEnded(bPassed);
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS
