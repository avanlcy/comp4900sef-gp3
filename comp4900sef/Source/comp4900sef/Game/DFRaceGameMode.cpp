// Dead Fire - COMP 4900SEF Group 3

#include "Game/DFRaceGameMode.h"
#include "Character/DFCharacter.h"
#include "Game/DFRaceGameState.h"
#include "Game/DFRacerComponent.h"
#include "Player/DFPlayerController.h"
#include "Track/DFCheckpoint.h"
#include "Track/DFTrackSpline.h"
#include "UI/DFHUD.h"
#include "Vehicle/DFVehiclePawn.h"
#include "comp4900sef.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "TimerManager.h"
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
	// Phase 2 spec section 7.
	RespawnDelay = 2.f;
	OffTrackMargin = 500.f;
	OffTrackGraceSeconds = 5.f;

	MainTrack = nullptr;
}

ADFRaceGameState* ADFRaceGameMode::GetRaceState() const
{
	return GetGameState<ADFRaceGameState>();
}

void ADFRaceGameMode::RegisterCheckpoint(ADFCheckpoint* Checkpoint)
{
	if (!Checkpoint || Checkpoints.Contains(Checkpoint))
	{
		return;
	}
	Checkpoints.Add(Checkpoint);
	// A gate removed since it registered leaves a null entry, and the sort dereferences every entry.
	Checkpoints.RemoveAll([](ADFCheckpoint* C) { return C == nullptr; });
	Checkpoints.StableSort([](const ADFCheckpoint& A, const ADFCheckpoint& B)
	{
		return A.CheckpointIndex < B.CheckpointIndex;
	});
}

void ADFRaceGameMode::CollectLevelActors()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	for (TActorIterator<ADFCheckpoint> It(World); It; ++It)
	{
		RegisterCheckpoint(*It);
	}
	// The race expects gates numbered 0, 1, 2, ... with no gaps or repeats: a racer whose next gate does
	// not exist never scores again. Say so for every gate out of place.
	for (int32 Position = 0; Position < Checkpoints.Num(); ++Position)
	{
		const ADFCheckpoint* Gate = Checkpoints[Position];
		if (Gate && Gate->CheckpointIndex != Position)
		{
			UE_LOG(LogDeadFire, Warning, TEXT("%s has checkpoint index %d but should be %d: number the level's %d gates 0 to %d without gaps or repeats"),
				*Gate->GetName(), Gate->CheckpointIndex, Position, Checkpoints.Num(), Checkpoints.Num() - 1);
		}
	}

	Tracks.Reset();
	MainTrack = nullptr;
	for (TActorIterator<ADFTrackSpline> It(World); It; ++It)
	{
		Tracks.Add(*It);
		if (!MainTrack && It->bIsMainTrack)
		{
			MainTrack = *It;
		}
	}
}

int32 ADFRaceGameMode::GetCheckpointCount() const
{
	return Checkpoints.Num();
}

bool ADFRaceGameMode::NotifyCheckpointReached(AController* Racer, ADFCheckpoint* Checkpoint)
{
	const ADFRaceGameState* State = GetRaceState();
	if (State && !State->bRaceActive)
	{
		return false;
	}
	UDFRacerComponent* RacerState = UDFRacerComponent::FindOn(Racer);
	// Only the racer's next gate counts: driving backwards, skipping gates or rolling back and
	// forth over one gate never credits anything.
	if (!RacerState || !Checkpoint || Checkpoint->CheckpointIndex != RacerState->NextCheckpointIndex)
	{
		return false;
	}

	RacerState->LastCheckpoint = Checkpoint;
	RacerState->LastCheckpointTime = GetWorld()->GetTimeSeconds();
	if (Checkpoint->CheckpointIndex == 0)
	{
		NotifyLapCompleted(Racer);
		// The start line is a checkpoint too.
		GrantCheckpointTimeBonus(Racer);
	}
	else
	{
		NotifyCheckpointPassed(Racer);
	}
	return true;
}

void ADFRaceGameMode::GrantCheckpointTimeBonus(AController* Racer)
{
	// The clock is the player's; NPC progress must not extend it.
	if (Racer && Racer->IsPlayerController())
	{
		if (ADFRaceGameState* State = GetRaceState())
		{
			State->AddTime(CheckpointTimeBonus);
		}
	}
}

void ADFRaceGameMode::BeginPlay()
{
	Super::BeginPlay();
	CollectLevelActors();
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
	if (!State || !State->bRaceActive)
	{
		return;
	}
	State->AddTime(-DeltaSeconds);
	if (State->RemainingTime <= 0.f)
	{
		EndRace(EDFRaceEndReason::TimeUp);
		return;
	}
	// Actor iteration covers player and AI controllers alike; TickRacer skips any without a racer component.
	for (TActorIterator<AController> It(GetWorld()); It; ++It)
	{
		TickRacer(*It, It->GetPawn(), DeltaSeconds);
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
		RacerState->NextCheckpointIndex = 1;
		AddScore(Racer, PointsPerLap);
	}
}

