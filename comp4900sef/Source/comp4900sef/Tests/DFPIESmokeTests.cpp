// Dead Fire - COMP 4900SEF Group 3
// Play-In-Editor smoke test: loads L_TestTrack, starts a real PIE session and drives
// the Phase 1 loop through the actual input bindings (W, Space, E, left mouse).
// Run headless with tools/run_tests.ps1 -Filter DeadFire.PIE, or in the editor with
// the console command `Automation RunTests DeadFire.PIE` (screenshots land in Saved/Screenshots).

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Character/DFCharacter.h"
#include "Vehicle/DFVehiclePawn.h"
#include "Weapons/DFWeaponComponent.h"
#include "Camera/CameraComponent.h"
#include "CollisionQueryParams.h"
#include "Components/SplineMeshComponent.h"
#include "Editor.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "FileHelpers.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "Tests/AutomationCommon.h"
#include "Tests/AutomationEditorCommon.h"
#include "UnrealClient.h"
#include "WheeledVehicleMovementComponent.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

namespace DFSmoke
{
	/** Body health plus every tire: a hit anywhere on the car lowers this. */
	float TotalHealth(const ADFVehiclePawn* Vehicle)
	{
		float Total = Vehicle->Health;
		for (const FDFTireState& Tire : Vehicle->Tires)
		{
			Total += Tire.Health;
		}
		return Total;
	}

	struct FState
	{
		TWeakObjectPtr<ADFVehiclePawn> Vehicle;
		TWeakObjectPtr<ADFCharacter> Character;
		FVector Start = FVector::ZeroVector;
		FVector ParkedAt = FVector::ZeroVector;
		float HealthBeforeShot = 0.f;
		double WaitStarted = 0.0;
	};
	static FState State;

	UWorld* PIEWorld()
	{
		for (const FWorldContext& Context : GEngine->GetWorldContexts())
		{
			if (Context.WorldType == EWorldType::PIE && Context.World())
			{
				return Context.World();
			}
		}
		return nullptr;
	}

	APlayerController* PlayerController()
	{
		UWorld* World = PIEWorld();
		return World ? UGameplayStatics::GetPlayerController(World, 0) : nullptr;
	}

	APawn* PlayerPawn()
	{
		UWorld* World = PIEWorld();
		return World ? UGameplayStatics::GetPlayerPawn(World, 0) : nullptr;
	}

	void Key(const FKey& Key, EInputEvent Event)
	{
		if (APlayerController* PC = PlayerController())
		{
			PC->InputKey(Key, Event, 1.f, false);
		}
	}
}

// ---- Latent steps -----------------------------------------------------------

/** The road must exist in the play world, not only in the editor: trace down under the car. */
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFSmokeCheckRoadUnderCar, FAutomationTestBase*, Test);
bool FDFSmokeCheckRoadUnderCar::Update()
{
	UWorld* World = DFSmoke::PIEWorld();
	ADFVehiclePawn* Vehicle = DFSmoke::State.Vehicle.Get();
	if (!Test->TestNotNull(TEXT("PIE world"), World) || !Test->TestNotNull(TEXT("vehicle"), Vehicle)) return true;

	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(DFSmokeRoad), false, Vehicle);
	const FVector From = Vehicle->GetActorLocation() + FVector(0.f, 0.f, 150.f);
	const bool bHit = World->LineTraceSingleByChannel(Hit, From, From - FVector(0.f, 0.f, 500.f), ECC_Visibility, Params);
	Test->TestTrue(TEXT("something under the car"), bHit);
	if (bHit)
	{
		Test->AddInfo(FString::Printf(TEXT("under the car: %s at Z %.0f"), Hit.GetComponent() ? *Hit.GetComponent()->GetClass()->GetName() : TEXT("none"), Hit.ImpactPoint.Z));
		Test->TestTrue(TEXT("the car starts on the generated road, not on bare ground"), Hit.GetComponent() && Hit.GetComponent()->IsA<USplineMeshComponent>());
	}
	return true;
}

