// Dead Fire - COMP 4900SEF Group 3
// Editor automation tests for the race framework (GameMode, GameState, racer components).

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "DFTestUtils.h"
#include "Game/DFRaceGameMode.h"
#include "Game/DFRaceGameState.h"
#include "Game/DFRacerComponent.h"
#include "Player/DFPlayerController.h"
#include "Vehicle/DFVehiclePawn.h"
#include "AIController.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFGameScoringHooksTest, "DeadFire.Game.ScoringHooks", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFGameScoringHooksTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFRaceGameMode* GameMode = DFTests::SpawnAt<ADFRaceGameMode>(World, FVector::ZeroVector);
	ADFPlayerController* PC1 = DFTests::SpawnAt<ADFPlayerController>(World, FVector::ZeroVector);
	ADFPlayerController* PC2 = DFTests::SpawnAt<ADFPlayerController>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("game mode"), GameMode) || !TestNotNull(TEXT("pc1"), PC1) || !TestNotNull(TEXT("pc2"), PC2)) return false;

	UDFRacerComponent* Racer1 = UDFRacerComponent::FindOn(PC1);
	UDFRacerComponent* Racer2 = UDFRacerComponent::FindOn(PC2);
	if (!TestNotNull(TEXT("racer 1"), Racer1) || !TestNotNull(TEXT("racer 2"), Racer2)) return false;

	GameMode->NotifyLapCompleted(PC1);
	TestEqual(TEXT("lap adds 100 points"), Racer1->Score, 100);
	TestEqual(TEXT("lap counted"), Racer1->LapsCompleted, 1);
	TestEqual(TEXT("after the start line gate 1 is next"), Racer1->NextCheckpointIndex, 1);
	TestEqual(TEXT("other racer untouched"), Racer2->Score, 0);

	ADFVehiclePawn* Car = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector(0.f, 2000.f, 0.f));
	if (!TestNotNull(TEXT("car"), Car)) return false;
	Car->LastDriver = PC1;
	GameMode->NotifyVehicleDestroyed(Car, PC2);
	TestEqual(TEXT("kill adds 50 points"), Racer2->Score, 50);
	TestEqual(TEXT("kill counted"), Racer2->Kills, 1);

	// Racers start with gate 1 next (they start on the line).
	GameMode->NotifyCheckpointPassed(PC2);
	TestEqual(TEXT("checkpoint advances the racer"), Racer2->NextCheckpointIndex, 2);

	TArray<UDFRacerComponent*> Ranked = GameMode->GetRankedRacers();
	TestEqual(TEXT("two racers ranked"), Ranked.Num(), 2);
	if (Ranked.Num() == 2)
	{
		TestEqual(TEXT("highest score first"), Ranked[0], Racer1);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFGameCheckpointTimeTest, "DeadFire.Game.CheckpointTimeOnlyForPlayers", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFGameCheckpointTimeTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFRaceGameMode* GameMode = DFTests::SpawnAt<ADFRaceGameMode>(World, FVector::ZeroVector);
	ADFRaceGameState* State = DFTests::SpawnAt<ADFRaceGameState>(World, FVector::ZeroVector);
	ADFPlayerController* Player = DFTests::SpawnAt<ADFPlayerController>(World, FVector::ZeroVector);
	AAIController* Bot = DFTests::SpawnAt<AAIController>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("game mode"), GameMode) || !TestNotNull(TEXT("state"), State) || !TestNotNull(TEXT("player"), Player) || !TestNotNull(TEXT("bot"), Bot)) return false;

	// NPC racers carry the same component as the player.
	UDFRacerComponent* BotRacer = NewObject<UDFRacerComponent>(Bot, TEXT("Racer"));
	BotRacer->RegisterComponent();
	GameMode->GameState = State;
	State->RemainingTime = 60.f;

	GameMode->NotifyCheckpointPassed(Player);
	TestEqual(TEXT("player checkpoint adds the bonus"), State->RemainingTime, 68.f);

	GameMode->NotifyCheckpointPassed(Bot);
	TestEqual(TEXT("NPC checkpoint does not touch the player's clock"), State->RemainingTime, 68.f);
	TestEqual(TEXT("NPC progress still recorded (gate 1 to gate 2)"), BotRacer->NextCheckpointIndex, 2);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFGameKillCreditTest, "DeadFire.Game.KillCreditRules", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFGameKillCreditTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFRaceGameMode* GameMode = DFTests::SpawnAt<ADFRaceGameMode>(World, FVector::ZeroVector);
	ADFPlayerController* PC1 = DFTests::SpawnAt<ADFPlayerController>(World, FVector::ZeroVector);
	ADFPlayerController* PC2 = DFTests::SpawnAt<ADFPlayerController>(World, FVector::ZeroVector);
	ADFVehiclePawn* Car = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("game mode"), GameMode) || !TestNotNull(TEXT("pc1"), PC1) || !TestNotNull(TEXT("pc2"), PC2) || !TestNotNull(TEXT("car"), Car)) return false;
	UDFRacerComponent* Racer1 = UDFRacerComponent::FindOn(PC1);
	UDFRacerComponent* Racer2 = UDFRacerComponent::FindOn(PC2);

	// Nothing died: nothing is credited.
	GameMode->NotifyVehicleDestroyed(nullptr, PC2);
	TestEqual(TEXT("no victim, no points"), Racer2->Score, 0);
	TestEqual(TEXT("no victim, no kill"), Racer2->Kills, 0);

	// A parked car still belongs to the player who last drove it.
	Car->LastDriver = PC1;
	GameMode->NotifyVehicleDestroyed(Car, PC1);
	TestEqual(TEXT("wrecking your own parked car is not a kill"), Racer1->Score, 0);
	TestEqual(TEXT("own car counts as a death"), Racer1->Deaths, 1);

	// PC1 is still waiting to respawn from the first wreck: the rival is credited, but one incident costs one life.
	GameMode->NotifyVehicleDestroyed(Car, PC2);
	TestEqual(TEXT("rival gets the kill points"), Racer2->Score, 50);
	TestEqual(TEXT("rival kill counted"), Racer2->Kills, 1);
	TestEqual(TEXT("no second death while the respawn is pending"), Racer1->Deaths, 1);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFGameStateClockTest, "DeadFire.Game.ClockAddsTime", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFGameStateClockTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFRaceGameState* State = DFTests::SpawnAt<ADFRaceGameState>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("game state"), State)) return false;

	State->RemainingTime = 65.f;
	State->AddTime(8.f);
	TestEqual(TEXT("checkpoint bonus added"), State->RemainingTime, 73.f);
	TestEqual(TEXT("formatted m:ss"), State->GetRemainingTimeText().ToString(), FString(TEXT("1:13")));
	State->AddTime(-100.f);
	TestEqual(TEXT("clock never negative"), State->RemainingTime, 0.f);
	TestEqual(TEXT("zero formatted"), State->GetRemainingTimeText().ToString(), FString(TEXT("0:00")));
	return true;
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
