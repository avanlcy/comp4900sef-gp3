// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Engine/EngineTypes.h"
#include "DFWeaponComponent.generated.h"

class UDamageType;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDFWeaponFiredSignature, const FHitResult&, Hit, bool, bHit);

/**
 * A hitscan weapon. Owned by the on-foot character in Phase 1; Phase 3 mounts
 * instances on vehicles for the gun and RPG items. Fire() traces from an
 * origin along a direction and applies point damage to whatever it hits.
 */
UCLASS(ClassGroup = (DeadFire), meta = (BlueprintSpawnableComponent))
class COMP4900SEF_API UDFWeaponComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UDFWeaponComponent();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Weapon")
	float Damage;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Weapon")
	float Range;

	/** Seconds between shots. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Weapon")
	float Cooldown;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Weapon")
	bool bDebugTrace;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Weapon")
	TSubclassOf<UDamageType> DamageTypeClass;

	UFUNCTION(BlueprintPure, Category = "Dead Fire|Weapon")
	bool CanFire() const;

	/** Returns true when the shot hit something. Damage goes to the hit actor with the owner's controller as instigator. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Weapon")
	bool Fire(const FVector& Origin, const FVector& Direction, FHitResult& OutHit);

	UFUNCTION(BlueprintPure, Category = "Dead Fire|Weapon")
	float GetLastFireTime() const { return LastFireTime; }

	UPROPERTY(BlueprintAssignable, Category = "Dead Fire|Events")
	FDFWeaponFiredSignature OnFired;

protected:
	float LastFireTime;
};
