// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Game/DFRaceGameState.h"
#include "DFRaceSummaryWidget.generated.h"

class UButton;
class UTextBlock;

/**
 * The end-of-race screen: the outcome as a title, the player's place, the score against the
 * requirement with laps, kills and deaths, and the RETRY (reload the level) and QUIT buttons.
 *
 * Without a designer tree it builds its own layout. A Widget Blueprint child can lay the screen out
 * in the designer instead: widgets named like the properties below are picked up, filled and wired.
 */
UCLASS()
class COMP4900SEF_API UDFRaceSummaryWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	/** RACE COMPLETE when the player passed, GAME OVER at the death limit, otherwise TIME UP. */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|HUD")
	static FText TitleFor(const FDFRaceResult& Result);

	/** Writes the title, the place line and the stats line into every element present. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|HUD")
	void ShowResults(const FDFRaceResult& Result);

	/** RETRY: reloads the current level. */
	UFUNCTION()
	void HandleRetry();

	/** QUIT: quits the game. */
	UFUNCTION()
	void HandleQuit();

	virtual bool Initialize() override;

	// ---- Elements (bound by name in a Widget Blueprint child) ---------------

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* TitleText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* PlaceText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* StatsText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UButton* RetryButton = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UButton* QuitButton = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* RetryLabel = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* QuitLabel = nullptr;

protected:
	/** Builds the default tree if needed, then wires RETRY and QUIT to their handlers. */
	virtual void NativeOnInitialized() override;

private:
	/** Builds the C++ layout on a canvas, unless the widget already has a tree (a designer layout). */
	void BuildDefaultTree();
};
