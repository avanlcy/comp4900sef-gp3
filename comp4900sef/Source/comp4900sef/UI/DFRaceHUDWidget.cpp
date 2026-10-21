// Dead Fire - COMP 4900SEF Group 3

#include "UI/DFRaceHUDWidget.h"
#include "UI/DFWidgetText.h"
#include "Character/DFCharacter.h"
#include "Game/DFRaceGameMode.h"
#include "Game/DFRaceGameState.h"
#include "Game/DFRacerComponent.h"
#include "Vehicle/DFVehiclePawn.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/ProgressBar.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Styling/CoreStyle.h"

#define LOCTEXT_NAMESPACE "DFRaceHUDWidget"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

using DFWidgetText::SetColorOf;
using DFWidgetText::SetTextOf;
using DFWidgetText::Whole;

namespace
{
	const FLinearColor HUDWhite(1.f, 1.f, 1.f);
	const FLinearColor HUDRed(1.f, 0.12f, 0.08f);
	const FLinearColor HUDYellow(1.f, 0.85f, 0.2f);
	const FLinearColor HUDGreen(0.35f, 1.f, 0.4f);

	/** The off-track countdown fades from yellow to red over its last seconds. */
	const float OffTrackRedSeconds = 5.f;

	/** One decimal, no digit grouping: 2.0. */
	FText OneDecimal(float Value)
	{
		FNumberFormattingOptions Options;
		Options.SetUseGrouping(false).SetMinimumFractionalDigits(1).SetMaximumFractionalDigits(1);
		return FText::AsNumber(Value, &Options);
	}

	// ---- Applying values to elements a designer layout may leave out --------

	void SetBar(UProgressBar* Bar, float Value, float Max)
	{
		if (Bar)
		{
			Bar->SetPercent(Max > 0.f ? FMath::Clamp(Value / Max, 0.f, 1.f) : 0.f);
		}
	}

	/** A HUD never takes clicks, so shown elements are hit-test invisible. */
	void ShowIf(UWidget* Widget, bool bShown)
	{
		if (Widget)
		{
			Widget->SetVisibility(bShown ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
		}
	}

	FLinearColor WarningColor(const FDFHUDSnapshot& Snapshot)
	{
		if (Snapshot.bVehicleDestroyed || Snapshot.bCharacterDead)
		{
			return HUDRed;
		}
		if (Snapshot.OffTrackRemaining >= 0.f)
		{
			return FMath::Lerp(HUDRed, HUDYellow, FMath::Clamp(Snapshot.OffTrackRemaining / OffTrackRedSeconds, 0.f, 1.f));
		}
		return HUDGreen;
	}

	// ---- Building the default layout ----------------------------------------

	UTextBlock* MakeText(UWidgetTree* Tree, FName Name, int32 Size, ETextJustify::Type Justify = ETextJustify::Left)
	{
		UTextBlock* Block = Tree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), Name);
		Block->SetFont(FCoreStyle::GetDefaultFontStyle("Bold", Size));
		Block->SetShadowOffset(FVector2D(1.5f, 1.5f));
		Block->SetShadowColorAndOpacity(FLinearColor(0.f, 0.f, 0.f, 0.8f));
		Block->SetJustification(Justify);
		return Block;
	}

	void AddToBox(UVerticalBox* Box, UWidget* Child, EHorizontalAlignment Align = HAlign_Left, float TopPadding = 0.f)
	{
		UVerticalBoxSlot* BoxSlot = Box->AddChildToVerticalBox(Child);
		BoxSlot->SetHorizontalAlignment(Align);
		BoxSlot->SetPadding(FMargin(0.f, TopPadding, 0.f, 0.f));
	}

	UProgressBar* AddBar(UWidgetTree* Tree, UVerticalBox* Box, FName Name, const FLinearColor& Fill)
	{
		USizeBox* Frame = Tree->ConstructWidget<USizeBox>(USizeBox::StaticClass(), *(Name.ToString() + TEXT("Frame")));
		Frame->SetWidthOverride(280.f);
		Frame->SetHeightOverride(12.f);
		UProgressBar* Bar = Tree->ConstructWidget<UProgressBar>(UProgressBar::StaticClass(), Name);
		Bar->SetFillColorAndOpacity(Fill);
		Frame->AddChild(Bar);
		AddToBox(Box, Frame, HAlign_Left, 4.f);
		return Bar;
	}

	/** Pins the widget to an anchor point of the screen at its desired size. */
	void Place(UCanvasPanel* Canvas, UWidget* Widget, const FVector2D& Anchor, const FVector2D& Alignment, const FVector2D& Offset)
	{
		UCanvasPanelSlot* CanvasSlot = Canvas->AddChildToCanvas(Widget);
		CanvasSlot->SetAnchors(FAnchors(Anchor.X, Anchor.Y));
		CanvasSlot->SetAlignment(Alignment);
		CanvasSlot->SetPosition(Offset);
		CanvasSlot->SetAutoSize(true);
	}
}

