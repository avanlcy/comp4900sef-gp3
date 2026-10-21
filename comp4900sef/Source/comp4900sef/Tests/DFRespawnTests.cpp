// Dead Fire - COMP 4900SEF Group 3
// Editor automation tests for deaths, respawns, the death limit and the end of the race.

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "DFTestUtils.h"
#include "Character/DFCharacter.h"
#include "Game/DFRaceGameMode.h"
#include "Game/DFRaceGameState.h"
#include "Game/DFRacerComponent.h"
#include "Player/DFPlayerController.h"
#include "Track/DFCheckpoint.h"
#include "Vehicle/DFVehicleMovementComponent.h"
#include "Vehicle/DFVehiclePawn.h"
#include "Engine/EngineTypes.h"
#include "GameFramework/CharacterMovementComponent.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

namespace
{
	const float CharacterHalfHeight = 96.f;

	/** Where the player's car starts: well away from both gates, so a respawn visibly moves it. */
	const FVector CarStart(2000.f, 3000.f, 0.f);

	FString ReasonName(EDFRaceEndReason Reason)
	{
		return UEnum::GetValueAsString(Reason);
	}

	int32 MovementModeOf(const ADFCharacter* Character)
	{
		return static_cast<int32>(Character->GetCharacterMovement()->MovementMode.GetValue());
	}

	/**
	 * A running race in a fresh editor world on a floor: GameMode and GameState (60 s left), the player,
	 * gate 0 at the origin and gate 1 at (5000, 0, 0) facing yaw 90 (the player's last checkpoint),
	 * and the player's car with the on-foot character stowed inside.
	 */
	struct FDFRespawnRace
	{
		UWorld* World = nullptr;
		ADFRaceGameMode* GameMode = nullptr;
		ADFRaceGameState* State = nullptr;
		ADFPlayerController* PC = nullptr;
		UDFRacerComponent* Racer = nullptr;
		ADFCheckpoint* Gate0 = nullptr;
		ADFCheckpoint* Gate1 = nullptr;
		ADFCharacter* Char = nullptr;
		ADFVehiclePawn* Car = nullptr;

		bool SetUp(FAutomationTestBase& Test)
		{
			World = DFTests::NewTestWorld();
			DFTests::SpawnFloor(World);
			GameMode = DFTests::SpawnAt<ADFRaceGameMode>(World, FVector::ZeroVector);
			State = DFTests::SpawnAt<ADFRaceGameState>(World, FVector::ZeroVector);
			PC = DFTests::SpawnAt<ADFPlayerController>(World, FVector::ZeroVector);
			if (!Test.TestNotNull(TEXT("game mode"), GameMode) || !Test.TestNotNull(TEXT("game state"), State) || !Test.TestNotNull(TEXT("player"), PC))
			{
				return false;
			}
			Racer = UDFRacerComponent::FindOn(PC);
			if (!Test.TestNotNull(TEXT("racer"), Racer))
			{
				return false;
			}
			// Editor worlds run no BeginPlay: wire the GameState and start the race by hand.
			GameMode->GameState = State;
			State->bRaceActive = true;
			State->RemainingTime = 60.f;

			Gate0 = AddGate(0, FVector::ZeroVector, FRotator::ZeroRotator);
			Gate1 = AddGate(1, FVector(5000.f, 0.f, 0.f), FRotator(0.f, 90.f, 0.f));
			Car = DFTests::SpawnAt<ADFVehiclePawn>(World, CarStart);
			Char = DFTests::SpawnAt<ADFCharacter>(World, CarStart + FVector(0.f, -250.f, CharacterHalfHeight));
			if (!Test.TestNotNull(TEXT("gate 0"), Gate0) || !Test.TestNotNull(TEXT("gate 1"), Gate1) || !Test.TestNotNull(TEXT("car"), Car) || !Test.TestNotNull(TEXT("character"), Char))
			{
				return false;
			}
			// Editor worlds never initialise actors for play, so run the hook a game world would run here:
			// a player controller leaving an uninitialised pawn logs a SetReplicates warning.
			Char->PostInitializeComponents();
			if (!Test.TestTrue(TEXT("character gets in"), Car->EnterVehicle(Char)))
			{
				return false;
			}
			// The player drove this car last (PossessedBy records that in play); the car itself has no controller.
			Car->LastDriver = PC;
			PC->CurrentVehicle = Car;
			PC->OnFootCharacter = Char;
			Racer->LastCheckpoint = Gate1;
			return true;
		}

