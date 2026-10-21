// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameStateBase.h"
#include "DFRaceGameState.generated.h"

/** Why the race ended. */
UENUM(BlueprintType)
enum class EDFRaceEndReason : uint8
{
	None,
	TimeUp,
	DeathLimit
};

/** The player's result, recorded when the race ends; the summary screen shows it. */
USTRUCT(BlueprintType)
struct FDFRaceResult
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|Race")
	EDFRaceEndReason Reason = EDFRaceEndReason::None;

	/** Time ran out with the score requirement met. A death-limit end never passes. */
	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|Race")
	bool bPassed = false;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|Race")
	int32 Score = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|Race")
	int32 ScoreRequirement = 0;

	/** The player's place among all racers, 1 = first. */
	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|Race")
	int32 Rank = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|Race")
	int32 RacerCount = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|Race")
	int32 Laps = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|Race")
	int32 Kills = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|Race")
	int32 Deaths = 0;
};

/** Shared race clock and, once the race is over, the player's result. */
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

	/** Filled by the GameMode when the race ends; Reason stays None while it runs. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Race")
	FDFRaceResult Result;

	/** Adds (or with a negative value, removes) seconds from the clock. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Race")
	void AddTime(float Seconds);

	/** Remaining time formatted as m:ss. */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|Race")
	FText GetRemainingTimeText() const;
};
