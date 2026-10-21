// Dead Fire - COMP 4900SEF Group 3

#include "Track/DFCheckpoint.h"
#include "Game/DFRaceGameMode.h"
#include "Vehicle/DFVehiclePawn.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "UObject/ConstructorHelpers.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

ADFCheckpoint::ADFCheckpoint()
{
	PrimaryActorTick.bCanEverTick = false;

	// Phase 2 spec section 7.
	CheckpointIndex = 0;
	TriggerHalfExtent = FVector(100.f, 1400.f, 250.f);
	PoleOffset = 700.f;
	PoleScale = FVector(1.f, 1.f, 6.f);
	RespawnHeightOffset = 50.f;

	Trigger = CreateDefaultSubobject<UBoxComponent>(TEXT("Trigger"));
	Trigger->InitBoxExtent(TriggerHalfExtent);
	Trigger->SetCollisionProfileName(TEXT("Trigger"));
	Trigger->SetGenerateOverlapEvents(true);
	Trigger->OnComponentBeginOverlap.AddDynamic(this, &ADFCheckpoint::OnTriggerBeginOverlap);
	RootComponent = Trigger;

	// Pole from the advanced vehicle template content in /Game/VehicleAdv; the gate works without it.
	static ConstructorHelpers::FObjectFinder<UStaticMesh> PoleMesh(TEXT("/Game/VehicleAdv/ArenaMesh/pole.pole"));
	LeftPole = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("LeftPole"));
	RightPole = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("RightPole"));
	for (UStaticMeshComponent* Pole : { LeftPole, RightPole })
	{
		Pole->SetupAttachment(Trigger);
		Pole->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
		if (PoleMesh.Succeeded())
		{
			Pole->SetStaticMesh(PoleMesh.Object);
		}
	}
	LeftPole->SetRelativeLocation(FVector(0.f, -PoleOffset, 0.f));
	RightPole->SetRelativeLocation(FVector(0.f, PoleOffset, 0.f));
	LeftPole->SetRelativeScale3D(PoleScale);
	RightPole->SetRelativeScale3D(PoleScale);
}

void ADFCheckpoint::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	// Re-applied here so a level designer's edits to the extent, offset or pole scale show up at once.
	Trigger->SetBoxExtent(TriggerHalfExtent);
	LeftPole->SetRelativeLocation(FVector(0.f, -PoleOffset, 0.f));
	RightPole->SetRelativeLocation(FVector(0.f, PoleOffset, 0.f));
	LeftPole->SetRelativeScale3D(PoleScale);
	RightPole->SetRelativeScale3D(PoleScale);
}

void ADFCheckpoint::BeginPlay()
{
	Super::BeginPlay();
	if (ADFRaceGameMode* GameMode = GetWorld()->GetAuthGameMode<ADFRaceGameMode>())
	{
		GameMode->RegisterCheckpoint(this);
	}
}

FTransform ADFCheckpoint::GetRespawnTransform() const
{
	return FTransform(GetActorRotation(), GetActorLocation() + FVector(0.f, 0.f, RespawnHeightOffset));
}

bool ADFCheckpoint::NotifyVehicle(ADFVehiclePawn* Vehicle)
{
	UWorld* World = GetWorld();
	ADFRaceGameMode* GameMode = World ? World->GetAuthGameMode<ADFRaceGameMode>() : nullptr;
	if (!Vehicle || !GameMode)
	{
		return false;
	}
	// A parked car is credited to its last driver until they take another car.
	AController* Racer = Vehicle->GetController() ? Vehicle->GetController() : Vehicle->LastDriver;
	return GameMode->NotifyCheckpointReached(Racer, this);
}

void ADFCheckpoint::OnTriggerBeginOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult)
{
	// Only vehicles trigger checkpoints: a racer on foot cannot score laps.
	if (ADFVehiclePawn* Vehicle = Cast<ADFVehiclePawn>(OtherActor))
	{
		NotifyVehicle(Vehicle);
	}
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS
