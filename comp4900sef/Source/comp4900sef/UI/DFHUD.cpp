// Dead Fire - COMP 4900SEF Group 3

#include "UI/DFHUD.h"
#include "UI/DFRaceHUDWidget.h"
#include "UI/DFRaceSummaryWidget.h"
#include "Game/DFRaceGameState.h"
#include "comp4900sef.h"
#include "Blueprint/UserWidget.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"

ADFHUD::ADFHUD()
{
	HUDWidgetClass = UDFRaceHUDWidget::StaticClass();
	HUDWidget = nullptr;
	SummaryWidgetClass = UDFRaceSummaryWidget::StaticClass();
	SummaryWidget = nullptr;
}

void ADFHUD::BeginPlay()
{
	Super::BeginPlay();
	APlayerController* Player = GetOwningPlayerController();
	if (!Player)
	{
		return;
	}
	// A Blueprint that cleared the class must not leave the race without a HUD: fall back to the built-in layout.
	if (!HUDWidgetClass)
	{
		UE_LOG(LogDeadFire, Warning, TEXT("%s has no HUDWidgetClass; using the built-in UDFRaceHUDWidget"), *GetName());
		HUDWidgetClass = UDFRaceHUDWidget::StaticClass();
	}
	HUDWidget = CreateWidget<UDFRaceHUDWidget>(Player, HUDWidgetClass);
	if (HUDWidget)
	{
		HUDWidget->AddToViewport();
	}
	else
	{
		UE_LOG(LogDeadFire, Warning, TEXT("%s could not create the HUD widget %s"), *GetName(), *HUDWidgetClass->GetName());
	}
}

void ADFHUD::ShowSummary()
{
	APlayerController* Player = GetOwningPlayerController();
	if (!SummaryWidget && Player)
	{
		// Without a summary the player would be stuck at the end of the race: fall back to the built-in layout.
		if (!SummaryWidgetClass)
		{
			UE_LOG(LogDeadFire, Warning, TEXT("%s has no SummaryWidgetClass; using the built-in UDFRaceSummaryWidget"), *GetName());
			SummaryWidgetClass = UDFRaceSummaryWidget::StaticClass();
		}
		SummaryWidget = CreateWidget<UDFRaceSummaryWidget>(Player, SummaryWidgetClass);
		if (!SummaryWidget)
		{
			UE_LOG(LogDeadFire, Warning, TEXT("%s could not create the summary widget %s"), *GetName(), *SummaryWidgetClass->GetName());
		}
	}
	if (!SummaryWidget)
	{
		return;
	}

	const UWorld* World = GetWorld();
	if (const ADFRaceGameState* State = World ? World->GetGameState<ADFRaceGameState>() : nullptr)
	{
		SummaryWidget->ShowResults(State->Result);
	}
	else
	{
		UE_LOG(LogDeadFire, Warning, TEXT("%s shows the summary without a race GameState: no result to fill in"), *GetName());
	}
	if (!SummaryWidget->IsInViewport())
	{
		SummaryWidget->AddToViewport(10);
	}
	if (HUDWidget)
	{
		HUDWidget->SetVisibility(ESlateVisibility::Collapsed);
	}

	// The race is over: the mouse is for the summary's buttons now.
	if (Player)
	{
		Player->bShowMouseCursor = true;
		Player->SetInputMode(FInputModeUIOnly());
	}
}

bool ADFHUD::IsSummaryShown() const
{
	return SummaryWidget && SummaryWidget->IsInViewport();
}