/** Pressing E at speed must keep the player in the car. */
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFSmokeCheckStillInCar, FAutomationTestBase*, Test);
bool FDFSmokeCheckStillInCar::Update()
{
	ADFVehiclePawn* Vehicle = DFSmoke::State.Vehicle.Get();
	if (!Test->TestNotNull(TEXT("vehicle"), Vehicle)) return true;
	Test->AddInfo(FString::Printf(TEXT("E pressed at %.0f km/h"), Vehicle->GetSpeedKPH()));
	Test->TestEqual(TEXT("E while moving keeps the player in the car"), DFSmoke::PlayerPawn(), static_cast<APawn*>(Vehicle));
	Test->TestEqual(TEXT("E while moving keeps the character stowed"), Vehicle->Occupant, DFSmoke::State.Character.Get());
	return true;
}

/** After an exit with W still held, the unmanned car must stay put. */
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFSmokeCheckCarParked, FAutomationTestBase*, Test);
bool FDFSmokeCheckCarParked::Update()
{
	ADFVehiclePawn* Vehicle = DFSmoke::State.Vehicle.Get();
	if (!Test->TestNotNull(TEXT("vehicle"), Vehicle)) return true;
	const float Drift = FVector::Dist(Vehicle->GetActorLocation(), DFSmoke::State.ParkedAt);
	const float Speed = Vehicle->GetVelocity().Size() * 0.036f;
	Test->AddInfo(FString::Printf(TEXT("unmanned car drifted %.0f cm, speed %.0f km/h"), Drift, Speed));
	Test->TestTrue(TEXT("unmanned car does not drive off on its own"), Drift < 100.f);
	Test->TestTrue(TEXT("unmanned car is stopped"), Speed < 5.f);
	return true;
}

DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFSmokeFindVehicle, FAutomationTestBase*, Test);
bool FDFSmokeFindVehicle::Update()
{
	APawn* Pawn = DFSmoke::PlayerPawn();
	if (!Test->TestNotNull(TEXT("PIE player pawn exists"), Pawn)) return true;
	ADFVehiclePawn* Vehicle = Cast<ADFVehiclePawn>(Pawn);
	if (!Test->TestNotNull(TEXT("player starts in a vehicle"), Vehicle)) return true;
	Test->TestTrue(TEXT("vehicle is the Blueprint child"), Vehicle->GetClass()->GetName().StartsWith(TEXT("BP_DFVehicle")));
	Test->TestNotNull(TEXT("on-foot character stowed inside"), Vehicle->Occupant);
	Test->TestTrue(TEXT("player controller is the Blueprint child"), DFSmoke::PlayerController()->GetClass()->GetName().StartsWith(TEXT("BP_DFPlayerController")));
	DFSmoke::State.Vehicle = Vehicle;
	DFSmoke::State.Character = Vehicle->Occupant;
	DFSmoke::State.Start = Vehicle->GetActorLocation();
	return true;
}

DEFINE_LATENT_AUTOMATION_COMMAND_TWO_PARAMETER(FDFSmokeKey, FKey, KeyToPress, EInputEvent, Event);
bool FDFSmokeKey::Update()
{
	DFSmoke::Key(KeyToPress, Event);
	return true;
}

/** Waits a number of engine frames (one Update per frame), independent of wall-clock throttling. */
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFSmokeWaitFrames, int32, Frames);
bool FDFSmokeWaitFrames::Update()
{
	return --Frames <= 0;
}

/** Waits until the car has driven MinDistance cm from where it started, or fails after MaxFrames frames. */
DEFINE_LATENT_AUTOMATION_COMMAND_THREE_PARAMETER(FDFSmokeWaitUntilMoved, FAutomationTestBase*, Test, float, MinDistance, int32, MaxFrames);
bool FDFSmokeWaitUntilMoved::Update()
{
	ADFVehiclePawn* Vehicle = DFSmoke::State.Vehicle.Get();
	if (!Test->TestNotNull(TEXT("vehicle still alive"), Vehicle)) return true;
	const float Moved = FVector::Dist(Vehicle->GetActorLocation(), DFSmoke::State.Start);
	if (Moved >= MinDistance)
	{
		Test->AddInfo(FString::Printf(TEXT("vehicle moved %.0f cm, speed %.0f km/h"), Moved, Vehicle->GetSpeedKPH()));
		return true;
	}
	if (--MaxFrames <= 0)
	{
		Test->AddError(FString::Printf(TEXT("holding W did not drive the car %.0f cm (moved %.0f cm, speed %.0f km/h)"), MinDistance, Moved, Vehicle->GetSpeedKPH()));
		return true;
	}
	return false;
}