// ---- Snapshot ---------------------------------------------------------------

FDFHUDSnapshot UDFRaceHUDWidget::CaptureSnapshot(APlayerController* Player, float FlashSeconds)
{
	UWorld* World = Player ? Player->GetWorld() : nullptr;
	const ADFRaceGameState* State = World ? World->GetGameState<ADFRaceGameState>() : nullptr;
	const ADFRaceGameMode* GameMode = World ? World->GetAuthGameMode<ADFRaceGameMode>() : nullptr;
	if (!GameMode && World)
	{
		// Editor worlds (the automation tests) have no authority GameMode; use the one placed in the world.
		TActorIterator<ADFRaceGameMode> It(World);
		GameMode = It ? *It : nullptr;
	}
	return CaptureSnapshotFor(Player ? Player->GetPawn() : nullptr, UDFRacerComponent::FindOn(Player), State, GameMode, FlashSeconds);
}

FDFHUDSnapshot UDFRaceHUDWidget::CaptureSnapshotFor(APawn* Pawn, const UDFRacerComponent* Racer, const ADFRaceGameState* State, const ADFRaceGameMode* GameMode, float FlashSeconds)
{
	FDFHUDSnapshot Snapshot;

	// ---- Race ----
	if (Racer)
	{
		Snapshot.Score = Racer->Score;
		Snapshot.Laps = Racer->LapsCompleted;
		Snapshot.Kills = Racer->Kills;
	}
	if (GameMode)
	{
		Snapshot.Lives = FMath::Max(0, GameMode->MaxDeaths - (Racer ? Racer->Deaths : 0));
	}
	if (State)
	{
		Snapshot.RemainingTime = State->RemainingTime;
		Snapshot.TimeText = State->GetRemainingTimeText();
	}
	else
	{
		Snapshot.TimeText = LOCTEXT("NoClock", "--:--");
	}
	if (Racer && GameMode && Racer->OffTrackSeconds > 0.f)
	{
		Snapshot.OffTrackRemaining = FMath::Max(0.f, GameMode->OffTrackGraceSeconds - Racer->OffTrackSeconds);
	}
	const UWorld* World = Racer ? Racer->GetWorld() : nullptr;
	if (World && Racer->LastCheckpointTime >= 0.f)
	{
		const float SinceCheckpoint = World->GetTimeSeconds() - Racer->LastCheckpointTime;
		if (SinceCheckpoint >= 0.f && SinceCheckpoint < FlashSeconds)
		{
			Snapshot.CheckpointFlashRemaining = FlashSeconds - SinceCheckpoint;
		}
	}

	// ---- Pawn ----
	if (const ADFVehiclePawn* Vehicle = Cast<ADFVehiclePawn>(Pawn))
	{
		Snapshot.bInVehicle = true;
		Snapshot.bVehicleDestroyed = Vehicle->bIsDestroyed;
		Snapshot.bInReverse = Vehicle->bInReverseGear;
		Snapshot.SpeedKPH = FMath::FloorToInt(Vehicle->GetSpeedKPH());
		Snapshot.GearText = Vehicle->GetGearDisplayText();
		Snapshot.VehicleHealth = Vehicle->Health;
		Snapshot.VehicleMaxHealth = Vehicle->MaxHealth;
		for (const FDFTireState& Tire : Vehicle->Tires)
		{
			Snapshot.TireHealth.Add(Tire.bBlown ? -1.f : Tire.Health);
		}

		if (Vehicle->bIsDestroyed)
		{
			// A wreck offers nothing; the warning line says WRECKED.
		}
		else if (Vehicle->CanExit())
		{
			FVector ExitLocation;
			Snapshot.PromptText = Vehicle->FindExitLocation(ExitLocation)
				? LOCTEXT("ExitPrompt", "[E] Exit vehicle")
				: LOCTEXT("NoRoomPrompt", "No room to exit");
		}
		else if (Vehicle->Occupant)
		{
			Snapshot.PromptText = LOCTEXT("StopPrompt", "Stop to exit  [E]");
		}
	}
	else if (const ADFCharacter* Character = Cast<ADFCharacter>(Pawn))
	{
		Snapshot.bOnFoot = true;
		Snapshot.bCharacterDead = Character->IsDead();
		Snapshot.CharacterHealth = Character->Health;
		Snapshot.CharacterMaxHealth = Character->MaxHealth;
		if (!Snapshot.bCharacterDead && Character->FindNearestEnterableVehicle())
		{
			Snapshot.PromptText = LOCTEXT("EnterPrompt", "[E] Enter vehicle");
		}
	}

	// ---- Warning, most important first ----
	if (Snapshot.bVehicleDestroyed)
	{
		Snapshot.WarningText = LOCTEXT("Wrecked", "WRECKED");
	}
	else if (Snapshot.bCharacterDead)
	{
		Snapshot.WarningText = LOCTEXT("Died", "YOU DIED");
	}
	else if (Snapshot.OffTrackRemaining >= 0.f)
	{
		Snapshot.WarningText = FText::Format(LOCTEXT("OffTrack", "RETURN TO TRACK  {0}"), OneDecimal(Snapshot.OffTrackRemaining));
	}
	else if (Snapshot.CheckpointFlashRemaining >= 0.f)
	{
		Snapshot.WarningText = GameMode
			? FText::Format(LOCTEXT("CheckpointBonus", "CHECKPOINT  +{0} s"), FText::AsNumber(GameMode->CheckpointTimeBonus, &FNumberFormattingOptions::DefaultNoGrouping()))
			: LOCTEXT("Checkpoint", "CHECKPOINT");
	}
	return Snapshot;
}

