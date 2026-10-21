// Dead Fire - COMP 4900SEF Group 3
// Editor automation tests for ADFVehiclePawn (damage routing, tires, enter/exit).

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "DFTestUtils.h"
#include "Character/DFCharacter.h"
#include "Vehicle/DFVehicleMovementComponent.h"
#include "Vehicle/DFVehiclePawn.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/EngineTypes.h"
#include "GameFramework/DamageType.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

namespace
{
	FPointDamageEvent MakePointDamage(float Damage, FName BoneName, const FVector& ImpactPoint = FVector::ZeroVector)
	{
		FHitResult Hit;
		Hit.BoneName = BoneName;
		Hit.ImpactPoint = ImpactPoint;
		Hit.Location = ImpactPoint;
		return FPointDamageEvent(Damage, Hit, FVector::ForwardVector, UDamageType::StaticClass());
	}

	const float CharacterHalfHeight = 96.f;
}

// ---- Damage -----------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFVehicleTireDamageByBoneTest, "DeadFire.Vehicle.TireDamageByBone", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFVehicleTireDamageByBoneTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	if (!TestNotNull(TEXT("test world"), World)) return false;
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("vehicle spawned"), Vehicle)) return false;

	TestEqual(TEXT("four tires"), Vehicle->Tires.Num(), 4);
	const float Applied = Vehicle->TakeDamage(10.f, MakePointDamage(10.f, TEXT("Wheel_Front_Left")), nullptr, nullptr);

	TestEqual(TEXT("applied damage"), Applied, 10.f);
	TestEqual(TEXT("front-left tire health"), Vehicle->Tires[0].Health, 20.f);
	TestEqual(TEXT("other tire untouched"), Vehicle->Tires[1].Health, 30.f);
	TestEqual(TEXT("body health untouched"), Vehicle->Health, 100.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFVehicleTireDamageByProximityTest, "DeadFire.Vehicle.TireDamageByProximity", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFVehicleTireDamageByProximityTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("vehicle spawned"), Vehicle)) return false;

	const FVector FrontRight = Vehicle->GetMesh()->GetBoneLocation(TEXT("Wheel_Front_Right"));
	const FVector FrontLeft = Vehicle->GetMesh()->GetBoneLocation(TEXT("Wheel_Front_Left"));
	TestTrue(TEXT("wheel bones resolve to distinct locations"), FVector::Dist(FrontRight, FrontLeft) > 50.f);

	// Bone name is the chassis, but the impact is right on the front-right wheel.
	Vehicle->TakeDamage(10.f, MakePointDamage(10.f, TEXT("Vehicle_Base"), FrontRight), nullptr, nullptr);

	TestEqual(TEXT("front-right tire took the hit"), Vehicle->Tires[1].Health, 20.f);
	TestEqual(TEXT("front-left tire untouched"), Vehicle->Tires[0].Health, 30.f);
	TestEqual(TEXT("body untouched"), Vehicle->Health, 100.f);
	TestEqual(TEXT("far impact is not a tire"), Vehicle->FindTireIndexForHit(NAME_None, FVector(0.f, 0.f, 5000.f)), (int32)INDEX_NONE);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFVehicleTireBlowsTest, "DeadFire.Vehicle.TireBlowsAndScalesThrottle", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFVehicleTireBlowsTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("vehicle spawned"), Vehicle)) return false;

	TestEqual(TEXT("no blown tires initially"), Vehicle->GetBlownTireCount(), 0);
	TestEqual(TEXT("full throttle initially"), Vehicle->GetThrottleScale(), 1.f);

	Vehicle->TakeDamage(30.f, MakePointDamage(30.f, TEXT("Wheel_Rear_Left")), nullptr, nullptr);

	TestTrue(TEXT("rear-left tire blown"), Vehicle->Tires[2].bBlown);
	TestEqual(TEXT("rear-left tire health floored"), Vehicle->Tires[2].Health, 0.f);
	TestEqual(TEXT("one blown tire"), Vehicle->GetBlownTireCount(), 1);
	TestEqual(TEXT("throttle scaled by 0.8"), Vehicle->GetThrottleScale(), 0.8f, 0.001f);

	// Extra damage to the same tire stays at zero and does not count twice.
	Vehicle->TakeDamage(10.f, MakePointDamage(10.f, TEXT("Wheel_Rear_Left")), nullptr, nullptr);
	TestEqual(TEXT("still one blown tire"), Vehicle->GetBlownTireCount(), 1);
	TestEqual(TEXT("health stays at zero"), Vehicle->Tires[2].Health, 0.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFVehicleBodyDamageTest, "DeadFire.Vehicle.BodyDamageDestroysOnce", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFVehicleBodyDamageTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("vehicle spawned"), Vehicle)) return false;

	FDamageEvent Generic(UDamageType::StaticClass());
	const float First = Vehicle->TakeDamage(100.f, Generic, nullptr, nullptr);
	TestEqual(TEXT("first hit applied"), First, 100.f);
	TestEqual(TEXT("health is zero"), Vehicle->Health, 0.f);
	TestTrue(TEXT("vehicle destroyed"), Vehicle->bIsDestroyed);
	TestFalse(TEXT("destroyed vehicle cannot be entered"), Vehicle->CanBeEntered());

	const float Second = Vehicle->TakeDamage(50.f, Generic, nullptr, nullptr);
	TestEqual(TEXT("damage after destruction is ignored"), Second, 0.f);
	TestEqual(TEXT("health stays zero"), Vehicle->Health, 0.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFVehicleBlueprintDefaultsTest, "DeadFire.Vehicle.BlueprintDefaultsSetStartingHealth", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFVehicleBlueprintDefaultsTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	// Deferred spawn mimics a Blueprint child whose defaults differ from the C++ constructor.
	ADFVehiclePawn* Vehicle = DFTests::SpawnDeferredAt<ADFVehiclePawn>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("vehicle spawned"), Vehicle)) return false;
	Vehicle->MaxHealth = 200.f;
	Vehicle->TireMaxHealth = 50.f;
	Vehicle->FinishSpawning(FTransform(FVector::ZeroVector));
	// Editor worlds never initialise actors for play, so run the hook a game world would run here.
	Vehicle->PostInitializeComponents();

	TestEqual(TEXT("starting body health follows MaxHealth"), Vehicle->Health, 200.f);
	TestEqual(TEXT("tire max follows TireMaxHealth"), Vehicle->Tires[0].MaxHealth, 50.f);
	TestEqual(TEXT("tire health follows TireMaxHealth"), Vehicle->Tires[3].Health, 50.f);
	TestEqual(TEXT("bone names kept"), Vehicle->Tires[0].BoneName, FName(TEXT("Wheel_Front_Left")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFVehicleDestroyedThrottleTest, "DeadFire.Vehicle.DestroyedCarIgnoresThrottle", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFVehicleDestroyedThrottleTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("vehicle spawned"), Vehicle)) return false;
	UDFVehicleMovementComponent* Movement = Cast<UDFVehicleMovementComponent>(Vehicle->GetVehicleMovementComponent());
	if (!TestNotNull(TEXT("Dead Fire movement component"), Movement)) return false;

	Vehicle->MoveForward(1.f);
	TestEqual(TEXT("throttle follows the input"), Movement->GetThrottleInput(), 1.f);

	Vehicle->TakeDamage(1000.f, FDamageEvent(UDamageType::StaticClass()), nullptr, nullptr);
	if (!TestTrue(TEXT("vehicle wrecked"), Vehicle->bIsDestroyed)) return false;
	TestEqual(TEXT("the wreck cuts the throttle"), Movement->GetThrottleInput(), 0.f);

	Vehicle->MoveForward(1.f);
	Vehicle->MoveRight(1.f);
	TestEqual(TEXT("a wreck ignores the throttle"), Movement->GetThrottleInput(), 0.f);
	TestEqual(TEXT("a wreck ignores the steering"), Movement->GetSteeringInput(), 0.f);
	return true;
}

