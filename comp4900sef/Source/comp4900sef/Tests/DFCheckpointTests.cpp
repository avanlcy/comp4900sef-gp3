// Dead Fire - COMP 4900SEF Group 3
// Editor automation tests for checkpoints and the ordered-gate rules of the GameMode.

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "DFTestUtils.h"
#include "Game/DFRaceGameMode.h"
#include "Game/DFRaceGameState.h"
#include "Game/DFRacerComponent.h"
#include "Player/DFPlayerController.h"
#include "Track/DFCheckpoint.h"
#include "Vehicle/DFVehiclePawn.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

namespace
{
	/** A running race in a fresh editor world: GameMode and GameState (60 s left) and one player. */
	struct FDFCheckpointRace
	{
		UWorld* World = nullptr;
		ADFRaceGameMode* GameMode = nullptr;
		ADFRaceGameState* State = nullptr;
		ADFPlayerController* PC = nullptr;
		UDFRacerComponent* Racer = nullptr;

		bool SetUp(FAutomationTestBase& Test)
		{
			World = DFTests::NewTestWorld();
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
			return true;
		}

		/** Spawns a gate with the given index and registers it with the GameMode. */
		ADFCheckpoint* AddGate(int32 Index, const FVector& Location, const FRotator& Rotation = FRotator::ZeroRotator)
		{
			ADFCheckpoint* Gate = DFTests::SpawnAt<ADFCheckpoint>(World, Location, Rotation);
			if (Gate)
			{
				Gate->CheckpointIndex = Index;
				GameMode->RegisterCheckpoint(Gate);
			}
			return Gate;
		}
	};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFCheckpointRegistrationTest, "DeadFire.Checkpoint.RegistrationSortsByIndex", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFCheckpointRegistrationTest::RunTest(const FString& Parameters)
{
	FDFCheckpointRace Race;
	if (!Race.SetUp(*this)) return false;

	ADFCheckpoint* Gate2 = Race.AddGate(2, FVector(4000.f, 0.f, 0.f));
	ADFCheckpoint* Gate0 = Race.AddGate(0, FVector(0.f, 0.f, 0.f));
	ADFCheckpoint* Gate1 = Race.AddGate(1, FVector(2000.f, 0.f, 0.f));
	if (!TestNotNull(TEXT("gate 2"), Gate2) || !TestNotNull(TEXT("gate 0"), Gate0) || !TestNotNull(TEXT("gate 1"), Gate1)) return false;

	ADFRaceGameMode* GameMode = Race.GameMode;
	if (!TestEqual(TEXT("three gates registered"), GameMode->GetCheckpointCount(), 3)) return false;
	TestEqual(TEXT("first is index 0"), GameMode->Checkpoints[0]->CheckpointIndex, 0);
	TestEqual(TEXT("second is index 1"), GameMode->Checkpoints[1]->CheckpointIndex, 1);
	TestEqual(TEXT("third is index 2"), GameMode->Checkpoints[2]->CheckpointIndex, 2);

	GameMode->RegisterCheckpoint(Gate1);
	TestEqual(TEXT("registering a gate twice adds it once"), GameMode->GetCheckpointCount(), 3);

	// A second GameMode that finds the same gates in the level on its own.
	ADFRaceGameMode* Collector = DFTests::SpawnAt<ADFRaceGameMode>(Race.World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("collecting game mode"), Collector)) return false;
	Collector->CollectLevelActors();
	if (!TestEqual(TEXT("level scan finds the three gates"), Collector->GetCheckpointCount(), 3)) return false;
	for (int32 i = 0; i < 3; ++i)
	{
		TestEqual(FString::Printf(TEXT("level scan order matches at %d"), i), Collector->Checkpoints[i], GameMode->Checkpoints[i]);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFCheckpointMisnumberedTest, "DeadFire.Checkpoint.MisnumberedGatesWarn", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFCheckpointMisnumberedTest::RunTest(const FString& Parameters)
{
	// Gates 0, 1, 2: numbered right, so the level scan says nothing.
	{
		FDFCheckpointRace Race;
		if (!Race.SetUp(*this)) return false;
		for (int32 Index = 0; Index < 3; ++Index)
		{
			if (!TestNotNull(FString::Printf(TEXT("gate %d"), Index), Race.AddGate(Index, FVector(2000.f * Index, 0.f, 0.f)))) return false;
		}
		const int32 WarningsBefore = ExecutionInfo.GetWarningTotal() + ExecutionInfo.GetErrorTotal();
		Race.GameMode->CollectLevelActors();
		TestEqual(TEXT("gates 0, 1, 2 raise no warning"), ExecutionInfo.GetWarningTotal() + ExecutionInfo.GetErrorTotal(), WarningsBefore);
	}

	// Gates 0, 1, 3 in a fresh world: gate 2 is missing, so the gate in its place is reported, once.
	FDFCheckpointRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFCheckpoint* Gate0 = Race.AddGate(0, FVector(0.f, 0.f, 0.f));
	ADFCheckpoint* Gate1 = Race.AddGate(1, FVector(2000.f, 0.f, 0.f));
	ADFCheckpoint* Gate3 = Race.AddGate(3, FVector(4000.f, 0.f, 0.f));
	if (!TestNotNull(TEXT("gate 0"), Gate0) || !TestNotNull(TEXT("gate 1"), Gate1) || !TestNotNull(TEXT("gate 3"), Gate3)) return false;

	// The warning names the gate and the index it should have; any other warning would count below.
	AddExpectedError(FString::Printf(TEXT("%s has checkpoint index 3 but should be 2"), *Gate3->GetName()), EAutomationExpectedErrorFlags::Contains, 1);
	const int32 WarningsBefore = ExecutionInfo.GetWarningTotal() + ExecutionInfo.GetErrorTotal();
	Race.GameMode->CollectLevelActors();
	TestEqual(TEXT("no warning besides the misnumbered gate's"), ExecutionInfo.GetWarningTotal() + ExecutionInfo.GetErrorTotal(), WarningsBefore);
	if (!TestEqual(TEXT("all three gates registered"), Race.GameMode->GetCheckpointCount(), 3)) return false;
	TestEqual(TEXT("gate 3 sorts last"), Race.GameMode->Checkpoints[2], Gate3);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFCheckpointOrderTest, "DeadFire.Checkpoint.OnlyTheNextGateCounts", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFCheckpointOrderTest::RunTest(const FString& Parameters)
{
	FDFCheckpointRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFCheckpoint* Gate0 = Race.AddGate(0, FVector(0.f, 0.f, 0.f));
	ADFCheckpoint* Gate1 = Race.AddGate(1, FVector(2000.f, 0.f, 0.f));
	ADFCheckpoint* Gate2 = Race.AddGate(2, FVector(4000.f, 0.f, 0.f));
	if (!TestNotNull(TEXT("gate 0"), Gate0) || !TestNotNull(TEXT("gate 1"), Gate1) || !TestNotNull(TEXT("gate 2"), Gate2)) return false;
	ADFRaceGameMode* GameMode = Race.GameMode;
	UDFRacerComponent* Racer = Race.Racer;

	TestEqual(TEXT("racers start with gate 1 next"), Racer->NextCheckpointIndex, 1);
	TestEqual(TEXT("no gate credited yet"), Racer->LastCheckpointTime, -1.f);

	// Driving the loop backwards from the start line reaches gate 2 first.
	TestFalse(TEXT("skipping ahead to gate 2 does not count"), GameMode->NotifyCheckpointReached(Race.PC, Gate2));
	TestEqual(TEXT("still gate 1 next"), Racer->NextCheckpointIndex, 1);
	TestEqual(TEXT("no time for a skipped gate"), Race.State->RemainingTime, 60.f);

	TestFalse(TEXT("the start line before any gate does not count"), GameMode->NotifyCheckpointReached(Race.PC, Gate0));
	TestEqual(TEXT("no lap"), Racer->LapsCompleted, 0);

	TestTrue(TEXT("the next gate counts"), GameMode->NotifyCheckpointReached(Race.PC, Gate1));
	TestEqual(TEXT("gate 2 next"), Racer->NextCheckpointIndex, 2);
	TestEqual(TEXT("player gains the time bonus"), Race.State->RemainingTime, 68.f);
	TestEqual(TEXT("last checkpoint remembered"), Racer->LastCheckpoint, Gate1);
	TestTrue(TEXT("time of the crossing recorded"), Racer->LastCheckpointTime >= 0.f);

	// Rolling back and forth over the same gate.
	TestFalse(TEXT("the same gate twice does not count"), GameMode->NotifyCheckpointReached(Race.PC, Gate1));
	TestEqual(TEXT("no second bonus"), Race.State->RemainingTime, 68.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFCheckpointLapTest, "DeadFire.Checkpoint.StartLineCompletesLapWithBonus", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFCheckpointLapTest::RunTest(const FString& Parameters)
{
	FDFCheckpointRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFCheckpoint* Gate0 = Race.AddGate(0, FVector(0.f, 0.f, 0.f));
	ADFCheckpoint* Gate1 = Race.AddGate(1, FVector(2000.f, 0.f, 0.f));
	ADFCheckpoint* Gate2 = Race.AddGate(2, FVector(4000.f, 0.f, 0.f));
	if (!TestNotNull(TEXT("gate 0"), Gate0) || !TestNotNull(TEXT("gate 1"), Gate1) || !TestNotNull(TEXT("gate 2"), Gate2)) return false;
	ADFRaceGameMode* GameMode = Race.GameMode;
	UDFRacerComponent* Racer = Race.Racer;

	TestTrue(TEXT("gate 1 counts"), GameMode->NotifyCheckpointReached(Race.PC, Gate1));
	TestTrue(TEXT("gate 2 counts"), GameMode->NotifyCheckpointReached(Race.PC, Gate2));
	TestEqual(TEXT("after the last gate the start line is next"), Racer->NextCheckpointIndex, 0);
	TestEqual(TEXT("no lap before the start line"), Racer->LapsCompleted, 0);

	TestTrue(TEXT("the start line counts"), GameMode->NotifyCheckpointReached(Race.PC, Gate0));
	TestEqual(TEXT("lap completed"), Racer->LapsCompleted, 1);
	TestEqual(TEXT("lap points"), Racer->Score, 100);
	TestEqual(TEXT("the next lap starts at gate 1"), Racer->NextCheckpointIndex, 1);
	TestEqual(TEXT("the start line gives the time bonus too (60 + 3 x 8)"), Race.State->RemainingTime, 84.f);
	TestEqual(TEXT("start line is the last checkpoint"), Racer->LastCheckpoint, Gate0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFCheckpointRaceOverTest, "DeadFire.Checkpoint.IgnoredWhenRaceOver", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFCheckpointRaceOverTest::RunTest(const FString& Parameters)
{
	FDFCheckpointRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFCheckpoint* Gate0 = Race.AddGate(0, FVector(0.f, 0.f, 0.f));
	ADFCheckpoint* Gate1 = Race.AddGate(1, FVector(2000.f, 0.f, 0.f));
	if (!TestNotNull(TEXT("gate 0"), Gate0) || !TestNotNull(TEXT("gate 1"), Gate1)) return false;

	Race.State->bRaceActive = false;
	TestFalse(TEXT("no crossing counts after the race"), Race.GameMode->NotifyCheckpointReached(Race.PC, Gate1));
	TestEqual(TEXT("still gate 1 next"), Race.Racer->NextCheckpointIndex, 1);
	TestEqual(TEXT("clock untouched"), Race.State->RemainingTime, 60.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFCheckpointRespawnTransformTest, "DeadFire.Checkpoint.RespawnTransformAndNoGameMode", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFCheckpointRespawnTransformTest::RunTest(const FString& Parameters)
{
	FDFCheckpointRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFCheckpoint* Gate1 = Race.AddGate(1, FVector(2000.f, 500.f, 120.f), FRotator(0.f, 90.f, 0.f));
	ADFVehiclePawn* Car = DFTests::SpawnAt<ADFVehiclePawn>(Race.World, FVector(0.f, 3000.f, 0.f));
	if (!TestNotNull(TEXT("gate 1"), Gate1) || !TestNotNull(TEXT("car"), Car)) return false;

	// A parked car: no controller, the player drove it last.
	Car->LastDriver = Race.PC;
	TestNull(TEXT("car has no controller"), Car->GetController());
	// The spawned GameMode is not the world's auth GameMode (editor worlds have none), so nothing is reported.
	TestFalse(TEXT("no race GameMode, nothing counts"), Gate1->NotifyVehicle(Car));
	TestEqual(TEXT("still gate 1 next"), Race.Racer->NextCheckpointIndex, 1);

	const FTransform Respawn = Gate1->GetRespawnTransform();
	TestEqual(TEXT("respawn 50 cm above the gate"), Respawn.GetLocation().Z, Gate1->GetActorLocation().Z + 50.f);
	TestEqual(TEXT("respawn at the gate's centre"), FVector2D(Respawn.GetLocation()), FVector2D(Gate1->GetActorLocation()));
	TestEqual(TEXT("respawn faces along the gate"), Respawn.Rotator(), Gate1->GetActorRotation(), 0.01f);
	return true;
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
