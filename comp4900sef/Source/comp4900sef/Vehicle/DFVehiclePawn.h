// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "WheeledVehicle.h"
#include "DFVehiclePawn.generated.h"

class UCameraComponent;
class USpringArmComponent;
class ADFCharacter;
class ADFVehiclePawn;

/** Health of one tire. The bone name ties it to the wheel it belongs to. */
USTRUCT(BlueprintType)
struct FDFTireState
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Health")
	FName BoneName;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Health")
	float MaxHealth = 30.f;

	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Health")
	float Health = 30.f;

	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Health")
	bool bBlown = false;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDFVehicleDestroyedSignature, ADFVehiclePawn*, Vehicle, AController*, LastDamageInstigator);

PRAGMA_DISABLE_DEPRECATION_WARNINGS

/**
 * The drivable car. Used by the player (with an on-foot character stowed inside)
 * and by NPC racers (AI controlled, no occupant). Visuals and tuning are set on
 * the Blueprint child BP_DFVehicle.
 */
UCLASS(config = Game)
class COMP4900SEF_API ADFVehiclePawn : public AWheeledVehicle
{
	GENERATED_BODY()

	/** Spring arm for the chase camera. */
	UPROPERTY(Category = "Dead Fire|Camera", VisibleDefaultsOnly, BlueprintReadOnly, meta = (AllowPrivateAccess = "true"))
	USpringArmComponent* SpringArm;

	/** Third-person chase camera. */
	UPROPERTY(Category = "Dead Fire|Camera", VisibleDefaultsOnly, BlueprintReadOnly, meta = (AllowPrivateAccess = "true"))
	UCameraComponent* ChaseCamera;

	/** Origin of the in-car camera. */
	UPROPERTY(Category = "Dead Fire|Camera", VisibleDefaultsOnly, BlueprintReadOnly, meta = (AllowPrivateAccess = "true"))
	USceneComponent* InternalCameraBase;

	/** In-car camera. */
	UPROPERTY(Category = "Dead Fire|Camera", VisibleDefaultsOnly, BlueprintReadOnly, meta = (AllowPrivateAccess = "true"))
	UCameraComponent* InternalCamera;

public:
	ADFVehiclePawn(const FObjectInitializer& ObjectInitializer);

	// ---- Health -------------------------------------------------------------

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Health")
	float MaxHealth;

	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Health")
	float Health;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Health")
	float TireMaxHealth;

	/** Multiplier applied to throttle per blown tire (0.8 = each blown tire costs 20%). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Health", meta = (ClampMin = "0.1", ClampMax = "1.0"))
	float BlownTireSpeedScale;

	/** A point hit within this distance (cm) of a wheel counts as a tire hit even if the bone name is not a wheel. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Health")
	float TireHitRadius;

	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Health")
	TArray<FDFTireState> Tires;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Health")
	bool bIsDestroyed;

	/** Controller that dealt the most recent damage (used for kill credit). */
	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|Health")
	AController* LastDamageInstigator;

	// ---- Enter / exit -------------------------------------------------------

	/** The occupant may only get out below this speed. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Enter Exit")
	float ExitMaxSpeedKPH;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Enter Exit")
	float ExitSideOffset;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Enter Exit")
	float ExitUpOffset;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Enter Exit")
	float ExitBehindOffset;

	/** How far below an exit spot the ground may be (cm); further than this is a drop and the spot is refused. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Enter Exit")
	float ExitGroundSearchDistance;

	/** Capsule used to check that an exit spot is free (matches the on-foot character). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Enter Exit")
	float ExitProbeRadius;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Enter Exit")
	float ExitProbeHalfHeight;

	/** On-foot character currently riding in this vehicle (null for NPC cars). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Enter Exit")
	ADFCharacter* Occupant;

	/** Controller that last drove this car; a parked car still belongs to them for scoring. */
	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Race")
	AController* LastDriver;

	// ---- Camera -------------------------------------------------------------

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Camera")
	bool bInCarCameraActive;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Camera")
	bool bInReverseGear;

	// ---- Queries ------------------------------------------------------------

	UFUNCTION(BlueprintPure, Category = "Dead Fire|Vehicle")
	float GetSpeedKPH() const;

	UFUNCTION(BlueprintPure, Category = "Dead Fire|Vehicle")
	FText GetGearDisplayText() const;

	UFUNCTION(BlueprintPure, Category = "Dead Fire|Health")
	int32 GetBlownTireCount() const;