// ---- Exit rules -------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFVehicleExitSpeedTest, "DeadFire.Vehicle.CannotExitWhenMoving", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFVehicleExitSpeedTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("vehicle spawned"), Vehicle)) return false;

	TestFalse(TEXT("no occupant: exit fails"), Vehicle->ExitVehicle());
	TestFalse(TEXT("no occupant: CanExit false"), Vehicle->CanExit());
	TestTrue(TEXT("empty vehicle can be entered"), Vehicle->CanBeEntered());
	TestTrue(TEXT("9.9 km/h is slow enough"), Vehicle->IsBelowExitSpeed(9.9f));
	TestFalse(TEXT("10 km/h is too fast"), Vehicle->IsBelowExitSpeed(10.f));
	TestFalse(TEXT("50 km/h is too fast"), Vehicle->IsBelowExitSpeed(50.f));
	TestTrue(TEXT("reverse speed uses magnitude"), Vehicle->IsBelowExitSpeed(-5.f));
	return true;
}

// ---- Enter / exit -----------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFVehicleEnterTest, "DeadFire.Vehicle.EnterStowsCharacter", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFVehicleEnterTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector::ZeroVector);
	ADFCharacter* Character = DFTests::SpawnAt<ADFCharacter>(World, FVector(0.f, -250.f, CharacterHalfHeight));
	if (!TestNotNull(TEXT("vehicle"), Vehicle) || !TestNotNull(TEXT("character"), Character)) return false;

	TestTrue(TEXT("enter succeeds"), Vehicle->EnterVehicle(Character));
	TestEqual(TEXT("occupant recorded"), Vehicle->Occupant, Character);
	TestTrue(TEXT("character knows its vehicle"), Character->IsInVehicle());
	TestEqual(TEXT("character vehicle pointer"), Character->CurrentVehicle, Vehicle);
	TestTrue(TEXT("character stowed"), Character->bIsStowed);
	TestTrue(TEXT("character hidden"), Character->IsHidden());
	TestEqual(TEXT("character attached to vehicle"), Character->GetAttachParentActor(), static_cast<AActor*>(Vehicle));
	TestFalse(TEXT("occupied vehicle cannot be entered"), Vehicle->CanBeEntered());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFVehicleExitTest, "DeadFire.Vehicle.ExitPlacesCharacterBeside", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFVehicleExitTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	DFTests::SpawnFloor(World);
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector::ZeroVector);
	ADFCharacter* Character = DFTests::SpawnAt<ADFCharacter>(World, FVector(0.f, -250.f, CharacterHalfHeight));
	if (!TestNotNull(TEXT("vehicle"), Vehicle) || !TestNotNull(TEXT("character"), Character)) return false;
	if (!TestTrue(TEXT("enter succeeds"), Vehicle->EnterVehicle(Character))) return false;

	TestTrue(TEXT("exit succeeds when stopped"), Vehicle->ExitVehicle());
	TestNull(TEXT("no occupant after exit"), Vehicle->Occupant);
	TestFalse(TEXT("character on foot"), Character->IsInVehicle());
	TestFalse(TEXT("character not stowed"), Character->bIsStowed);
	TestFalse(TEXT("character visible"), Character->IsHidden());
	TestNull(TEXT("character detached"), Character->GetAttachParentActor());
	const FVector Delta = Character->GetActorLocation() - Vehicle->GetActorLocation();
	TestTrue(TEXT("placed on the driver side"), Delta.Y <= -150.f);
	TestTrue(TEXT("placed close to the car"), Delta.Size() < 500.f);
	TestEqual(TEXT("placed standing on the floor"), Character->GetActorLocation().Z, CharacterHalfHeight, 15.f);
	TestTrue(TEXT("vehicle can be entered again"), Vehicle->CanBeEntered());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFVehicleExitNoGroundTest, "DeadFire.Vehicle.ExitFailsWithoutGround", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFVehicleExitNoGroundTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	// No floor at all: every exit spot would be a drop into the void.
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector::ZeroVector);
	ADFCharacter* Character = DFTests::SpawnAt<ADFCharacter>(World, FVector(0.f, -250.f, CharacterHalfHeight));
	if (!TestNotNull(TEXT("vehicle"), Vehicle) || !TestNotNull(TEXT("character"), Character)) return false;
	if (!TestTrue(TEXT("enter succeeds"), Vehicle->EnterVehicle(Character))) return false;

	FVector Unused;
	TestFalse(TEXT("no exit spot without ground"), Vehicle->FindExitLocation(Unused));
	TestFalse(TEXT("exit refused"), Vehicle->ExitVehicle());
	TestTrue(TEXT("character stays stowed"), Character->bIsStowed);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFVehicleExitBlockedTest, "DeadFire.Vehicle.ExitFailsWhenBlocked", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFVehicleExitBlockedTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	DFTests::SpawnFloor(World);
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector::ZeroVector);
	ADFCharacter* Character = DFTests::SpawnAt<ADFCharacter>(World, FVector(0.f, -250.f, CharacterHalfHeight));
	if (!TestNotNull(TEXT("vehicle"), Vehicle) || !TestNotNull(TEXT("character"), Character)) return false;
	if (!TestTrue(TEXT("enter succeeds"), Vehicle->EnterVehicle(Character))) return false;

	// Walls on the left, right and behind: every exit candidate is blocked.
	DFTests::SpawnBlockingCube(World, FVector(0.f, -Vehicle->ExitSideOffset, 150.f), 300.f);
	DFTests::SpawnBlockingCube(World, FVector(0.f, Vehicle->ExitSideOffset, 150.f), 300.f);
	DFTests::SpawnBlockingCube(World, FVector(-Vehicle->ExitBehindOffset, 0.f, 150.f), 300.f);

	FVector Unused;
	TestFalse(TEXT("no free exit spot"), Vehicle->FindExitLocation(Unused));
	TestFalse(TEXT("exit refused"), Vehicle->ExitVehicle());
	TestTrue(TEXT("character stays stowed"), Character->bIsStowed);
	TestEqual(TEXT("occupant unchanged"), Vehicle->Occupant, Character);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFVehicleExitWallBetweenTest, "DeadFire.Vehicle.ExitAvoidsWallBetween", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFVehicleExitWallBetweenTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	DFTests::SpawnFloor(World);
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector::ZeroVector);
	ADFCharacter* Character = DFTests::SpawnAt<ADFCharacter>(World, FVector(0.f, 250.f, CharacterHalfHeight));
	if (!TestNotNull(TEXT("vehicle"), Vehicle) || !TestNotNull(TEXT("character"), Character)) return false;
	if (!TestTrue(TEXT("enter succeeds"), Vehicle->EnterVehicle(Character))) return false;

	// A thin wall hugging the driver side: the left spot itself is free, but it lies on the far side of the wall.
	DFTests::SpawnBlockingBox(World, FVector(0.f, -140.f, 150.f), FVector(400.f, 15.f, 150.f));

	TestTrue(TEXT("exit succeeds"), Vehicle->ExitVehicle());
	const FVector Delta = Character->GetActorLocation() - Vehicle->GetActorLocation();
	TestTrue(TEXT("character placed on the open side, not through the wall"), Delta.Y >= 150.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFVehicleEnterOccupiedTest, "DeadFire.Vehicle.EnterRefusedWhenOccupied", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFVehicleEnterOccupiedTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector::ZeroVector);
	ADFCharacter* First = DFTests::SpawnAt<ADFCharacter>(World, FVector(0.f, -250.f, CharacterHalfHeight));
	ADFCharacter* Second = DFTests::SpawnAt<ADFCharacter>(World, FVector(0.f, 250.f, CharacterHalfHeight));
	if (!TestNotNull(TEXT("vehicle"), Vehicle) || !TestNotNull(TEXT("first"), First) || !TestNotNull(TEXT("second"), Second)) return false;

	TestTrue(TEXT("first enters"), Vehicle->EnterVehicle(First));
	TestFalse(TEXT("second refused"), Vehicle->EnterVehicle(Second));
	TestFalse(TEXT("second refused via character"), Second->TryEnterVehicle(Vehicle));
	TestEqual(TEXT("occupant is still the first"), Vehicle->Occupant, First);
	TestFalse(TEXT("second not stowed"), Second->bIsStowed);
	return true;
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