void ADFRaceGameMode::NotifyCheckpointPassed(AController* Racer)
{
	if (UDFRacerComponent* RacerState = UDFRacerComponent::FindOn(Racer))
	{
		// After the last gate the start line (index 0) is next.
		const int32 Count = GetCheckpointCount();
		const int32 Next = RacerState->NextCheckpointIndex;
		RacerState->NextCheckpointIndex = (Count > 0) ? (Next + 1) % Count : Next + 1;
	}
	GrantCheckpointTimeBonus(Racer);
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

bool ADFRaceGameMode::IsRaceOver() const
{
	const ADFRaceGameState* State = GetRaceState();
	return State && !State->bRaceActive;
}

bool ADFRaceGameMode::IsOnAnyTrack(const FVector& Location) const
{
	// A level without track splines never penalises anyone.
	if (Tracks.Num() == 0)
	{
		return true;
	}
	for (const ADFTrackSpline* Track : Tracks)
	{
		if (IsValid(Track) && Track->GetLateralDistanceFromTrack(Location) <= Track->RoadWidth * 0.5f + OffTrackMargin)
		{
			return true;
		}
	}
	return false;
}

void ADFRaceGameMode::TickRacer(AController* Racer, APawn* Pawn, float DeltaSeconds)
{
	UDFRacerComponent* RacerState = UDFRacerComponent::FindOn(Racer);
	if (!RacerState || IsRaceOver())
	{
		return;
	}
	if (Pawn && IsValid(MainTrack))
	{
		RacerState->DistanceAlongTrack = MainTrack->GetDistanceAlongTrack(Pawn->GetActorLocation());
	}

	// The timer runs only while the racer drives an intact car. On foot (exploring off the road is free),
	// in a wreck (the death respawn takes over) or without a pawn it starts again from 0.
	const ADFVehiclePawn* Vehicle = Cast<ADFVehiclePawn>(Pawn);
	if (!Vehicle || Vehicle->bIsDestroyed || IsOnAnyTrack(Vehicle->GetActorLocation()))
	{
		RacerState->OffTrackSeconds = 0.f;
		return;
	}
	RacerState->OffTrackSeconds += DeltaSeconds;
	if (RacerState->OffTrackSeconds >= OffTrackGraceSeconds)
	{
		// Leaving the road costs progress, not a life.
		RacerState->OffTrackSeconds = 0.f;
		UE_LOG(LogDeadFire, Log, TEXT("%s stayed off the track for %.1f s"), *Racer->GetName(), OffTrackGraceSeconds);
		RespawnRacer(Racer);
	}
}

void ADFRaceGameMode::EndRace(EDFRaceEndReason Reason)
{
	ADFRaceGameState* State = GetRaceState();
	if (State)
	{
		if (!State->bRaceActive)
		{
			return;
		}
		State->bRaceActive = false;
		if (Reason == EDFRaceEndReason::TimeUp)
		{
			State->RemainingTime = 0.f;
		}
	}

	// A respawn still waiting must not bring anyone back after the end.
	for (TPair<AController*, FTimerHandle>& Pending : PendingRespawns)
	{
		GetWorldTimerManager().ClearTimer(Pending.Value);
	}
	PendingRespawns.Reset();

	FDFRaceResult Result;
	Result.Reason = Reason;
	Result.ScoreRequirement = ScoreRequirement;
	const TArray<UDFRacerComponent*> Ranked = GetRankedRacers();
	Result.RacerCount = Ranked.Num();

	UWorld* World = GetWorld();
	if (World)
	{
		// The result is the player's: the first player controller that races.
		for (TActorIterator<APlayerController> It(World); It; ++It)
		{
			if (UDFRacerComponent* RacerState = UDFRacerComponent::FindOn(*It))
			{
				Result.Score = RacerState->Score;
				Result.Laps = RacerState->LapsCompleted;
				Result.Kills = RacerState->Kills;
				Result.Deaths = RacerState->Deaths;
				Result.Rank = Ranked.Find(RacerState) + 1;
				Result.bPassed = Reason == EDFRaceEndReason::TimeUp && RacerState->Score >= ScoreRequirement;
				break;
			}
		}
	}
	if (State)
	{
		State->Result = Result;
	}

	if (World)
	{
		for (TActorIterator<APlayerController> It(World); It; ++It)
		{
			APlayerController* Player = *It;
			if (APawn* Pawn = Player->GetPawn())
			{
				Pawn->DisableInput(Player);
				// Input no longer reaches the car, so park it or it keeps driving on the last pedals.
				if (ADFVehiclePawn* Vehicle = Cast<ADFVehiclePawn>(Pawn))
				{
					Vehicle->ReleaseControls();
				}
			}
			if (ADFHUD* HUD = Cast<ADFHUD>(Player->GetHUD()))
			{
				HUD->ShowSummary();
			}
		}
	}

	UE_LOG(LogDeadFire, Log, TEXT("Race ended: %s. Passed: %s"), *UEnum::GetValueAsString(Reason), Result.bPassed ? TEXT("yes") : TEXT("no"));
	OnRaceEnded(Result.bPassed);
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS
