// Dead Fire - COMP 4900SEF Group 3

#include "UI/DFRaceSummaryWidget.h"
#include "UI/DFWidgetText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/Button.h"
#include "Components/ButtonSlot.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Styling/CoreStyle.h"

#define LOCTEXT_NAMESPACE "DFRaceSummaryWidget"

using DFWidgetText::SetColorOf;
using DFWidgetText::SetTextOf;
using DFWidgetText::Whole;

namespace
{
	const FLinearColor SummaryGreen(0.35f, 1.f, 0.4f);
	const FLinearColor SummaryRed(1.f, 0.12f, 0.08f);
	const FLinearColor PanelColor(0.02f, 0.02f, 0.025f, 0.88f);
	const FLinearColor ButtonColor(0.7f, 0.18f, 0.08f);

	// ---- Building the default layout ----------------------------------------

	UTextBlock* MakeText(UWidgetTree* Tree, FName Name, int32 Size)
	{
		UTextBlock* Block = Tree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), Name);
		Block->SetFont(FCoreStyle::GetDefaultFontStyle("Bold", Size));
		Block->SetShadowOffset(FVector2D(1.5f, 1.5f));
		Block->SetShadowColorAndOpacity(FLinearColor(0.f, 0.f, 0.f, 0.8f));
		Block->SetJustification(ETextJustify::Center);
		return Block;
	}

	void AddToBox(UVerticalBox* Box, UWidget* Child, float TopPadding)
	{
		UVerticalBoxSlot* BoxSlot = Box->AddChildToVerticalBox(Child);
		BoxSlot->SetHorizontalAlignment(HAlign_Center);
		BoxSlot->SetPadding(FMargin(0.f, TopPadding, 0.f, 0.f));
	}

	/** A button holding a centred label, added to the row with a gap on either side. */
	UButton* AddButton(UWidgetTree* Tree, UHorizontalBox* Row, FName Name, FName LabelName, const FText& Caption, UTextBlock*& OutLabel)
	{
		UButton* Button = Tree->ConstructWidget<UButton>(UButton::StaticClass(), Name);
		Button->SetBackgroundColor(ButtonColor);
		OutLabel = MakeText(Tree, LabelName, 24);
		OutLabel->SetText(Caption);
		if (UButtonSlot* LabelSlot = Cast<UButtonSlot>(Button->AddChild(OutLabel)))
		{
			LabelSlot->SetPadding(FMargin(36.f, 10.f));
		}
		UHorizontalBoxSlot* RowSlot = Row->AddChildToHorizontalBox(Button);
		RowSlot->SetPadding(FMargin(12.f, 0.f));
		return Button;
	}
}

// ---- Results ----------------------------------------------------------------

FText UDFRaceSummaryWidget::TitleFor(const FDFRaceResult& Result)
{
	if (Result.Reason == EDFRaceEndReason::DeathLimit)
	{
		return LOCTEXT("GameOver", "GAME OVER");
	}
	return Result.bPassed ? LOCTEXT("RaceComplete", "RACE COMPLETE") : LOCTEXT("TimeUp", "TIME UP");
}

void UDFRaceSummaryWidget::ShowResults(const FDFRaceResult& Result)
{
	SetTextOf(TitleText, TitleFor(Result));
	SetColorOf(TitleText, Result.bPassed ? SummaryGreen : SummaryRed);
	SetTextOf(PlaceText, FText::Format(LOCTEXT("Place", "Place {0} of {1}"), Whole(Result.Rank), Whole(Result.RacerCount)));
	SetTextOf(StatsText, FText::Format(LOCTEXT("Stats", "Score {0} / {1}    Laps {2}    Kills {3}    Deaths {4}"),
		Whole(Result.Score), Whole(Result.ScoreRequirement), Whole(Result.Laps), Whole(Result.Kills), Whole(Result.Deaths)));
}

// ---- Buttons ----------------------------------------------------------------

void UDFRaceSummaryWidget::HandleRetry()
{
	// The UI-only input mode is kept by the game viewport, which outlives the level: give it back to
	// the game first, or the reloaded race would ignore every key.
	if (APlayerController* Player = GetOwningPlayer())
	{
		Player->SetInputMode(FInputModeGameOnly());
	}
	UGameplayStatics::OpenLevel(this, FName(*UGameplayStatics::GetCurrentLevelName(this, true)));
}

void UDFRaceSummaryWidget::HandleQuit()
{
	UKismetSystemLibrary::QuitGame(this, GetOwningPlayer(), EQuitPreference::Quit, false);
}

// ---- UUserWidget ------------------------------------------------------------

bool UDFRaceSummaryWidget::Initialize()
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

void UDFRaceSummaryWidget::NativeOnInitialized()
{
	BuildDefaultTree();
	Super::NativeOnInitialized();
	if (RetryButton)
	{
		RetryButton->OnClicked.AddDynamic(this, &UDFRaceSummaryWidget::HandleRetry);
	}
	if (QuitButton)
	{
		QuitButton->OnClicked.AddDynamic(this, &UDFRaceSummaryWidget::HandleQuit);
	}
}

void UDFRaceSummaryWidget::BuildDefaultTree()
{
	if (!WidgetTree || WidgetTree->RootWidget)
	{
		return;
	}

	UCanvasPanel* Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("SummaryRoot"));
	WidgetTree->RootWidget = Root;

	// A dark panel in the middle of the screen.
	UBorder* Panel = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("SummaryPanel"));
	Panel->SetBrushColor(PanelColor);
	Panel->SetPadding(FMargin(56.f, 36.f));
	UCanvasPanelSlot* PanelSlot = Root->AddChildToCanvas(Panel);
	PanelSlot->SetAnchors(FAnchors(0.5f, 0.5f));
	PanelSlot->SetAlignment(FVector2D(0.5f, 0.5f));
	PanelSlot->SetPosition(FVector2D::ZeroVector);
	PanelSlot->SetAutoSize(true);

	// Inside it, centred: the title, the place, the stats and the buttons.
	UVerticalBox* Box = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("SummaryBox"));
	Panel->SetContent(Box);
	TitleText = MakeText(WidgetTree, TEXT("TitleText"), 56);
	PlaceText = MakeText(WidgetTree, TEXT("PlaceText"), 30);
	StatsText = MakeText(WidgetTree, TEXT("StatsText"), 22);
	AddToBox(Box, TitleText, 0.f);
	AddToBox(Box, PlaceText, 14.f);
	AddToBox(Box, StatsText, 10.f);

	UHorizontalBox* Buttons = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), TEXT("ButtonRow"));
	RetryButton = AddButton(WidgetTree, Buttons, TEXT("RetryButton"), TEXT("RetryLabel"), LOCTEXT("Retry", "RETRY"), RetryLabel);
	QuitButton = AddButton(WidgetTree, Buttons, TEXT("QuitButton"), TEXT("QuitLabel"), LOCTEXT("Quit", "QUIT"), QuitLabel);
	AddToBox(Box, Buttons, 30.f);
}

#undef LOCTEXT_NAMESPACE