// ---- Display ----------------------------------------------------------------

void UDFRaceHUDWidget::ApplySnapshot(const FDFHUDSnapshot& Snapshot)
{
	SetTextOf(ScoreText, FText::Format(LOCTEXT("Score", "SCORE {0}"), Whole(Snapshot.Score)));
	SetTextOf(LapText, FText::Format(LOCTEXT("Laps", "LAPS {0}"), Whole(Snapshot.Laps)));
	SetTextOf(KillsText, FText::Format(LOCTEXT("Kills", "KILLS {0}"), Whole(Snapshot.Kills)));
	SetTextOf(LivesText, FText::Format(LOCTEXT("Lives", "LIVES {0}"), Whole(Snapshot.Lives)));
	SetTextOf(TimeText, Snapshot.TimeText);
	SetColorOf(TimeText, Snapshot.RemainingTime < 10.f ? HUDRed : HUDWhite);

	// In a car: speed and gear bottom-right, car health and tires bottom-left.
	ShowIf(SpeedText, Snapshot.bInVehicle);
	ShowIf(GearText, Snapshot.bInVehicle);
	ShowIf(VehiclePanel, Snapshot.bInVehicle);
	SetTextOf(SpeedText, FText::Format(LOCTEXT("Speed", "{0} km/h"), Whole(Snapshot.SpeedKPH)));
	SetTextOf(GearText, FText::Format(LOCTEXT("Gear", "GEAR {0}"), Snapshot.GearText));
	SetColorOf(GearText, Snapshot.bInReverse ? HUDRed : HUDWhite);
	SetTextOf(VehicleHealthText, FText::Format(LOCTEXT("CarHealth", "CAR {0} / {1}"),
		Whole(FMath::CeilToInt(Snapshot.VehicleHealth)), Whole(FMath::CeilToInt(Snapshot.VehicleMaxHealth))));
	SetBar(VehicleHealthBar, Snapshot.VehicleHealth, Snapshot.VehicleMaxHealth);
	TArray<FString> Tires;
	for (const float Tire : Snapshot.TireHealth)
	{
		Tires.Add(Tire < 0.f ? FString(TEXT("[X]")) : FString::Printf(TEXT("[%d]"), FMath::CeilToInt(Tire)));
	}
	SetTextOf(TireText, FText::Format(LOCTEXT("Tires", "TIRES {0}"), FText::FromString(FString::Join(Tires, TEXT(" ")))));

	// On foot: character health bottom-left and the crosshair.
	ShowIf(CharacterPanel, Snapshot.bOnFoot);
	ShowIf(CrosshairText, Snapshot.bOnFoot);
	SetTextOf(CharacterHealthText, FText::Format(LOCTEXT("CharacterHealth", "HEALTH {0} / {1}"),
		Whole(FMath::CeilToInt(Snapshot.CharacterHealth)), Whole(FMath::CeilToInt(Snapshot.CharacterMaxHealth))));
	SetBar(CharacterHealthBar, Snapshot.CharacterHealth, Snapshot.CharacterMaxHealth);

	SetTextOf(PromptText, Snapshot.PromptText);
	SetTextOf(WarningText, Snapshot.WarningText);
	SetColorOf(WarningText, WarningColor(Snapshot));
}

// ---- UUserWidget ------------------------------------------------------------

bool UDFRaceHUDWidget::Initialize()
{
	const bool bFirstTime = Super::Initialize();
	// The engine calls NativeOnInitialized only for a widget with a local player. One made for a bare
	// world (the automation tests) still needs its layout, so build it here too; it is built only once.
	if (bFirstTime && !IsDesignTime())
	{
		BuildDefaultTree();
	}
	return bFirstTime;
}

void UDFRaceHUDWidget::NativeOnInitialized()
{
	BuildDefaultTree();
	Super::NativeOnInitialized();
}

