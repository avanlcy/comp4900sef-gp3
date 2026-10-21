// Dead Fire - COMP 4900SEF Group 3
// Play-In-Editor race-flow test: loads L_TestTrack, starts a real PIE session and plays the Phase 2
// race rules in the running game: a gate crossing with its time bonus, a wreck and the respawn at the
// last gate, the off-track reset, and the race end with the summary.
// Run headless with tools/run_tests.ps1 -Filter DeadFire.PIE, or in the editor with
// the console command `Automation RunTests DeadFire.PIE` (screenshots land in Saved/Screenshots).

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Tests/DFPIETestUtils.h"
#include "Character/DFCharacter.h"
#include "Game/DFRaceGameMode.h"
#include "Game/DFRaceGameState.h"
#include "Game/DFRacerComponent.h"
#include "Track/DFCheckpoint.h"
#include "UI/DFHUD.h"
#include "UI/DFRaceHUDWidget.h"
#include "Vehicle/DFVehiclePawn.h"
#include "Editor.h"
#include "Engine/World.h"
#include "GameFramework/DamageType.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "Tests/AutomationCommon.h"
#include "Tests/AutomationEditorCommon.h"
#include "WheeledVehicleMovementComponent.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

namespace DFRaceFlow
{
	/** Spec value of CheckpointTimeBonus (BP_DFRaceGameMode keeps the C++ default). */
	const float TimeBonus = 8.f;

	/** A car this close (cm) to gate 1 counts as put back at the gate. */
	const float NearGate = 1500.f;

	struct FState
	{
		TWeakObjectPtr<ADFRaceGameMode> GameMode;
		TWeakObjectPtr<ADFRaceGameState> RaceState;
		TWeakObjectPtr<UDFRacerComponent> Racer;
		TWeakObjectPtr<ADFHUD> HUD;
		TWeakObjectPtr<ADFCharacter> Character;
		/** The player's car: the one the race starts in, then the one the respawn brings. */
		TWeakObjectPtr<ADFVehiclePawn> Vehicle;
		TWeakObjectPtr<ADFVehiclePawn> Wreck;
		float ClockAtStart = 0.f;
		float WorldTimeAtStart = 0.f;
		/** The clock and the game time just before the latest respawn wait. */
		float ClockBeforeRespawn = 0.f;
		float WorldTimeBeforeRespawn = 0.f;
	};
	static FState State;

	/** Notes the clock and the game time, so a check after the respawn can show it added no time. */
	void NoteClockBeforeRespawn()
	{
		UWorld* World = DFPIE::PIEWorld();
		ADFRaceGameState* RaceState = State.RaceState.Get();
		if (World && RaceState)
		{
			State.ClockBeforeRespawn = RaceState->RemainingTime;
			State.WorldTimeBeforeRespawn = World->GetTimeSeconds();
		}
	}

	/** Checkpoint 1: the gate the test drives through, respawns at and is put back at. */
	ADFCheckpoint* GateOne()
	{
		ADFRaceGameMode* GameMode = State.GameMode.Get();
		return (GameMode && GameMode->Checkpoints.IsValidIndex(1)) ? GameMode->Checkpoints[1] : nullptr;
	}

	/** Distance in cm from the actor to gate 1, or -1 when either is missing. */
	float DistanceToGateOne(const AActor* Actor)
	{
		const ADFCheckpoint* Gate = GateOne();
		return (Actor && Gate) ? FVector::Dist(Actor->GetActorLocation(), Gate->GetActorLocation()) : -1.f;
	}
}

// ---- Latent steps -----------------------------------------------------------

/** Waits until the play session has begun with the player in a car, or fails after MaxFrames frames. */
DEFINE_LATENT_AUTOMATION_COMMAND_TWO_PARAMETER(FDFRaceWaitForPlay, FAutomationTestBase*, Test, int32, MaxFrames);
bool FDFRaceWaitForPlay::Update()
{
	UWorld* World = DFPIE::PIEWorld();
	if (World && World->HasBegunPlay() && Cast<ADFVehiclePawn>(DFPIE::PlayerPawn()))
	{
		return true;
	}
	if (--MaxFrames <= 0)
	{
		Test->AddError(TEXT("the play session did not begin with the player in a car"));
		return true;
	}
	return false;
}

