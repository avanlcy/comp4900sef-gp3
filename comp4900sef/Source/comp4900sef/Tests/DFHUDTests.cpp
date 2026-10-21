// Dead Fire - COMP 4900SEF Group 3
// Editor automation tests for the HUD snapshot, the in-race UMG widget and the end-of-race summary.

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "DFTestUtils.h"
#include "Character/DFCharacter.h"
#include "Game/DFRaceGameMode.h"
#include "Game/DFRaceGameState.h"
#include "Game/DFRacerComponent.h"
#include "Player/DFPlayerController.h"
#include "UI/DFHUDSnapshot.h"
#include "UI/DFRaceHUDWidget.h"
#include "UI/DFRaceSummaryWidget.h"
#include "Vehicle/DFVehiclePawn.h"
#include "Blueprint/UserWidget.h"
#include "Components/TextBlock.h"
#include "Components/Widget.h"
#include "Engine/EngineTypes.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

namespace
{
	const float CharacterHalfHeight = 96.f;

	/** True when the element takes part in the layout (neither Collapsed nor Hidden). */
	bool IsShown(const UWidget* Widget)
	{
		const ESlateVisibility Visibility = Widget->GetVisibility();
		return Visibility != ESlateVisibility::Collapsed && Visibility != ESlateVisibility::Hidden;
	}

	bool IsCollapsed(const UWidget* Widget)
	{
		return Widget->GetVisibility() == ESlateVisibility::Collapsed;
	}

