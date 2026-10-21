// Dead Fire - COMP 4900SEF Group 3
// Editor automation tests for UDFWeaponComponent and ADFCharacter.

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "DFTestUtils.h"
#include "Character/DFCharacter.h"
#include "Vehicle/DFVehiclePawn.h"
#include "Weapons/DFWeaponComponent.h"
#include "Camera/CameraComponent.h"
#include "CollisionQueryParams.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/EngineTypes.h"
#include "GameFramework/DamageType.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFWeaponHitscanTest, "DeadFire.Weapon.HitscanDamagesVehicle", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFWeaponHitscanTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector(400.f, 0.f, 0.f));
	ADFCharacter* Character = DFTests::SpawnAt<ADFCharacter>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("vehicle"), Vehicle) || !TestNotNull(TEXT("character"), Character)) return false;

	FHitResult Hit;
	const bool bHit = Character->GetWeapon()->Fire(FVector(0.f, 0.f, 100.f), FVector::ForwardVector, Hit);

	TestTrue(TEXT("shot hit something"), bHit);
	TestEqual(TEXT("hit the vehicle"), Hit.GetActor(), static_cast<AActor*>(Vehicle));
	TestEqual(TEXT("vehicle lost 20 health"), Vehicle->Health, 80.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFWeaponCooldownTest, "DeadFire.Weapon.RespectsCooldown", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFWeaponCooldownTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector(400.f, 0.f, 0.f));
	ADFCharacter* Character = DFTests::SpawnAt<ADFCharacter>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("vehicle"), Vehicle) || !TestNotNull(TEXT("character"), Character)) return false;

	FHitResult Hit;
	TestTrue(TEXT("can fire initially"), Character->GetWeapon()->CanFire());
	TestTrue(TEXT("first shot hits"), Character->GetWeapon()->Fire(FVector(0.f, 0.f, 100.f), FVector::ForwardVector, Hit));
	TestFalse(TEXT("cooling down"), Character->GetWeapon()->CanFire());
	TestFalse(TEXT("second immediate shot refused"), Character->GetWeapon()->Fire(FVector(0.f, 0.f, 100.f), FVector::ForwardVector, Hit));
	TestEqual(TEXT("vehicle damaged only once"), Vehicle->Health, 80.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFCharacterFireTest, "DeadFire.Character.FireUsesCameraDirection", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFCharacterFireTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector(400.f, 0.f, 0.f));
	// Standing on the ground: the capsule centre sits one half-height (96 cm) above Z 0, like in play.
	ADFCharacter* Character = DFTests::SpawnAt<ADFCharacter>(World, FVector(0.f, 0.f, 96.f), FRotator::ZeroRotator);
	if (!TestNotNull(TEXT("vehicle"), Vehicle) || !TestNotNull(TEXT("character"), Character)) return false;

	const FVector CameraLocation = Character->GetFollowCamera()->GetComponentLocation();
	AddInfo(FString::Printf(TEXT("camera at %s forward %s; vehicle bounds origin %s extent %s"),
		*CameraLocation.ToString(), *Character->GetFollowCamera()->GetForwardVector().ToString(),
		*Vehicle->GetMesh()->Bounds.Origin.ToString(), *Vehicle->GetMesh()->Bounds.BoxExtent.ToString()));
	TestTrue(TEXT("camera sits behind the character"), CameraLocation.X < 0.f);
	TestTrue(TEXT("fire hits the vehicle ahead"), Character->Fire());
	TestTrue(TEXT("vehicle took damage"), Vehicle->Health < 100.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFCharacterDiesTest, "DeadFire.Character.DiesAtZeroHealth", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFCharacterDiesTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFCharacter* Character = DFTests::SpawnAt<ADFCharacter>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("character"), Character)) return false;

	FDamageEvent Generic(UDamageType::StaticClass());
	TestFalse(TEXT("alive at start"), Character->IsDead());
	TestEqual(TEXT("damage applied"), Character->TakeDamage(100.f, Generic, nullptr, nullptr), 100.f);
	TestEqual(TEXT("health is zero"), Character->Health, 0.f);
	TestTrue(TEXT("dead"), Character->IsDead());
	TestEqual(TEXT("damage after death ignored"), Character->TakeDamage(10.f, Generic, nullptr, nullptr), 0.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFCharacterTraceTargetTest, "DeadFire.Character.InteractionSphereDoesNotBlockTraces", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFCharacterTraceTargetTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFCharacter* Character = DFTests::SpawnAt<ADFCharacter>(World, FVector(0.f, 0.f, 96.f));
	if (!TestNotNull(TEXT("character"), Character)) return false;

	// A shot at the character must hit the body, not an invisible 3 m bubble around it.
	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(DFTestTrace), false);
	const bool bHit = World->LineTraceSingleByChannel(Hit, FVector(-1000.f, 0.f, 96.f), FVector(1000.f, 0.f, 96.f), ECC_Visibility, Params);
	TestTrue(TEXT("visibility trace hits the character"), bHit);
	if (bHit)
	{
		TestEqual(TEXT("hit actor is the character"), Hit.GetActor(), static_cast<AActor*>(Character));
		TestTrue(TEXT("hit on the body, not metres away"), Hit.ImpactPoint.X >= -60.f && Hit.ImpactPoint.X <= 0.f);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFCharacterBlueprintDefaultsTest, "DeadFire.Character.BlueprintDefaultsSetStartingHealth", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFCharacterBlueprintDefaultsTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFCharacter* Character = DFTests::SpawnDeferredAt<ADFCharacter>(World, FVector(0.f, 0.f, 96.f));
	if (!TestNotNull(TEXT("character"), Character)) return false;
	Character->MaxHealth = 150.f;
	Character->FinishSpawning(FTransform(FVector(0.f, 0.f, 96.f)));
	// Editor worlds never initialise actors for play, so run the hook a game world would run here.
	Character->PostInitializeComponents();

	TestEqual(TEXT("starting health follows MaxHealth"), Character->Health, 150.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFCharacterNearestVehicleTest, "DeadFire.Character.FindsNearestVehicle", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFCharacterNearestVehicleTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFCharacter* Character = DFTests::SpawnAt<ADFCharacter>(World, FVector::ZeroVector);
	ADFVehiclePawn* Far = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector(900.f, 0.f, 0.f));
	ADFVehiclePawn* Near = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector(250.f, 0.f, 0.f));
	if (!TestNotNull(TEXT("character"), Character) || !TestNotNull(TEXT("near"), Near) || !TestNotNull(TEXT("far"), Far)) return false;

	TestEqual(TEXT("nearest enterable vehicle"), Character->FindNearestEnterableVehicle(), Near);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFCharacterNoVehicleInRangeTest, "DeadFire.Character.NoVehicleOutOfRange", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFCharacterNoVehicleInRangeTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFCharacter* Character = DFTests::SpawnAt<ADFCharacter>(World, FVector::ZeroVector);
	ADFVehiclePawn* Vehicle = DFTests::SpawnAt<ADFVehiclePawn>(World, FVector(900.f, 0.f, 0.f));
	if (!TestNotNull(TEXT("character"), Character) || !TestNotNull(TEXT("vehicle"), Vehicle)) return false;

	TestNull(TEXT("nothing within 300 cm"), Character->FindNearestEnterableVehicle());
	TestFalse(TEXT("TryEnterVehicle fails with nothing in range"), Character->TryEnterVehicle(nullptr));
	return true;
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