/** Step 1: the race is set up in the play world: four gates, gate 1 next, the HUD on screen. */
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFRaceFindRace, FAutomationTestBase*, Test);
bool FDFRaceFindRace::Update()
{
	UWorld* World = DFPIE::PIEWorld();
	APlayerController* PC = DFPIE::PlayerController();
	ADFVehiclePawn* Vehicle = Cast<ADFVehiclePawn>(DFPIE::PlayerPawn());
	if (!Test->TestNotNull(TEXT("PIE world"), World) || !Test->TestNotNull(TEXT("player controller"), PC) || !Test->TestNotNull(TEXT("player starts in a vehicle"), Vehicle)) return true;

	ADFRaceGameMode* GameMode = Cast<ADFRaceGameMode>(World->GetAuthGameMode());
	ADFRaceGameState* RaceState = World->GetGameState<ADFRaceGameState>();
	UDFRacerComponent* Racer = UDFRacerComponent::FindOn(PC);
	ADFHUD* HUD = Cast<ADFHUD>(PC->GetHUD());
	if (!Test->TestNotNull(TEXT("race GameMode"), GameMode) || !Test->TestNotNull(TEXT("race GameState"), RaceState)
		|| !Test->TestNotNull(TEXT("player racer"), Racer) || !Test->TestNotNull(TEXT("Dead Fire HUD"), HUD))
	{
		return true;
	}

	Test->TestEqual(TEXT("the four gates of L_TestTrack are registered"), GameMode->GetCheckpointCount(), 4);
	Test->TestEqual(TEXT("the player heads for gate 1 first"), Racer->NextCheckpointIndex, 1);
	if (Test->TestNotNull(TEXT("HUD widget created"), HUD->HUDWidget))
	{
		Test->TestTrue(TEXT("HUD widget on screen"), HUD->HUDWidget->IsInViewport());
	}
	Test->TestNotNull(TEXT("on-foot character stowed in the car"), Vehicle->Occupant);

	DFRaceFlow::State.GameMode = GameMode;
	DFRaceFlow::State.RaceState = RaceState;
	DFRaceFlow::State.Racer = Racer;
	DFRaceFlow::State.HUD = HUD;
	DFRaceFlow::State.Character = Vehicle->Occupant;
	DFRaceFlow::State.Vehicle = Vehicle;
	return true;
}

/** Step 2: puts the car on the road 1500 cm before gate 1, at rest and facing it, and notes the clock. */
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFRacePlaceBeforeGate, FAutomationTestBase*, Test);
bool FDFRacePlaceBeforeGate::Update()
{
	UWorld* World = DFPIE::PIEWorld();
	ADFVehiclePawn* Vehicle = DFRaceFlow::State.Vehicle.Get();
	ADFRaceGameState* RaceState = DFRaceFlow::State.RaceState.Get();
	ADFCheckpoint* Gate = DFRaceFlow::GateOne();
	if (!Test->TestNotNull(TEXT("PIE world"), World) || !Test->TestNotNull(TEXT("vehicle"), Vehicle)
		|| !Test->TestNotNull(TEXT("race GameState"), RaceState) || !Test->TestNotNull(TEXT("gate 1"), Gate))
	{
		return true;
	}

	FTransform Point = Gate->GetRespawnTransform();
	Point.AddToTranslation(-Point.GetRotation().GetForwardVector() * 1500.f);
	Vehicle->TeleportAndStop(Point);
	// TeleportAndStop parks the car with the handbrake on; take it off so holding W drives it.
	Vehicle->GetVehicleMovementComponent()->SetHandbrakeInput(false);

	DFRaceFlow::State.ClockAtStart = RaceState->RemainingTime;
	DFRaceFlow::State.WorldTimeAtStart = World->GetTimeSeconds();
	Test->AddInfo(FString::Printf(TEXT("car placed at %s, 1500 cm before gate 1; %.2f s on the clock"), *Point.GetLocation().ToString(), RaceState->RemainingTime));
	return true;
}

