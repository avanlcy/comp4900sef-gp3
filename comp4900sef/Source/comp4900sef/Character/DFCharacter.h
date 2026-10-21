// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "DFCharacter.generated.h"

class ADFVehiclePawn;
class UCameraComponent;
class USpringArmComponent;
class USphereComponent;
class UDFWeaponComponent;

/**
 * The on-foot player: walks, jumps, shoots, and enters vehicles.
 * Visuals (Mannequin) are set in C++; tunables are exposed to the Blueprint child BP_DFCharacter.
 */
UCLASS(config = Game)
class COMP4900SEF_API ADFCharacter : public ACharacter
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Camera", meta = (AllowPrivateAccess = "true"))
	USpringArmComponent* CameraBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Camera", meta = (AllowPrivateAccess = "true"))
	UCameraComponent* FollowCamera;

	/** Radius within which a vehicle can be entered. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Enter Exit", meta = (AllowPrivateAccess = "true"))
	USphereComponent* InteractionSphere;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Weapon", meta = (AllowPrivateAccess = "true"))
	UDFWeaponComponent* Weapon;

public:
	ADFCharacter();

	// ---- Health -------------------------------------------------------------

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Health")
	float MaxHealth;

	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Health")
	float Health;

	// ---- Camera -------------------------------------------------------------

	/** Gamepad turn rate, degrees per second. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Camera")
	float BaseTurnRate;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Camera")
	float BaseLookUpRate;

	// ---- State --------------------------------------------------------------

	/** Vehicle this character is riding in, or null when on foot. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Enter Exit")
	ADFVehiclePawn* CurrentVehicle;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Enter Exit")
	bool bIsStowed;

	// ---- Queries / actions --------------------------------------------------

	UFUNCTION(BlueprintPure, Category = "Dead Fire|Enter Exit")
	bool IsInVehicle() const;

	UFUNCTION(BlueprintPure, Category = "Dead Fire|Health")
	bool IsDead() const;

	/** Closest vehicle within the interaction radius that can be entered, or null. */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|Enter Exit")
	ADFVehiclePawn* FindNearestEnterableVehicle() const;

	/** Enters the given vehicle, or the nearest enterable one when null. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Enter Exit")
	bool TryEnterVehicle(ADFVehiclePawn* Vehicle = nullptr);

	/** Hides, disables and attaches the character (stowed) or restores it (unstowed). Called by the vehicle. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Enter Exit")
	void SetStowed(bool bStowed, AActor* AttachTo);

	/** Fires the weapon from the camera along the view direction. Returns true on a hit. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Weapon")
	bool Fire();

	virtual float TakeDamage(float DamageAmount, struct FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser) override;

	// ---- Blueprint hooks ----------------------------------------------------

	UFUNCTION(BlueprintImplementableEvent, Category = "Dead Fire|Events")
	void OnCharacterDamaged(float Damage);

	UFUNCTION(BlueprintImplementableEvent, Category = "Dead Fire|Events")
	void OnCharacterDied();

	UFUNCTION(BlueprintImplementableEvent, Category = "Dead Fire|Events")
	void OnEnteredVehicle(ADFVehiclePawn* Vehicle);

	UFUNCTION(BlueprintImplementableEvent, Category = "Dead Fire|Events")
	void OnExitedVehicle(ADFVehiclePawn* Vehicle);

	// ---- APawn --------------------------------------------------------------

	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void PostInitializeComponents() override;

	FORCEINLINE USpringArmComponent* GetCameraBoom() const { return CameraBoom; }
	FORCEINLINE UCameraComponent* GetFollowCamera() const { return FollowCamera; }
	FORCEINLINE USphereComponent* GetInteractionSphere() const { return InteractionSphere; }
	FORCEINLINE UDFWeaponComponent* GetWeapon() const { return Weapon; }

protected:
	void MoveForward(float Value);
	void MoveRight(float Value);
	void TurnAtRate(float Rate);
	void LookUpAtRate(float Rate);
	void OnInteract();
	void OnFire();
};
