// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "DFPlayerController.generated.h"

class ADFCharacter;
class ADFVehiclePawn;
class UDFRacerComponent;

/**
 * The player's controller. Tracks both of the player's pawns (vehicle and on-foot
 * character) across possession swaps and carries the player's race state.
 */
UCLASS()
class COMP4900SEF_API ADFPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	ADFPlayerController();

	/** Score, laps, kills and deaths for this player. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Race")
	UDFRacerComponent* Racer;

	/** The player's on-foot character, whether possessed or stowed in the vehicle. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Enter Exit")
	ADFCharacter* OnFootCharacter;

	/** The vehicle the player last drove (possessed or parked). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Enter Exit")
	ADFVehiclePawn* CurrentVehicle;

	/** Possesses the pawn and remembers it as the current vehicle or character. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Enter Exit")
	void SwitchToPawn(APawn* NewPawn);

protected:
	virtual void OnPossess(APawn* InPawn) override;
};
