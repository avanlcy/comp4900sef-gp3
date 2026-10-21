// Dead Fire - COMP 4900SEF Group 3
// Shared helpers for the DeadFire.* editor automation tests.

#pragma once

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "CoreMinimal.h"
#include "Engine/World.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Components/StaticMeshComponent.h"
#include "Tests/AutomationEditorCommon.h"
#include "UObject/ConstructorHelpers.h"

namespace DFTests
{
	/** A fresh, empty editor world for each test so actors never leak between tests. */
	inline UWorld* NewTestWorld()
	{
		return FAutomationEditorCommonUtils::CreateNewMap();
	}

	template <class T>
	T* SpawnAt(UWorld* World, const FVector& Location, const FRotator& Rotation = FRotator::ZeroRotator, UClass* Class = nullptr)
	{
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		return World->SpawnActor<T>(Class ? Class : T::StaticClass(), Location, Rotation, Params);
	}

	/**
	 * Spawns deferred so class-default properties can be changed before PostInitializeComponents,
	 * the way a Blueprint child's defaults would be applied. Call FinishSpawning on the result.
	 */
	template <class T>
	T* SpawnDeferredAt(UWorld* World, const FVector& Location)
	{
		return World->SpawnActorDeferred<T>(T::StaticClass(), FTransform(Location), nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
	}

	/** Spawns a solid, blocking box (engine basic cube) with the given half-extents in cm. */
	inline AStaticMeshActor* SpawnBlockingBox(UWorld* World, const FVector& Center, const FVector& HalfExtent)
	{
		AStaticMeshActor* Box = SpawnAt<AStaticMeshActor>(World, Center);
		if (Box)
		{
			UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
			UStaticMeshComponent* Comp = Box->GetStaticMeshComponent();
			Comp->SetMobility(EComponentMobility::Movable);
			Comp->SetStaticMesh(Mesh);
			Comp->SetCollisionProfileName(TEXT("BlockAll"));
			Box->SetActorScale3D(HalfExtent * 2.f / 100.f);
		}
		return Box;
	}

	/** Spawns a solid, blocking cube scaled to the given size in cm. */
	inline AStaticMeshActor* SpawnBlockingCube(UWorld* World, const FVector& Location, float SizeCm)
	{
		return SpawnBlockingBox(World, Location, FVector(SizeCm * 0.5f));
	}

	/** A large floor whose top surface is at Z = 0 around the given centre. */
	inline AStaticMeshActor* SpawnFloor(UWorld* World, const FVector& Center = FVector::ZeroVector, float SizeCm = 20000.f)
	{
		return SpawnBlockingBox(World, Center + FVector(0.f, 0.f, -50.f), FVector(SizeCm * 0.5f, SizeCm * 0.5f, 50.f));
	}
}

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