/** Waits until gate 1 is credited (the racer's next gate becomes 2), or fails after MaxFrames frames. */
DEFINE_LATENT_AUTOMATION_COMMAND_TWO_PARAMETER(FDFRaceWaitForGateOne, FAutomationTestBase*, Test, int32, MaxFrames);
bool FDFRaceWaitForGateOne::Update()
{
	UDFRacerComponent* Racer = DFRaceFlow::State.Racer.Get();
	ADFVehiclePawn* Vehicle = DFRaceFlow::State.Vehicle.Get();
	if (!Test->TestNotNull(TEXT("racer"), Racer) || !Test->TestNotNull(TEXT("vehicle"), Vehicle)) return true;
	if (Racer->NextCheckpointIndex == 2)
	{
		Test->AddInfo(FString::Printf(TEXT("gate 1 credited at %.0f km/h, %.0f cm from its centre"), Vehicle->GetSpeedKPH(), DFRaceFlow::DistanceToGateOne(Vehicle)));
		return true;
	}
	if (--MaxFrames <= 0)
	{
		Test->AddError(FString::Printf(TEXT("holding W did not take the car through gate 1 (next gate %d, car %.0f cm from the gate at %.0f km/h)"),
			Racer->NextCheckpointIndex, DFRaceFlow::DistanceToGateOne(Vehicle), Vehicle->GetSpeedKPH()));
		return true;
	}
	return false;
}

/** Step 2 checks: gate 1 is the last checkpoint and added its time bonus to the running clock. */
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFRaceCheckGateCredited, FAutomationTestBase*, Test);
bool FDFRaceCheckGateCredited::Update()
{
	UWorld* World = DFPIE::PIEWorld();
	UDFRacerComponent* Racer = DFRaceFlow::State.Racer.Get();
	ADFRaceGameState* RaceState = DFRaceFlow::State.RaceState.Get();
	if (!Test->TestNotNull(TEXT("PIE world"), World) || !Test->TestNotNull(TEXT("racer"), Racer) || !Test->TestNotNull(TEXT("race GameState"), RaceState)) return true;

	Test->TestEqual(TEXT("gate 1 is the racer's last checkpoint"), Racer->LastCheckpoint, DFRaceFlow::GateOne());
	const float Elapsed = World->GetTimeSeconds() - DFRaceFlow::State.WorldTimeAtStart;
	const float Expected = DFRaceFlow::State.ClockAtStart - Elapsed + DFRaceFlow::TimeBonus;
	Test->AddInfo(FString::Printf(TEXT("clock %.2f s -> %.2f s after %.2f s of game time (expected %.2f with the +8 s bonus)"),
		DFRaceFlow::State.ClockAtStart, RaceState->RemainingTime, Elapsed, Expected));
	Test->TestEqual(TEXT("gate 1 added 8 s to the clock"), RaceState->RemainingTime, Expected, 0.5f);
	return true;
}

/** Step 3: wrecks the car through the engine's damage call, as a weapon would. */
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFRaceWreckCar, FAutomationTestBase*, Test);
bool FDFRaceWreckCar::Update()
{
	ADFVehiclePawn* Vehicle = DFRaceFlow::State.Vehicle.Get();
	UDFRacerComponent* Racer = DFRaceFlow::State.Racer.Get();
	if (!Test->TestNotNull(TEXT("vehicle"), Vehicle) || !Test->TestNotNull(TEXT("racer"), Racer)) return true;

	UGameplayStatics::ApplyDamage(Vehicle, 1000.f, nullptr, nullptr, UDamageType::StaticClass());
	Test->TestTrue(TEXT("1000 damage wrecks the car"), Vehicle->bIsDestroyed);
	Test->TestEqual(TEXT("the wreck costs one life"), Racer->Deaths, 1);
	DFRaceFlow::State.Wreck = Vehicle;
	DFRaceFlow::NoteClockBeforeRespawn();
	return true;
}

/** Waits until the player drives a car other than the wreck, or fails after MaxFrames frames. */
DEFINE_LATENT_AUTOMATION_COMMAND_TWO_PARAMETER(FDFRaceWaitForRespawn, FAutomationTestBase*, Test, int32, MaxFrames);
bool FDFRaceWaitForRespawn::Update()
{
	ADFVehiclePawn* Car = Cast<ADFVehiclePawn>(DFPIE::PlayerPawn());
	if (Car && Car != DFRaceFlow::State.Wreck.Get(true))
	{
		DFRaceFlow::State.Vehicle = Car;
		return true;
	}
	if (--MaxFrames <= 0)
	{
		Test->AddError(TEXT("the player was not put in a fresh car after the wreck"));
		return true;
	}
	return false;
}

