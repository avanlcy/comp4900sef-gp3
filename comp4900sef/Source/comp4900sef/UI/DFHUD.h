// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "DFHUD.generated.h"

class UFont;

/**
 * Phase 1 canvas HUD: score and clock, vehicle speed/gear/health, on-foot health
 * and crosshair, and the enter/exit prompt. Phase 2 replaces this with UMG.
 */
UCLASS()
class COMP4900SEF_API ADFHUD : public AHUD
{
	GENERATED_BODY()

public:
	ADFHUD();

	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|HUD")
	UFont* HUDFont;

	virtual void DrawHUD() override;

protected:
	void DrawRaceInfo(float Scale);
	void DrawVehicleInfo(float Scale);
	void DrawCharacterInfo(float Scale);
	void DrawPrompt(const FString& Text, float Scale);
};