	/** 1.0 with no blown tires, BlownTireSpeedScale^N with N blown tires. */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|Health")
	float GetThrottleScale() const;

	/** Tire index for a point hit: bone-name match first, then nearest wheel within TireHitRadius, else -1. */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|Health")
	int32 FindTireIndexForHit(FName BoneName, const FVector& ImpactPoint) const;

	UFUNCTION(BlueprintPure, Category = "Dead Fire|Enter Exit")
	bool IsBelowExitSpeed(float KPH) const;

	UFUNCTION(BlueprintPure, Category = "Dead Fire|Enter Exit")
	bool CanBeEntered() const;

	UFUNCTION(BlueprintPure, Category = "Dead Fire|Enter Exit")
	bool CanExit() const;

	/**
	 * Finds a spot beside (left, right) or behind the car that is reachable without passing
	 * through anything, has ground under it, and has room for the character. OutLocation is
	 * where the character's capsule centre goes.
	 */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Enter Exit")
	bool FindExitLocation(FVector& OutLocation) const;

	/** Stows the character inside and hands control to this vehicle. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Enter Exit")
	bool EnterVehicle(ADFCharacter* Character);

	/** Puts the occupant back on the ground beside the car and hands control to them. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Enter Exit")
	bool ExitVehicle();

	/**
	 * Takes the occupant out where it sits (unstowed, no exit spot search) without changing who is
	 * possessed. Used before a wreck is removed. Does nothing without an occupant.
	 */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Enter Exit")
	void EjectOccupant();

	/** Restores full body health and every tire. */
	void ResetHealth();

	// ---- Driving ------------------------------------------------------------

	/** Throttle from -1 (reverse) to 1, scaled down by blown tires. Ignored once the car is wrecked. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Vehicle")
	void MoveForward(float Val);

	/** Steering from -1 (left) to 1. Ignored once the car is wrecked. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Vehicle")
	void MoveRight(float Val);

	/** Parks the car: throttle and steering released, handbrake on. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Vehicle")
	void ReleaseControls();

	/** Puts the car down at the transform's location and rotation, at rest: velocity zeroed, controls released. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Vehicle")
	void TeleportAndStop(const FTransform& Transform);

	virtual float TakeDamage(float DamageAmount, struct FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser) override;

	// ---- Blueprint hooks ----------------------------------------------------

	/** TireIndex is -1 for body damage. */
	UFUNCTION(BlueprintImplementableEvent, Category = "Dead Fire|Events")
	void OnVehicleDamaged(float Damage, int32 TireIndex);

	UFUNCTION(BlueprintImplementableEvent, Category = "Dead Fire|Events")
	void OnTireBlown(int32 TireIndex);

	UFUNCTION(BlueprintImplementableEvent, Category = "Dead Fire|Events")
	void OnVehicleDestroyed();

	UFUNCTION(BlueprintImplementableEvent, Category = "Dead Fire|Events")
	void OnOccupantEntered(ADFCharacter* Character);

	UFUNCTION(BlueprintImplementableEvent, Category = "Dead Fire|Events")
	void OnOccupantExited(ADFCharacter* Character);

	UPROPERTY(BlueprintAssignable, Category = "Dead Fire|Events")
	FDFVehicleDestroyedSignature OnDestroyedDelegate;

	// ---- APawn / AActor -----------------------------------------------------

	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void PostInitializeComponents() override;
	virtual void PossessedBy(AController* NewController) override;

	FORCEINLINE USpringArmComponent* GetSpringArm() const { return SpringArm; }
	FORCEINLINE UCameraComponent* GetChaseCamera() const { return ChaseCamera; }
	FORCEINLINE UCameraComponent* GetInternalCamera() const { return InternalCamera; }

protected:
	virtual void BeginPlay() override;

	void OnHandbrakePressed();
	void OnHandbrakeReleased();
	void OnToggleCamera();
	void OnInteract();

	void EnableInCarView(bool bState, bool bForce = false);
	void ApplyTireDamage(int32 TireIndex, float Damage);
	void ApplyBodyDamage(float Damage);
	void DestroyVehicle();
	FVector GetWheelWorldLocation(int32 TireIndex) const;
	/** Validates one exit candidate (path clear, ground found, room for the capsule) and returns the grounded spot. */
	bool IsExitSpotFree(const FVector& Candidate, FVector& OutGroundedLocation) const;

	static const FName LookUpBinding;
	static const FName LookRightBinding;
};

PRAGMA_ENABLE_DEPRECATION_WARNINGS