/** Step 3 checks: the fresh car stands at gate 1 with the character inside and full health. */
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFRaceCheckRespawn, FAutomationTestBase*, Test);
bool FDFRaceCheckRespawn::Update()
{
	ADFVehiclePawn* Car = DFRaceFlow::State.Vehicle.Get();
	if (!Test->TestNotNull(TEXT("respawned car"), Car)) return true;

	const float Distance = DFRaceFlow::DistanceToGateOne(Car);
	Test->AddInfo(FString::Printf(TEXT("respawned in %s, %.0f cm from gate 1"), *Car->GetName(), Distance));
	Test->TestTrue(TEXT("the fresh car is at gate 1, the last checkpoint"), Distance >= 0.f && Distance < DFRaceFlow::NearGate);
	Test->TestNotNull(TEXT("the fresh car has an occupant"), Car->Occupant);
	Test->TestEqual(TEXT("the character rides in the fresh car"), Car->Occupant, DFRaceFlow::State.Character.Get());
	Test->TestEqual(TEXT("the fresh car has full health"), Car->Health, Car->MaxHealth);
	return true;
}

/** Step 4: puts the car down 4000 cm to the side of gate 1, well off the road. */
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFRaceLeaveTrack, FAutomationTestBase*, Test);
bool FDFRaceLeaveTrack::Update()
{
	ADFVehiclePawn* Car = DFRaceFlow::State.Vehicle.Get();
	ADFCheckpoint* Gate = DFRaceFlow::GateOne();
	if (!Test->TestNotNull(TEXT("vehicle"), Car) || !Test->TestNotNull(TEXT("gate 1"), Gate)) return true;

	// The respawn transform is the gate lifted RespawnHeightOffset, so the wheels start above the ground.
	FTransform Point = Gate->GetRespawnTransform();
	Point.AddToTranslation(Gate->GetActorRightVector() * 4000.f);
	Car->TeleportAndStop(Point);
	Test->AddInfo(FString::Printf(TEXT("car moved off the road to %s"), *Point.GetLocation().ToString()));
	DFRaceFlow::NoteClockBeforeRespawn();
	return true;
}

/** Waits until the off-track timer has run past 0.5 s, or fails after MaxFrames frames. */
DEFINE_LATENT_AUTOMATION_COMMAND_TWO_PARAMETER(FDFRaceWaitOffTrack, FAutomationTestBase*, Test, int32, MaxFrames);
bool FDFRaceWaitOffTrack::Update()
{
	UDFRacerComponent* Racer = DFRaceFlow::State.Racer.Get();
	if (!Test->TestNotNull(TEXT("racer"), Racer)) return true;
	if (Racer->OffTrackSeconds > 0.5f)
	{
		Test->AddInfo(FString::Printf(TEXT("off-track timer running: %.2f s"), Racer->OffTrackSeconds));
		return true;
	}
	if (--MaxFrames <= 0)
	{
		Test->AddError(FString::Printf(TEXT("the off-track timer did not run off the road (%.2f s)"), Racer->OffTrackSeconds));
		return true;
	}
	return false;
}

/** Waits until the car is back within NearGate of gate 1, or fails after MaxFrames frames. */
DEFINE_LATENT_AUTOMATION_COMMAND_TWO_PARAMETER(FDFRaceWaitBackAtGate, FAutomationTestBase*, Test, int32, MaxFrames);
bool FDFRaceWaitBackAtGate::Update()
{
	ADFVehiclePawn* Car = DFRaceFlow::State.Vehicle.Get();
	if (!Test->TestNotNull(TEXT("the car survives the off-track reset"), Car)) return true;
	const float Distance = DFRaceFlow::DistanceToGateOne(Car);
	if (Distance >= 0.f && Distance < DFRaceFlow::NearGate)
	{
		Test->AddInfo(FString::Printf(TEXT("put back at gate 1 (%.0f cm away) after the off-track grace time"), Distance));
		return true;
	}
	if (--MaxFrames <= 0)
	{
		Test->AddError(FString::Printf(TEXT("the car was not put back at gate 1 (%.0f cm away)"), Distance));
		return true;
	}
	return false;
}