void UDFRaceHUDWidget::NativeTick(const FGeometry& MyGeometry, float InDeltaTime)
{
	Super::NativeTick(MyGeometry, InDeltaTime);
	ApplySnapshot(CaptureSnapshot(GetOwningPlayer(), CheckpointFlashSeconds));
}

void UDFRaceHUDWidget::BuildDefaultTree()
{
	if (!WidgetTree || WidgetTree->RootWidget)
	{
		return;
	}

	UCanvasPanel* Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("HUDRoot"));
	Root->SetVisibility(ESlateVisibility::HitTestInvisible);
	WidgetTree->RootWidget = Root;

	// Top-left: score, completed laps, kills, lives.
	UVerticalBox* Stats = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("StatsPanel"));
	ScoreText = MakeText(WidgetTree, TEXT("ScoreText"), 26);
	LapText = MakeText(WidgetTree, TEXT("LapText"), 20);
	KillsText = MakeText(WidgetTree, TEXT("KillsText"), 20);
	LivesText = MakeText(WidgetTree, TEXT("LivesText"), 20);
	AddToBox(Stats, ScoreText);
	AddToBox(Stats, LapText, HAlign_Left, 2.f);
	AddToBox(Stats, KillsText, HAlign_Left, 2.f);
	AddToBox(Stats, LivesText, HAlign_Left, 2.f);
	Place(Root, Stats, FVector2D(0.f, 0.f), FVector2D(0.f, 0.f), FVector2D(32.f, 24.f));

	// Top-centre: the clock.
	TimeText = MakeText(WidgetTree, TEXT("TimeText"), 40, ETextJustify::Center);
	Place(Root, TimeText, FVector2D(0.5f, 0.f), FVector2D(0.5f, 0.f), FVector2D(0.f, 20.f));

	// Bottom-right: speed and gear.
	UVerticalBox* Drive = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("DrivePanel"));
	SpeedText = MakeText(WidgetTree, TEXT("SpeedText"), 44, ETextJustify::Right);
	GearText = MakeText(WidgetTree, TEXT("GearText"), 26, ETextJustify::Right);
	AddToBox(Drive, SpeedText, HAlign_Right);
	AddToBox(Drive, GearText, HAlign_Right);
	Place(Root, Drive, FVector2D(1.f, 1.f), FVector2D(1.f, 1.f), FVector2D(-32.f, -28.f));

	// Bottom-left, in a car: car health and tires.
	UVerticalBox* Car = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("VehiclePanel"));
	VehicleHealthText = MakeText(WidgetTree, TEXT("VehicleHealthText"), 22);
	TireText = MakeText(WidgetTree, TEXT("TireText"), 20);
	AddToBox(Car, VehicleHealthText);
	VehicleHealthBar = AddBar(WidgetTree, Car, TEXT("VehicleHealthBar"), FLinearColor(1.f, 0.55f, 0.1f));
	AddToBox(Car, TireText, HAlign_Left, 6.f);
	Place(Root, Car, FVector2D(0.f, 1.f), FVector2D(0.f, 1.f), FVector2D(32.f, -28.f));
	VehiclePanel = Car;

	// Bottom-left, on foot: character health.
	UVerticalBox* Foot = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("CharacterPanel"));
	CharacterHealthText = MakeText(WidgetTree, TEXT("CharacterHealthText"), 22);
	AddToBox(Foot, CharacterHealthText);
	CharacterHealthBar = AddBar(WidgetTree, Foot, TEXT("CharacterHealthBar"), FLinearColor(0.3f, 0.9f, 0.35f));
	Place(Root, Foot, FVector2D(0.f, 1.f), FVector2D(0.f, 1.f), FVector2D(32.f, -28.f));
	CharacterPanel = Foot;

	// Centre: the crosshair (on foot only).
	CrosshairText = MakeText(WidgetTree, TEXT("CrosshairText"), 28, ETextJustify::Center);
	CrosshairText->SetText(FText::FromString(TEXT("+")));
	Place(Root, CrosshairText, FVector2D(0.5f, 0.5f), FVector2D(0.5f, 0.5f), FVector2D::ZeroVector);

	// The prompt line at 72 % of the height, the warning line at 40 %.
	PromptText = MakeText(WidgetTree, TEXT("PromptText"), 28, ETextJustify::Center);
	SetColorOf(PromptText, HUDYellow);
	Place(Root, PromptText, FVector2D(0.5f, 0.72f), FVector2D(0.5f, 0.5f), FVector2D::ZeroVector);
	WarningText = MakeText(WidgetTree, TEXT("WarningText"), 44, ETextJustify::Center);
	Place(Root, WarningText, FVector2D(0.5f, 0.40f), FVector2D(0.5f, 0.5f), FVector2D::ZeroVector);
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS

#undef LOCTEXT_NAMESPACE
