// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "UI/DFHUDSnapshot.h"
#include "DFRaceHUDWidget.generated.h"

class ADFRaceGameMode;
class ADFRaceGameState;
class APawn;
class APlayerController;
class UDFRacerComponent;
class UProgressBar;
class UTextBlock;
class UWidget;

/**
 * The in-race HUD: score, laps, kills and lives top-left, the clock top-centre, speed and gear
 * bottom-right, car or character health bottom-left, the crosshair on foot, the enter/exit prompt
 * and one warning line. Every frame it captures a snapshot from its player and shows it.
 *
 * Without a designer tree it builds its own layout. A Widget Blueprint child can lay the screen out
 * in the designer instead: widgets named like the properties below are picked up and fed the same data.
 */
UCLASS()
class COMP4900SEF_API UDFRaceHUDWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	/** How long "CHECKPOINT +8 s" stays up after a gate is credited. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|HUD")
	float CheckpointFlashSeconds = 1.5f;

	/** The snapshot for a player: its racer, its pawn, the world's race GameState and the race GameMode. */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|HUD")
	static FDFHUDSnapshot CaptureSnapshot(APlayerController* Player, float FlashSeconds);

	/**
	 * The snapshot from explicit inputs, any of which may be null. Prompt in a car: none in a wreck,
	 * "No room to exit" / "[E] Exit vehicle" when slow enough to get out, else "Stop to exit  [E]";
	 * on foot: "[E] Enter vehicle" when alive beside an enterable car. Warning, most important first:
	 * WRECKED, YOU DIED, the off-track countdown, the checkpoint flash.
	 */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|HUD")
	static FDFHUDSnapshot CaptureSnapshotFor(APawn* Pawn, const UDFRacerComponent* Racer, const ADFRaceGameState* State, const ADFRaceGameMode* GameMode, float FlashSeconds);

	/** Writes the snapshot into every element present and shows only the car or the on-foot elements. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|HUD")
	void ApplySnapshot(const FDFHUDSnapshot& Snapshot);

	virtual bool Initialize() override;

	// ---- Elements (bound by name in a Widget Blueprint child) ---------------

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* ScoreText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* LapText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* KillsText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* LivesText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* TimeText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* SpeedText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* GearText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* VehicleHealthText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* TireText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* CharacterHealthText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* CrosshairText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* PromptText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UTextBlock* WarningText = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UProgressBar* VehicleHealthBar = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UProgressBar* CharacterHealthBar = nullptr;

	/** Bottom-left block shown only in a car (car health and tires). */
	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UWidget* VehiclePanel = nullptr;

	/** Bottom-left block shown only on foot (character health). */
	UPROPERTY(BlueprintReadOnly, Category = "Dead Fire|HUD", meta = (BindWidgetOptional))
	UWidget* CharacterPanel = nullptr;

protected:
	virtual void NativeOnInitialized() override;
	virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

private:
	/** Builds the C++ layout on a canvas, unless the widget already has a tree (a designer layout). */
	void BuildDefaultTree();
};