/** Waits until the car is slow enough to exit (or gives up after TimeoutSeconds). */
DEFINE_LATENT_AUTOMATION_COMMAND_TWO_PARAMETER(FDFSmokeWaitUntilStopped, FAutomationTestBase*, Test, float, TimeoutSeconds);
bool FDFSmokeWaitUntilStopped::Update()
{
	ADFVehiclePawn* Vehicle = DFSmoke::State.Vehicle.Get();
	if (!Vehicle) return true;
	if (DFSmoke::State.WaitStarted <= 0.0)
	{
		DFSmoke::State.WaitStarted = FPlatformTime::Seconds();
	}
	if (Vehicle->CanExit())
	{
		DFSmoke::State.WaitStarted = 0.0;
		return true;
	}
	if (FPlatformTime::Seconds() - DFSmoke::State.WaitStarted > TimeoutSeconds)
	{
		Test->AddError(FString::Printf(TEXT("car did not stop within %.0f s (speed %.0f km/h)"), TimeoutSeconds, Vehicle->GetSpeedKPH()));
		DFSmoke::State.WaitStarted = 0.0;
		return true;
	}
	return false;
}

/** bExpectBeside: false when the player may have walked off since (W still held after the exit). */
DEFINE_LATENT_AUTOMATION_COMMAND_TWO_PARAMETER(FDFSmokeCheckOnFoot, FAutomationTestBase*, Test, bool, bExpectBeside);
bool FDFSmokeCheckOnFoot::Update()
{
	ADFVehiclePawn* Vehicle = DFSmoke::State.Vehicle.Get();
	ADFCharacter* Character = Cast<ADFCharacter>(DFSmoke::PlayerPawn());
	if (!Test->TestNotNull(TEXT("pressing E put the player on foot"), Character)) return true;
	Test->TestTrue(TEXT("character is the Blueprint child"), Character->GetClass()->GetName().StartsWith(TEXT("BP_DFCharacter")));
	Test->TestFalse(TEXT("character visible"), Character->IsHidden());
	if (Vehicle)
	{
		const float Distance = FVector::Dist(Character->GetActorLocation(), Vehicle->GetActorLocation());
		Test->AddInfo(FString::Printf(TEXT("on foot at %s, car at %s (%.0f cm apart, car speed %.0f km/h)"),
			*Character->GetActorLocation().ToString(), *Vehicle->GetActorLocation().ToString(), Distance, Vehicle->GetVelocity().Size() * 0.036f));
		Test->TestNull(TEXT("vehicle is empty"), Vehicle->Occupant);
		if (bExpectBeside)
		{
			Test->TestTrue(TEXT("character beside the car"), Distance < 600.f);
		}
		DFSmoke::State.ParkedAt = Vehicle->GetActorLocation();
	}
	DFSmoke::State.Character = Character;
	return true;
}

DEFINE_LATENT_AUTOMATION_COMMAND(FDFSmokeAimAtCar);
bool FDFSmokeAimAtCar::Update()
{
	ADFVehiclePawn* Vehicle = DFSmoke::State.Vehicle.Get();
	ADFCharacter* Character = DFSmoke::State.Character.Get();
	APlayerController* PC = DFSmoke::PlayerController();
	if (Vehicle && Character && PC)
	{
		const FVector From = Character->GetFollowCamera() ? Character->GetFollowCamera()->GetComponentLocation() : Character->GetActorLocation();
		const FVector To = Vehicle->GetActorLocation() + FVector(0.f, 0.f, 60.f);
		PC->SetControlRotation((To - From).Rotation());
		DFSmoke::State.HealthBeforeShot = DFSmoke::TotalHealth(Vehicle);
	}
	return true;
}

DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFSmokeCheckShot, FAutomationTestBase*, Test);
bool FDFSmokeCheckShot::Update()
{
	ADFVehiclePawn* Vehicle = DFSmoke::State.Vehicle.Get();
	ADFCharacter* Character = DFSmoke::State.Character.Get();
	if (!Test->TestNotNull(TEXT("vehicle still alive"), Vehicle)) return true;
	const float LastFire = (Character && Character->GetWeapon()) ? Character->GetWeapon()->GetLastFireTime() : -1.f;
	const FVector CameraForward = (Character && Character->GetFollowCamera()) ? Character->GetFollowCamera()->GetForwardVector() : FVector::ZeroVector;
	const float TotalAfter = DFSmoke::TotalHealth(Vehicle);
	Test->AddInfo(FString::Printf(TEXT("vehicle body+tires health %.0f -> %.0f (body %.0f); weapon last fired at %.2f; camera forward %s"),
		DFSmoke::State.HealthBeforeShot, TotalAfter, Vehicle->Health, LastFire, *CameraForward.ToString()));
	Test->TestTrue(TEXT("left mouse fired the weapon"), LastFire >= 0.f);
	Test->TestTrue(TEXT("left mouse fired and damaged the car (body or a tire)"), TotalAfter < DFSmoke::State.HealthBeforeShot);
	return true;
}

DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFSmokeCheckBackInCar, FAutomationTestBase*, Test);
bool FDFSmokeCheckBackInCar::Update()
{
	ADFVehiclePawn* Vehicle = DFSmoke::State.Vehicle.Get();
	ADFCharacter* Character = DFSmoke::State.Character.Get();
	Test->TestEqual(TEXT("pressing E near the car re-enters it"), DFSmoke::PlayerPawn(), static_cast<APawn*>(Vehicle));
	if (Vehicle)
	{
		Test->TestEqual(TEXT("character stowed again"), Vehicle->Occupant, Character);
	}
	return true;
}

DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFSmokeScreenshot, FString, Name);
bool FDFSmokeScreenshot::Update()
{
	FScreenshotRequest::RequestScreenshot(Name, false, false);
	return true;
}

// ---- The test ---------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFPIESmokeTest, "DeadFire.PIE.DriveExitFireEnter", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFPIESmokeTest::RunTest(const FString& Parameters)
{
	FAutomationEditorCommonUtils::LoadMap(TEXT("/Game/DeadFire/Maps/L_TestTrack"));
	UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	if (!TestNotNull(TEXT("editor world"), EditorWorld) || !TestEqual(TEXT("L_TestTrack loaded"), EditorWorld->GetName(), FString(TEXT("L_TestTrack"))))
	{
		return false;
	}
	DFSmoke::State = DFSmoke::FState();

	// Waits are in frames or game conditions, never wall-clock seconds: a headless or
	// background editor is CPU-throttled and its physics runs at a fraction of real time.
	ADD_LATENT_AUTOMATION_COMMAND(FStartPIECommand(false));
	ADD_LATENT_AUTOMATION_COMMAND(FWaitLatentCommand(2.0f));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeWaitFrames(10));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeFindVehicle(this));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeCheckRoadUnderCar(this));

	// Drive: hold W until the car has covered 300 cm.
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::W, IE_Pressed));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeWaitUntilMoved(this, 300.f, 1800));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeScreenshot(TEXT("DF_PIE_01_driving")));

	// E while still rolling must be refused.
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::E, IE_Pressed));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeWaitFrames(3));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::E, IE_Released));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeCheckStillInCar(this));

	// Stop: release W, hold the handbrake, wait until slow enough to exit.
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::W, IE_Released));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::SpaceBar, IE_Pressed));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeWaitUntilStopped(this, 60.f));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::SpaceBar, IE_Released));

	// Exit with E.
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::E, IE_Pressed));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::E, IE_Released));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeWaitFrames(5));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeCheckOnFoot(this, true));

	// Shoot the car with the left mouse button.
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeAimAtCar());
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeWaitFrames(5));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeScreenshot(TEXT("DF_PIE_02_on_foot")));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::LeftMouseButton, IE_Pressed));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeWaitFrames(3));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::LeftMouseButton, IE_Released));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeWaitFrames(5));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeCheckShot(this));

	// Get back in with E.
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::E, IE_Pressed));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeWaitFrames(3));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::E, IE_Released));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeWaitFrames(5));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeCheckBackInCar(this));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeScreenshot(TEXT("DF_PIE_03_back_in_car")));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeWaitFrames(5));

	// Get out again while W is still held: the empty car must not drive away.
	// (W keeps driving the character after the swap, so no "beside the car" check here.)
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::W, IE_Pressed));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeWaitFrames(2));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::E, IE_Pressed));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeWaitFrames(3));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::E, IE_Released));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeKey(EKeys::W, IE_Released));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeWaitFrames(5));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeCheckOnFoot(this, false));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeWaitFrames(90));
	ADD_LATENT_AUTOMATION_COMMAND(FDFSmokeCheckCarParked(this));

	ADD_LATENT_AUTOMATION_COMMAND(FEndPlayMapCommand());
	return true;
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