/** Step 4 checks: the reset kept the same car and cost no life. */
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFRaceCheckNoDeath, FAutomationTestBase*, Test);
bool FDFRaceCheckNoDeath::Update()
{
	UDFRacerComponent* Racer = DFRaceFlow::State.Racer.Get();
	if (!Test->TestNotNull(TEXT("racer"), Racer)) return true;
	Test->TestEqual(TEXT("leaving the road costs no life"), Racer->Deaths, 1);
	Test->TestEqual(TEXT("the same car is put back"), DFPIE::PlayerPawn(), static_cast<APawn*>(DFRaceFlow::State.Vehicle.Get()));
	return true;
}

/** Steps 3 and 4 checks: the respawn put the car inside gate 1's trigger, yet the gate was not credited again. */
DEFINE_LATENT_AUTOMATION_COMMAND_TWO_PARAMETER(FDFRaceCheckGateNotCreditedAgain, FAutomationTestBase*, Test, FString, After);
bool FDFRaceCheckGateNotCreditedAgain::Update()
{
	UWorld* World = DFPIE::PIEWorld();
	UDFRacerComponent* Racer = DFRaceFlow::State.Racer.Get();
	ADFRaceGameState* RaceState = DFRaceFlow::State.RaceState.Get();
	if (!Test->TestNotNull(TEXT("PIE world"), World) || !Test->TestNotNull(TEXT("racer"), Racer) || !Test->TestNotNull(TEXT("race GameState"), RaceState)) return true;

	const float Elapsed = World->GetTimeSeconds() - DFRaceFlow::State.WorldTimeBeforeRespawn;
	const float Ceiling = DFRaceFlow::State.ClockBeforeRespawn - Elapsed + 0.5f;
	Test->AddInfo(FString::Printf(TEXT("after the %s: next gate %d; clock %.2f s -> %.2f s after %.2f s of game time (at most %.2f without a bonus)"),
		*After, Racer->NextCheckpointIndex, DFRaceFlow::State.ClockBeforeRespawn, RaceState->RemainingTime, Elapsed, Ceiling));
	Test->TestEqual(FString::Printf(TEXT("after the %s gate 2 is still next"), *After), Racer->NextCheckpointIndex, 2);
	Test->TestTrue(FString::Printf(TEXT("the %s added no time to the clock"), *After), RaceState->RemainingTime <= Ceiling);
	return true;
}

/** Step 5: leaves 0.1 s on the clock. */
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFRaceRunOutClock, FAutomationTestBase*, Test);
bool FDFRaceRunOutClock::Update()
{
	ADFRaceGameState* RaceState = DFRaceFlow::State.RaceState.Get();
	if (Test->TestNotNull(TEXT("race GameState"), RaceState))
	{
		RaceState->RemainingTime = 0.1f;
	}
	return true;
}

/** Step 5 checks: time is up, the summary is on screen and the player's pawn takes no input. */
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFRaceCheckSummary, FAutomationTestBase*, Test);
bool FDFRaceCheckSummary::Update()
{
	ADFRaceGameState* RaceState = DFRaceFlow::State.RaceState.Get();
	ADFHUD* HUD = DFRaceFlow::State.HUD.Get();
	APawn* Pawn = DFPIE::PlayerPawn();
	if (!Test->TestNotNull(TEXT("race GameState"), RaceState) || !Test->TestNotNull(TEXT("HUD"), HUD) || !Test->TestNotNull(TEXT("player pawn"), Pawn)) return true;

	Test->AddInfo(FString::Printf(TEXT("race ended: %s, score %d, deaths %d"), *UEnum::GetValueAsString(RaceState->Result.Reason), RaceState->Result.Score, RaceState->Result.Deaths));
	Test->TestFalse(TEXT("the race is over"), RaceState->bRaceActive);
	Test->TestEqual(TEXT("the race ended on time"), RaceState->Result.Reason, EDFRaceEndReason::TimeUp);
	Test->TestTrue(TEXT("the summary is on screen"), HUD->IsSummaryShown());
	Test->TestFalse(TEXT("the player's pawn takes no input"), Pawn->InputEnabled());
	return true;
}

