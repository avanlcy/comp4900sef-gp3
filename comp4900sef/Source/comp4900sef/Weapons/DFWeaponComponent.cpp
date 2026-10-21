// Dead Fire - COMP 4900SEF Group 3

#include "Weapons/DFWeaponComponent.h"
#include "CollisionQueryParams.h"
#include "DrawDebugHelpers.h"
#include "Engine/World.h"
#include "GameFramework/DamageType.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"

UDFWeaponComponent::UDFWeaponComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
	Damage = 20.f;
	Range = 8000.f;
	Cooldown = 0.15f;
	bDebugTrace = true;
	DamageTypeClass = UDamageType::StaticClass();
	LastFireTime = -1000.f;
}

bool UDFWeaponComponent::CanFire() const
{
	const UWorld* World = GetWorld();
	return World != nullptr && (World->GetTimeSeconds() - LastFireTime) >= Cooldown;
}

bool UDFWeaponComponent::Fire(const FVector& Origin, const FVector& Direction, FHitResult& OutHit)
{
	UWorld* World = GetWorld();
	if (!World || !CanFire())
	{
		return false;
	}
	LastFireTime = World->GetTimeSeconds();

	const FVector End = Origin + Direction.GetSafeNormal() * Range;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(DFWeaponFire), true, GetOwner());
	if (AActor* Owner = GetOwner())
	{
		// Never hit ourselves or the vehicle we are mounted on / riding in.
		Params.AddIgnoredActor(Owner);
		if (AActor* Parent = Owner->GetAttachParentActor())
		{
			Params.AddIgnoredActor(Parent);
		}
	}

	const bool bHit = World->LineTraceSingleByChannel(OutHit, Origin, End, ECC_Visibility, Params);

	if (bDebugTrace)
	{
		DrawDebugLine(World, Origin, bHit ? OutHit.ImpactPoint : End, bHit ? FColor::Red : FColor::Green, false, 1.f, 0, 1.f);
	}

	if (bHit && OutHit.GetActor())
	{
		AController* InstigatorController = nullptr;
		if (const APawn* OwnerPawn = Cast<APawn>(GetOwner()))
		{
			InstigatorController = OwnerPawn->GetController();
		}
		UGameplayStatics::ApplyPointDamage(OutHit.GetActor(), Damage, Direction, OutHit, InstigatorController, GetOwner(), DamageTypeClass);
	}

	OnFired.Broadcast(OutHit, bHit);
	return bHit;
}
