// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "DFHUDSnapshot.generated.h"

/**
 * Everything the in-race HUD shows, captured from the player once per frame.
 * The HUD widget only reads this, so the capture is the part the tests check.
 */
USTRUCT(BlueprintType)
struct FDFHUDSnapshot
{
	GENERATED_BODY()

	// ---- Race ---------------------------------------------------------------

	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	int32 Score = 0;

	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	int32 Laps = 0;

	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	int32 Kills = 0;

	/** Deaths left before game over: MaxDeaths - Deaths. */
	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	int32 Lives = 0;

	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	float RemainingTime = 0.f;

	/** The clock as m:ss. */
	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	FText TimeText;

	// ---- In a car -----------------------------------------------------------

	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	bool bInVehicle = false;

	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	bool bVehicleDestroyed = false;

	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	bool bInReverse = false;

	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	int32 SpeedKPH = 0;

	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	FText GearText;

	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	float VehicleHealth = 0.f;

	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	float VehicleMaxHealth = 0.f;

	/** Health of each tire, -1 for a blown one. */
	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	TArray<float> TireHealth;

	// ---- On foot ------------------------------------------------------------

	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	bool bOnFoot = false;

	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	bool bCharacterDead = false;

	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	float CharacterHealth = 0.f;

	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	float CharacterMaxHealth = 0.f;

	// ---- Messages -----------------------------------------------------------

	/** Enter/exit prompt; empty when there is none. */
	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	FText PromptText;

	/** The most important warning (wrecked, died, off track, checkpoint); empty when there is none. */
	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	FText WarningText;

	/** Seconds before the off-track reset; -1 when not off track. */
	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	float OffTrackRemaining = -1.f;

	/** Seconds the checkpoint message stays up; -1 when none. */
	UPROPERTY(BlueprintReadWrite, Category = "Dead Fire|HUD")
	float CheckpointFlashRemaining = -1.f;
};
