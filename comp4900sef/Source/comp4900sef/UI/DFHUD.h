// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "DFHUD.generated.h"

class UDFRaceHUDWidget;
class UDFRaceSummaryWidget;

/**
 * The player's HUD. Draws nothing on the canvas: when play starts it puts the in-race UMG widget
 * on screen, and the GameMode asks it for the summary once the race is over.
 */
UCLASS()
class COMP4900SEF_API ADFHUD : public AHUD
{
	GENERATED_BODY()

public:
	ADFHUD();

	/** In-race widget; a Widget Blueprint child of UDFRaceHUDWidget can replace the built-in layout. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|HUD")
	TSubclassOf<UDFRaceHUDWidget> HUDWidgetClass;

	/** The in-race widget on screen, created in BeginPlay. */
	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD")
	UDFRaceHUDWidget* HUDWidget;

	/** End-of-race summary; a Widget Blueprint child of UDFRaceSummaryWidget can replace the built-in layout. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|HUD")
	TSubclassOf<UDFRaceSummaryWidget> SummaryWidgetClass;

	/** The summary on screen, created the first time ShowSummary runs. */
	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD")
	UDFRaceSummaryWidget* SummaryWidget;

	/**
	 * Shows the end-of-race summary over the game, filled from the race GameState's result, hides the
	 * in-race widget and hands the mouse to the UI. Called by the GameMode once the race is over.
	 */
	virtual void ShowSummary();

	/** True once the summary is on screen. */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|HUD")
	bool IsSummaryShown() const;

protected:
	virtual void BeginPlay() override;
};