// ---- The test ---------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFPIERaceFlowTest, "DeadFire.PIE.CheckpointWreckRespawnSummary", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFPIERaceFlowTest::RunTest(const FString& Parameters)
{
	FAutomationEditorCommonUtils::LoadMap(TEXT("/Game/DeadFire/Maps/L_TestTrack"));
	UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	if (!TestNotNull(TEXT("editor world"), EditorWorld) || !TestEqual(TEXT("L_TestTrack loaded"), EditorWorld->GetName(), FString(TEXT("L_TestTrack"))))
	{
		return false;
	}
	DFRaceFlow::State = DFRaceFlow::FState();

	// Waits are in frames or game conditions, never wall-clock seconds: a headless or
	// background editor is CPU-throttled and its physics runs at a fraction of real time.
	ADD_LATENT_AUTOMATION_COMMAND(FStartPIECommand(false));
	ADD_LATENT_AUTOMATION_COMMAND(FDFRaceWaitForPlay(this, 600));
	ADD_LATENT_AUTOMATION_COMMAND(FDFPIEWaitFrames(10));
	ADD_LATENT_AUTOMATION_COMMAND(FDFRaceFindRace(this));

	// Drive through gate 1 with W: the gate is credited and adds its time bonus.
	ADD_LATENT_AUTOMATION_COMMAND(FDFRacePlaceBeforeGate(this));
	ADD_LATENT_AUTOMATION_COMMAND(FDFPIEKey(EKeys::W, IE_Pressed));
	ADD_LATENT_AUTOMATION_COMMAND(FDFRaceWaitForGateOne(this, 900));
	ADD_LATENT_AUTOMATION_COMMAND(FDFPIEKey(EKeys::W, IE_Released));
	ADD_LATENT_AUTOMATION_COMMAND(FDFRaceCheckGateCredited(this));

	// Wreck the car: one life lost, and after the respawn delay a fresh car at gate 1.
	ADD_LATENT_AUTOMATION_COMMAND(FDFRaceWreckCar(this));
	ADD_LATENT_AUTOMATION_COMMAND(FDFRaceWaitForRespawn(this, 600));
	ADD_LATENT_AUTOMATION_COMMAND(FDFRaceCheckRespawn(this));
	ADD_LATENT_AUTOMATION_COMMAND(FDFPIEWaitFrames(10));
	ADD_LATENT_AUTOMATION_COMMAND(FDFRaceCheckGateNotCreditedAgain(this, TEXT("wreck respawn")));
	ADD_LATENT_AUTOMATION_COMMAND(FDFPIEScreenshot(TEXT("DF_PIE_04_respawned")));

	// Leave the road: after the grace time the same car is put back at gate 1 without a death.
	ADD_LATENT_AUTOMATION_COMMAND(FDFRaceLeaveTrack(this));
	ADD_LATENT_AUTOMATION_COMMAND(FDFRaceWaitOffTrack(this, 300));
	ADD_LATENT_AUTOMATION_COMMAND(FDFRaceWaitBackAtGate(this, 2000));
	ADD_LATENT_AUTOMATION_COMMAND(FDFPIEWaitFrames(10));
	ADD_LATENT_AUTOMATION_COMMAND(FDFRaceCheckNoDeath(this));
	ADD_LATENT_AUTOMATION_COMMAND(FDFRaceCheckGateNotCreditedAgain(this, TEXT("off-track reset")));

	// Run the clock out: the race ends, the pawn stops taking input and the summary shows.
	ADD_LATENT_AUTOMATION_COMMAND(FDFRaceRunOutClock(this));
	ADD_LATENT_AUTOMATION_COMMAND(FDFPIEWaitFrames(30));
	ADD_LATENT_AUTOMATION_COMMAND(FDFRaceCheckSummary(this));
	ADD_LATENT_AUTOMATION_COMMAND(FDFPIEScreenshot(TEXT("DF_PIE_05_summary")));

	ADD_LATENT_AUTOMATION_COMMAND(FEndPlayMapCommand());
	return true;
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
