// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameStateBase.h"
#include "DFRaceGameState.generated.h"

/** Shared race clock. */
UCLASS()
class COMP4900SEF_API ADFRaceGameState : public AGameStateBase
{
	GENERATED_BODY()

public:
	ADFRaceGameState();

	/** Seconds left before the race ends. */
	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Race")
	float RemainingTime;

	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category = "Dead Fire|Race")
	bool bRaceActive;

	/** Adds (or with a negative value, removes) seconds from the clock. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void AddTime(float Seconds);

	/** Remaining time formatted as m:ss. */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|Race")
	FText GetRemainingTimeText() const;
};