		ADFCheckpoint* AddGate(int32 Index, const FVector& Location, const FRotator& Rotation)
		{
			ADFCheckpoint* Gate = DFTests::SpawnAt<ADFCheckpoint>(World, Location, Rotation);
			if (Gate)
			{
				Gate->CheckpointIndex = Index;
				GameMode->RegisterCheckpoint(Gate);
			}
			return Gate;
		}

		static void Wreck(ADFVehiclePawn* Vehicle)
		{
			Vehicle->TakeDamage(1000.f, FDamageEvent(), nullptr, nullptr);
		}

		static float Distance2D(const AActor* A, const AActor* B)
		{
			return FVector::Dist2D(A->GetActorLocation(), B->GetActorLocation());
		}
	};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFRespawnWreckTest, "DeadFire.Respawn.WreckSpawnsFreshCarAtLastCheckpoint", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFRespawnWreckTest::RunTest(const FString& Parameters)
{
	FDFRespawnRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFVehiclePawn* Car = Race.Car;

	FDFRespawnRace::Wreck(Car);
	if (!TestTrue(TEXT("car wrecked"), Car->bIsDestroyed)) return false;
	Race.GameMode->NotifyVehicleDestroyed(Car, nullptr);
	TestEqual(TEXT("the wreck counts as a death"), Race.Racer->Deaths, 1);
	TestTrue(TEXT("one death does not end the race"), Race.State->bRaceActive);

	Race.GameMode->RespawnRacer(Race.PC);
	ADFVehiclePawn* NewCar = Race.PC->CurrentVehicle;
	if (!TestNotNull(TEXT("player has a car"), NewCar)) return false;
	TestNotEqual(TEXT("a fresh car replaces the wreck"), NewCar, Car);
	TestFalse(TEXT("fresh car is intact"), NewCar->bIsDestroyed);
	TestEqual(TEXT("fresh car at full health"), NewCar->Health, NewCar->MaxHealth);
	TestTrue(TEXT("fresh car at the last checkpoint"), FDFRespawnRace::Distance2D(NewCar, Race.Gate1) <= 300.f);
	TestEqual(TEXT("fresh car faces along the gate"), NewCar->GetActorRotation().Yaw, 90.f, 1.f);
	TestEqual(TEXT("character rides in the fresh car"), NewCar->Occupant, Race.Char);
	TestTrue(TEXT("character is in a vehicle"), Race.Char->IsInVehicle());
	TestTrue(TEXT("wreck removed"), Car->IsPendingKill() || Car->IsActorBeingDestroyed());
	TestEqual(TEXT("player drives the fresh car"), Race.PC->GetPawn(), static_cast<APawn*>(NewCar));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFRespawnParkedWreckTest, "DeadFire.Respawn.WreckedParkedCarPullsCharacterIn", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFRespawnParkedWreckTest::RunTest(const FString& Parameters)
{
	FDFRespawnRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFVehiclePawn* Car = Race.Car;
	ADFCharacter* Char = Race.Char;

	if (!TestTrue(TEXT("character gets out onto the floor"), Car->ExitVehicle())) return false;
	TestFalse(TEXT("character on foot is visible"), Char->IsHidden());
	Race.PC->Possess(Char);
	if (!TestEqual(TEXT("player controls the character"), Race.PC->GetPawn(), static_cast<APawn*>(Char))) return false;

	// The parked car is wrecked while the player stands beside it.
	FDFRespawnRace::Wreck(Car);
	if (!TestTrue(TEXT("parked car wrecked"), Car->bIsDestroyed)) return false;
	Race.GameMode->RespawnRacer(Race.PC);

	ADFVehiclePawn* NewCar = Race.PC->CurrentVehicle;
	if (!TestNotNull(TEXT("player has a car"), NewCar)) return false;
	TestNotEqual(TEXT("a fresh car replaces the wreck"), NewCar, Car);
	TestTrue(TEXT("character pulled into the fresh car"), Char->IsInVehicle());
	TestEqual(TEXT("fresh car's occupant is the character"), NewCar->Occupant, Char);
	TestTrue(TEXT("character stowed (hidden)"), Char->IsHidden());
	TestTrue(TEXT("fresh car at the last checkpoint"), FDFRespawnRace::Distance2D(NewCar, Race.Gate1) <= 300.f);
	TestEqual(TEXT("player drives the fresh car"), Race.PC->GetPawn(), static_cast<APawn*>(NewCar));
	TestTrue(TEXT("wreck removed"), Car->IsPendingKill());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFRespawnPendingOneDeathTest, "DeadFire.Respawn.PendingRespawnCountsOneDeath", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFRespawnPendingOneDeathTest::RunTest(const FString& Parameters)
{
	FDFRespawnRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFVehiclePawn* Car = Race.Car;
	ADFCharacter* Char = Race.Char;

	if (!TestTrue(TEXT("character gets out onto the floor"), Car->ExitVehicle())) return false;
	Race.PC->Possess(Char);
	if (!TestEqual(TEXT("player controls the character"), Race.PC->GetPawn(), static_cast<APawn*>(Char))) return false;

	// Killed on foot: the respawn is now waiting out RespawnDelay.
	Char->TakeDamage(500.f, FDamageEvent(), nullptr, nullptr);
	if (!TestTrue(TEXT("character dead"), Char->IsDead())) return false;
	Race.GameMode->NotifyCharacterDied(Char);
	TestEqual(TEXT("the character's death counts"), Race.Racer->Deaths, 1);

	// Before the respawn the parked car is wrecked too: the same incident, so no second life is lost.
	FDFRespawnRace::Wreck(Car);
	if (!TestTrue(TEXT("parked car wrecked"), Car->bIsDestroyed)) return false;
	TestEqual(TEXT("the parked car is the player's"), Car->LastDriver, static_cast<AController*>(Race.PC));
	Race.GameMode->NotifyVehicleDestroyed(Car, nullptr);
	TestEqual(TEXT("one incident costs one life"), Race.Racer->Deaths, 1);

	Race.GameMode->RespawnRacer(Race.PC);
	ADFVehiclePawn* NewCar = Race.PC->CurrentVehicle;
	if (!TestNotNull(TEXT("player has a car"), NewCar)) return false;
	TestNotEqual(TEXT("a fresh car replaces the wreck"), NewCar, Car);
	TestFalse(TEXT("fresh car is intact"), NewCar->bIsDestroyed);
	TestEqual(TEXT("character stowed in the fresh car"), NewCar->Occupant, Char);
	TestTrue(TEXT("character hidden in the car"), Char->IsHidden());
	TestEqual(TEXT("player drives the fresh car"), Race.PC->GetPawn(), static_cast<APawn*>(NewCar));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFRespawnAbandonedCarTest, "DeadFire.Respawn.AbandonedCarIsNobodysDeath", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFRespawnAbandonedCarTest::RunTest(const FString& Parameters)
{
	FDFRespawnRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFVehiclePawn* CarA = Race.Car;
	ADFVehiclePawn* CarB = DFTests::SpawnAt<ADFVehiclePawn>(Race.World, CarStart + FVector(0.f, 1000.f, 0.f));
	if (!TestNotNull(TEXT("car B"), CarB)) return false;
	// The player leaves car A below: run the hook a game world would run (see the fixture's character).
	CarA->PostInitializeComponents();

	Race.PC->Possess(CarA);
	if (!TestEqual(TEXT("player drives car A"), Race.PC->GetPawn(), static_cast<APawn*>(CarA))) return false;
	Race.PC->Possess(CarB);
	if (!TestEqual(TEXT("player drives car B"), Race.PC->GetPawn(), static_cast<APawn*>(CarB))) return false;
	TestNull(TEXT("car A, left behind for another car, belongs to nobody"), CarA->LastDriver);
	TestEqual(TEXT("car B is the player's"), CarB->LastDriver, static_cast<AController*>(Race.PC));
	TestEqual(TEXT("car B is the player's current vehicle"), Race.PC->CurrentVehicle, CarB);

	// Someone wrecks the abandoned car: not the player's death, and nothing is respawned.
	const FVector CarBBefore = CarB->GetActorLocation();
	FDFRespawnRace::Wreck(CarA);
	if (!TestTrue(TEXT("car A wrecked"), CarA->bIsDestroyed)) return false;
	Race.GameMode->NotifyVehicleDestroyed(CarA, nullptr);
	TestEqual(TEXT("the abandoned car's wreck costs the player no life"), Race.Racer->Deaths, 0);
	TestEqual(TEXT("no respawn: still car B"), Race.PC->CurrentVehicle, CarB);
	TestEqual(TEXT("no respawn: car B not moved"), CarB->GetActorLocation(), CarBBefore);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFRespawnDeadCharacterTest, "DeadFire.Respawn.DeadCharacterRevivedIntoCar", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFRespawnDeadCharacterTest::RunTest(const FString& Parameters)
{
	FDFRespawnRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFVehiclePawn* Car = Race.Car;
	ADFCharacter* Char = Race.Char;

	if (!TestTrue(TEXT("character gets out onto the floor"), Car->ExitVehicle())) return false;
	TestNull(TEXT("the car had no controller, so nothing possesses the character"), Char->GetController());
	Race.PC->Possess(Char);
	if (!TestEqual(TEXT("player controls the character"), Race.PC->GetPawn(), static_cast<APawn*>(Char))) return false;

	Char->TakeDamage(500.f, FDamageEvent(), nullptr, nullptr);
	TestTrue(TEXT("character dead"), Char->IsDead());
	TestEqual(TEXT("dead character cannot move"), MovementModeOf(Char), static_cast<int32>(MOVE_None));
	Race.GameMode->NotifyCharacterDied(Char);
	TestEqual(TEXT("the death counts"), Race.Racer->Deaths, 1);

	Race.GameMode->RespawnRacer(Race.PC);
	TestEqual(TEXT("character back at full health"), Char->Health, Char->MaxHealth);
	TestFalse(TEXT("character alive"), Char->IsDead());
	TestEqual(TEXT("the intact car is kept"), Race.PC->CurrentVehicle, Car);
	TestEqual(TEXT("character stowed in the player's car"), Char->CurrentVehicle, Race.PC->CurrentVehicle);
	TestEqual(TEXT("car's occupant is the character"), Car->Occupant, Char);
	TestTrue(TEXT("character hidden in the car"), Char->IsHidden());
	TestTrue(TEXT("intact car moved to the last checkpoint"), FDFRespawnRace::Distance2D(Car, Race.Gate1) <= 300.f);
	TestEqual(TEXT("player drives the car"), Race.PC->GetPawn(), static_cast<APawn*>(Car));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFRespawnGateZeroTest, "DeadFire.Respawn.NoCheckpointUsesGateZero", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFRespawnGateZeroTest::RunTest(const FString& Parameters)
{
	FDFRespawnRace Race;
	if (!Race.SetUp(*this)) return false;

	// No gate credited yet (the start of the race).
	Race.Racer->LastCheckpoint = nullptr;
	Race.GameMode->RespawnRacer(Race.PC);

	ADFVehiclePawn* Vehicle = Race.PC->CurrentVehicle;
	if (!TestNotNull(TEXT("player has a car"), Vehicle)) return false;
	TestEqual(TEXT("the intact car is kept"), Vehicle, Race.Car);
	TestTrue(TEXT("respawned at gate 0 at the origin"), FDFRespawnRace::Distance2D(Vehicle, Race.Gate0) <= 300.f);
	TestEqual(TEXT("faces along gate 0"), Vehicle->GetActorRotation().Yaw, 0.f, 1.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFRespawnDeathLimitTest, "DeadFire.Respawn.DeathLimitEndsRace", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFRespawnDeathLimitTest::RunTest(const FString& Parameters)
{
	FDFRespawnRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFVehiclePawn* Car = Race.Car;
	ADFRaceGameState* State = Race.State;

	Race.Racer->Deaths = 2;
	FDFRespawnRace::Wreck(Car);
	Race.GameMode->NotifyVehicleDestroyed(Car, nullptr);

	TestEqual(TEXT("third death counted"), Race.Racer->Deaths, 3);
	TestFalse(TEXT("race over"), State->bRaceActive);
	TestEqual(TEXT("ended by the death limit"), ReasonName(State->Result.Reason), ReasonName(EDFRaceEndReason::DeathLimit));
	TestFalse(TEXT("game over never passes"), State->Result.bPassed);
	TestEqual(TEXT("result records the deaths"), State->Result.Deaths, 3);
	TestEqual(TEXT("result records the requirement"), State->Result.ScoreRequirement, Race.GameMode->ScoreRequirement);
	TestEqual(TEXT("place 1"), State->Result.Rank, 1);
	TestEqual(TEXT("of 1 racer"), State->Result.RacerCount, 1);
	TestEqual(TEXT("the clock keeps its time on a game over"), State->RemainingTime, 60.f);
	TestEqual(TEXT("no respawn: the wreck is still the player's car"), Race.PC->CurrentVehicle, Car);
	TestFalse(TEXT("wreck left in place"), Car->IsPendingKill());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFRespawnAfterEndTest, "DeadFire.Respawn.NothingAfterRaceEnd", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFRespawnAfterEndTest::RunTest(const FString& Parameters)
{
	FDFRespawnRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFVehiclePawn* Car = Race.Car;
	ADFRaceGameState* State = Race.State;

	Race.Racer->Score = 300;
	// The player is driving, foot down, when the clock runs out.
	Race.PC->Possess(Car);
	if (!TestEqual(TEXT("player drives the car"), Race.PC->GetPawn(), static_cast<APawn*>(Car))) return false;
	Car->MoveForward(1.f);
	Race.GameMode->EndRace(EDFRaceEndReason::TimeUp);
	TestFalse(TEXT("race over"), State->bRaceActive);
	TestTrue(TEXT("score requirement met: passed"), State->Result.bPassed);
	TestEqual(TEXT("ended by time up"), ReasonName(State->Result.Reason), ReasonName(EDFRaceEndReason::TimeUp));
	TestEqual(TEXT("result records the score"), State->Result.Score, 300);
	TestEqual(TEXT("clock at zero"), State->RemainingTime, 0.f);
	TestFalse(TEXT("the car takes no more input"), Car->InputEnabled());
	const UDFVehicleMovementComponent* Movement = Cast<UDFVehicleMovementComponent>(Car->GetVehicleMovementComponent());
	if (!TestNotNull(TEXT("Dead Fire movement component"), Movement)) return false;
	TestEqual(TEXT("throttle released at the end"), Movement->GetThrottleInput(), 0.f);

	const FVector Before = Car->GetActorLocation();
	Race.GameMode->RespawnRacer(Race.PC);
	TestEqual(TEXT("no respawn after the end: same car"), Race.PC->CurrentVehicle, Car);
	TestEqual(TEXT("no respawn after the end: car not moved"), Car->GetActorLocation(), Before);

	FDFRespawnRace::Wreck(Car);
	Race.GameMode->NotifyVehicleDestroyed(Car, nullptr);
	TestEqual(TEXT("no death counted after the end"), Race.Racer->Deaths, 0);
	TestEqual(TEXT("still the old car (no respawn)"), Race.PC->CurrentVehicle, Car);
	return true;
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