	FString TextOf(const UTextBlock* Block)
	{
		return Block->GetText().ToString();
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFHUDSnapshotRaceStateTest, "DeadFire.HUD.SnapshotFromRaceState", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFHUDSnapshotRaceStateTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	if (!TestNotNull(TEXT("test world"), World)) return false;
	ADFRaceGameMode* GameMode = DFTests::SpawnAt<ADFRaceGameMode>(World, FVector::ZeroVector);
	ADFRaceGameState* State = DFTests::SpawnAt<ADFRaceGameState>(World, FVector::ZeroVector);
	ADFPlayerController* PC = DFTests::SpawnAt<ADFPlayerController>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("game mode"), GameMode) || !TestNotNull(TEXT("game state"), State) || !TestNotNull(TEXT("player"), PC)) return false;
	UDFRacerComponent* Racer = UDFRacerComponent::FindOn(PC);
	if (!TestNotNull(TEXT("racer"), Racer)) return false;

	// Editor worlds run no PostInitializeComponents, which is where a GameState registers itself with its world.
	World->SetGameState(State);
	State->RemainingTime = 73.f;
	Racer->Score = 150;
	Racer->LapsCompleted = 2;
	Racer->Kills = 1;
	Racer->Deaths = 1;
	if (!TestEqual(TEXT("default death limit"), GameMode->MaxDeaths, 3)) return false;

	const FDFHUDSnapshot Snapshot = UDFRaceHUDWidget::CaptureSnapshot(PC, 1.5f);
	TestEqual(TEXT("score"), Snapshot.Score, 150);
	TestEqual(TEXT("laps"), Snapshot.Laps, 2);
	TestEqual(TEXT("kills"), Snapshot.Kills, 1);
	TestEqual(TEXT("lives left: MaxDeaths - Deaths"), Snapshot.Lives, 2);
	TestEqual(TEXT("seconds left"), Snapshot.RemainingTime, 73.f);
	TestEqual(TEXT("clock text"), Snapshot.TimeText.ToString(), FString(TEXT("1:13")));
	TestFalse(TEXT("no pawn: not in a vehicle"), Snapshot.bInVehicle);
	TestFalse(TEXT("no pawn: not on foot"), Snapshot.bOnFoot);
	TestTrue(TEXT("no prompt"), Snapshot.PromptText.IsEmpty());
	TestEqual(TEXT("not off track"), Snapshot.OffTrackRemaining, -1.f);
	TestEqual(TEXT("no checkpoint flash"), Snapshot.CheckpointFlashRemaining, -1.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFHUDSnapshotVehiclePromptsTest, "DeadFire.HUD.SnapshotVehiclePrompts", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFHUDSnapshotVehiclePromptsTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	if (!TestNotNull(TEXT("test world"), World)) return false;
	DFTests::SpawnFloor(World);
	ADFRaceGameMode* GameMode = DFTests::SpawnAt<ADFRaceGameMode>(World, FVector::ZeroVector);
	ADFRaceGameState* State = DFTests::SpawnAt<ADFRaceGameState>(World, FVector::ZeroVector);
	ADFPlayerController* PC = DFTests::SpawnAt<ADFPlayerController>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("game mode"), GameMode) || !TestNotNull(TEXT("game state"), State) || !TestNotNull(TEXT("player"), PC)) return false;
	UDFRacerComponent* Racer = UDFRacerComponent::FindOn(PC);
	ADFVehiclePawn* Car = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector::ZeroVector);
	ADFCharacter* Char = DFTests::SpawnAt<ADFCharacter>(World, FVector(0.f, -250.f, CharacterHalfHeight));
	if (!TestNotNull(TEXT("racer"), Racer) || !TestNotNull(TEXT("car"), Car) || !TestNotNull(TEXT("character"), Char)) return false;
	if (!TestTrue(TEXT("character gets in"), Car->EnterVehicle(Char))) return false;

	// A stopped car on open ground.
	FDFHUDSnapshot Snapshot = UDFRaceHUDWidget::CaptureSnapshotFor(Car, Racer, State, GameMode, 1.5f);
	TestTrue(TEXT("in a vehicle"), Snapshot.bInVehicle);
	TestFalse(TEXT("not on foot"), Snapshot.bOnFoot);
	TestEqual(TEXT("a stopped car may be left"), Snapshot.PromptText.ToString(), FString(TEXT("[E] Exit vehicle")));
	TestEqual(TEXT("standing still"), Snapshot.SpeedKPH, 0);
	TestEqual(TEXT("four tires"), Snapshot.TireHealth.Num(), 4);
	TestTrue(TEXT("no warning"), Snapshot.WarningText.IsEmpty());

	// Walls on the left, right and behind: slow enough to get out, but nowhere to step.
	DFTests::SpawnBlockingBox(World, FVector(0.f, -Car->ExitSideOffset, 150.f), FVector(150.f));
	DFTests::SpawnBlockingBox(World, FVector(0.f, Car->ExitSideOffset, 150.f), FVector(150.f));
	DFTests::SpawnBlockingBox(World, FVector(-Car->ExitBehindOffset, 0.f, 150.f), FVector(150.f));
	Snapshot = UDFRaceHUDWidget::CaptureSnapshotFor(Car, Racer, State, GameMode, 1.5f);
	TestEqual(TEXT("every exit spot blocked"), Snapshot.PromptText.ToString(), FString(TEXT("No room to exit")));

	// Three seconds off the road out of five.
	if (!TestEqual(TEXT("default off-track grace"), GameMode->OffTrackGraceSeconds, 5.f)) return false;
	Racer->OffTrackSeconds = 3.f;
	Snapshot = UDFRaceHUDWidget::CaptureSnapshotFor(Car, Racer, State, GameMode, 1.5f);
	TestEqual(TEXT("two seconds left to get back"), Snapshot.OffTrackRemaining, 2.f);
	TestTrue(TEXT("off-track countdown shown"), Snapshot.WarningText.ToString().StartsWith(TEXT("RETURN TO TRACK")));

	// Wrecked while still off the road.
	Car->TakeDamage(1000.f, FDamageEvent(), nullptr, nullptr);
	if (!TestTrue(TEXT("car wrecked"), Car->bIsDestroyed)) return false;
	Snapshot = UDFRaceHUDWidget::CaptureSnapshotFor(Car, Racer, State, GameMode, 1.5f);
	TestTrue(TEXT("wreck flagged"), Snapshot.bVehicleDestroyed);
	TestEqual(TEXT("the wreck outranks the off-track countdown"), Snapshot.WarningText.ToString(), FString(TEXT("WRECKED")));
	TestTrue(TEXT("no prompt in a wreck"), Snapshot.PromptText.IsEmpty());

	// Out of the wreck: the wreck right beside the character cannot be entered, so no enter prompt.
	Car->EjectOccupant();
	if (!TestFalse(TEXT("the wreck cannot be entered"), Car->CanBeEntered())) return false;
	Snapshot = UDFRaceHUDWidget::CaptureSnapshotFor(Char, Racer, State, GameMode, 1.5f);
	TestTrue(TEXT("on foot"), Snapshot.bOnFoot);
	TestFalse(TEXT("not in a vehicle"), Snapshot.bInVehicle);
	TestTrue(TEXT("no enter prompt beside a wreck"), Snapshot.PromptText.IsEmpty());

	// Killed on foot (the off-track timer is still set).
	Char->TakeDamage(500.f, FDamageEvent(), nullptr, nullptr);
	if (!TestTrue(TEXT("character dead"), Char->IsDead())) return false;
	Snapshot = UDFRaceHUDWidget::CaptureSnapshotFor(Char, Racer, State, GameMode, 1.5f);
	TestTrue(TEXT("death flagged"), Snapshot.bCharacterDead);
	TestEqual(TEXT("death outranks the off-track countdown"), Snapshot.WarningText.ToString(), FString(TEXT("YOU DIED")));
	TestTrue(TEXT("no prompt when dead"), Snapshot.PromptText.IsEmpty());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFHUDWidgetAppliesSnapshotTest, "DeadFire.HUD.WidgetAppliesSnapshot", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFHUDWidgetAppliesSnapshotTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	if (!TestNotNull(TEXT("test world"), World)) return false;

	// No game instance and no local player in an editor world: the widget still builds its default tree.
	UDFRaceHUDWidget* Widget = CreateWidget<UDFRaceHUDWidget>(World);
	if (!TestNotNull(TEXT("widget created"), Widget)) return false;
	if (!TestNotNull(TEXT("score text built"), Widget->ScoreText) || !TestNotNull(TEXT("lap text built"), Widget->LapText)
		|| !TestNotNull(TEXT("clock built"), Widget->TimeText) || !TestNotNull(TEXT("prompt built"), Widget->PromptText)) return false;
	if (!TestNotNull(TEXT("speed text built"), Widget->SpeedText) || !TestNotNull(TEXT("gear text built"), Widget->GearText) || !TestNotNull(TEXT("tire text built"), Widget->TireText)
		|| !TestNotNull(TEXT("character health text built"), Widget->CharacterHealthText) || !TestNotNull(TEXT("crosshair built"), Widget->CrosshairText)
		|| !TestNotNull(TEXT("vehicle panel built"), Widget->VehiclePanel) || !TestNotNull(TEXT("character panel built"), Widget->CharacterPanel)) return false;

	FDFHUDSnapshot InCar;
	InCar.Score = 150;
	InCar.Laps = 2;
	InCar.RemainingTime = 73.f;
	InCar.TimeText = FText::FromString(TEXT("1:13"));
	InCar.bInVehicle = true;
	InCar.SpeedKPH = 87;
	InCar.GearText = FText::FromString(TEXT("3"));
	InCar.VehicleHealth = 80.f;
	InCar.VehicleMaxHealth = 100.f;
	InCar.TireHealth = { 30.f, -1.f, 30.f, 30.f };
	InCar.PromptText = FText::FromString(TEXT("[E] Exit vehicle"));
	Widget->ApplySnapshot(InCar);
	TestEqual(TEXT("score line"), TextOf(Widget->ScoreText), FString(TEXT("SCORE 150")));
	TestEqual(TEXT("completed laps"), TextOf(Widget->LapText), FString(TEXT("LAPS 2")));
	TestEqual(TEXT("clock"), TextOf(Widget->TimeText), FString(TEXT("1:13")));
	TestEqual(TEXT("speed"), TextOf(Widget->SpeedText), FString(TEXT("87 km/h")));
	TestEqual(TEXT("gear"), TextOf(Widget->GearText), FString(TEXT("GEAR 3")));
	TestEqual(TEXT("tires, the blown one as X"), TextOf(Widget->TireText), FString(TEXT("TIRES [30] [X] [30] [30]")));
	TestEqual(TEXT("prompt"), TextOf(Widget->PromptText), FString(TEXT("[E] Exit vehicle")));
	TestTrue(TEXT("on-foot panel collapsed in a car"), IsCollapsed(Widget->CharacterPanel));
	TestTrue(TEXT("car panel shown in a car"), IsShown(Widget->VehiclePanel));

	FDFHUDSnapshot OnFoot;
	OnFoot.Score = 1500;
	OnFoot.bOnFoot = true;
	OnFoot.CharacterHealth = 40.f;
	OnFoot.CharacterMaxHealth = 100.f;
	OnFoot.PromptText = FText::FromString(TEXT("[E] Enter vehicle"));
	Widget->ApplySnapshot(OnFoot);
	TestEqual(TEXT("score without digit grouping"), TextOf(Widget->ScoreText), FString(TEXT("SCORE 1500")));
	TestEqual(TEXT("character health"), TextOf(Widget->CharacterHealthText), FString(TEXT("HEALTH 40 / 100")));
	TestEqual(TEXT("enter prompt"), TextOf(Widget->PromptText), FString(TEXT("[E] Enter vehicle")));
	TestTrue(TEXT("car panel collapsed on foot"), IsCollapsed(Widget->VehiclePanel));
	TestTrue(TEXT("on-foot panel shown on foot"), IsShown(Widget->CharacterPanel));
	TestTrue(TEXT("crosshair shown on foot"), IsShown(Widget->CrosshairText));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFSummaryTitleByOutcomeTest, "DeadFire.Summary.TitleByOutcome", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFSummaryTitleByOutcomeTest::RunTest(const FString& Parameters)
{
	FDFRaceResult Passed;
	Passed.Reason = EDFRaceEndReason::TimeUp;
	Passed.bPassed = true;
	TestEqual(TEXT("time up with the requirement met"), UDFRaceSummaryWidget::TitleFor(Passed).ToString(), FString(TEXT("RACE COMPLETE")));

	FDFRaceResult Short;
	Short.Reason = EDFRaceEndReason::TimeUp;
	Short.bPassed = false;
	TestEqual(TEXT("time up below the requirement"), UDFRaceSummaryWidget::TitleFor(Short).ToString(), FString(TEXT("TIME UP")));

	FDFRaceResult OutOfLives;
	OutOfLives.Reason = EDFRaceEndReason::DeathLimit;
	TestEqual(TEXT("death limit"), UDFRaceSummaryWidget::TitleFor(OutOfLives).ToString(), FString(TEXT("GAME OVER")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFSummaryShowsPlaceAndStatsTest, "DeadFire.Summary.ShowsPlaceAndStats", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFSummaryShowsPlaceAndStatsTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	if (!TestNotNull(TEXT("test world"), World)) return false;

	// No game instance and no local player in an editor world: the summary still builds its default tree.
	UDFRaceSummaryWidget* Widget = CreateWidget<UDFRaceSummaryWidget>(World);
	if (!TestNotNull(TEXT("widget created"), Widget)) return false;
	if (!TestNotNull(TEXT("title built"), Widget->TitleText) || !TestNotNull(TEXT("place line built"), Widget->PlaceText)
		|| !TestNotNull(TEXT("stats line built"), Widget->StatsText)) return false;

	FDFRaceResult Result;
	Result.Reason = EDFRaceEndReason::TimeUp;
	Result.bPassed = true;
	Result.Score = 1500;
	Result.ScoreRequirement = 300;
	Result.Rank = 1;
	Result.RacerCount = 3;
	Result.Laps = 2;
	Result.Kills = 1;
	Result.Deaths = 0;
	Widget->ShowResults(Result);
	TestEqual(TEXT("title"), TextOf(Widget->TitleText), FString(TEXT("RACE COMPLETE")));
	TestEqual(TEXT("place"), TextOf(Widget->PlaceText), FString(TEXT("Place 1 of 3")));
	TestEqual(TEXT("stats, without digit grouping"), TextOf(Widget->StatsText), FString(TEXT("Score 1500 / 300    Laps 2    Kills 1    Deaths 0")));
	TestNotNull(TEXT("retry button built"), Widget->RetryButton);
	TestNotNull(TEXT("quit button built"), Widget->QuitButton);
	if (TestNotNull(TEXT("retry label built"), Widget->RetryLabel))
	{
		TestEqual(TEXT("retry label"), TextOf(Widget->RetryLabel), FString(TEXT("RETRY")));
	}
	if (TestNotNull(TEXT("quit label built"), Widget->QuitLabel))
	{
		TestEqual(TEXT("quit label"), TextOf(Widget->QuitLabel), FString(TEXT("QUIT")));
	}
	return true;
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
