// Dead Fire - COMP 4900SEF Group 3

#include "UI/DFHUD.h"
#include "Character/DFCharacter.h"
#include "Game/DFRaceGameState.h"
#include "Game/DFRacerComponent.h"
#include "Vehicle/DFVehiclePawn.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "UObject/ConstructorHelpers.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

ADFHUD::ADFHUD()
{
	static ConstructorHelpers::FObjectFinder<UFont> Font(TEXT("/Engine/EngineFonts/RobotoDistanceField"));
	HUDFont = Font.Succeeded() ? Font.Object : nullptr;
}

void ADFHUD::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas)
	{
		return;
	}
	const float Scale = FMath::Max(0.5f, Canvas->SizeY / 720.f);
	DrawRaceInfo(Scale);

	APawn* Pawn = GetOwningPawn();
	if (Cast<ADFVehiclePawn>(Pawn))
	{
		DrawVehicleInfo(Scale);
	}
	else if (Cast<ADFCharacter>(Pawn))
	{
		DrawCharacterInfo(Scale);
	}
}

void ADFHUD::DrawRaceInfo(float Scale)
{
	const UDFRacerComponent* Racer = UDFRacerComponent::FindOn(GetOwningPlayerController());
	const ADFRaceGameState* State = GetWorld() ? GetWorld()->GetGameState<ADFRaceGameState>() : nullptr;

	const FString ScoreLine = FString::Printf(TEXT("SCORE %d    LAPS %d    KILLS %d"),
		Racer ? Racer->Score : 0, Racer ? Racer->LapsCompleted : 0, Racer ? Racer->Kills : 0);
	const FString TimeLine = State
		? FString::Printf(TEXT("TIME %s"), *State->GetRemainingTimeText().ToString())
		: FString(TEXT("TIME --:--"));
	const FLinearColor TimeColor = (State && State->RemainingTime < 10.f) ? FLinearColor::Red : FLinearColor::Yellow;

	DrawText(ScoreLine, FLinearColor::White, 24.f * Scale, 20.f * Scale, HUDFont, 1.1f * Scale);
	DrawText(TimeLine, TimeColor, 24.f * Scale, 48.f * Scale, HUDFont, 1.1f * Scale);
}

void ADFHUD::DrawVehicleInfo(float Scale)
{
	ADFVehiclePawn* Vehicle = Cast<ADFVehiclePawn>(GetOwningPawn());
	if (!Vehicle)
	{
		return;
	}

	const FString SpeedLine = FString::Printf(TEXT("%d km/h"), FMath::FloorToInt(Vehicle->GetSpeedKPH()));
	const FString GearLine = FString::Printf(TEXT("GEAR %s"), *Vehicle->GetGearDisplayText().ToString());
	const FString HealthLine = FString::Printf(TEXT("CAR %d / %d"), FMath::CeilToInt(Vehicle->Health), FMath::CeilToInt(Vehicle->MaxHealth));
	FString TireLine = TEXT("TIRES ");
	for (const FDFTireState& Tire : Vehicle->Tires)
	{
		TireLine += Tire.bBlown ? TEXT("[X] ") : FString::Printf(TEXT("[%d] "), FMath::CeilToInt(Tire.Health));
	}

	const float RightX = Canvas->SizeX - 260.f * Scale;
	const float BottomY = Canvas->SizeY - 130.f * Scale;
	DrawText(SpeedLine, FLinearColor::White, RightX, BottomY, HUDFont, 1.6f * Scale);
	DrawText(GearLine, Vehicle->bInReverseGear ? FLinearColor::Red : FLinearColor::White, RightX, BottomY + 40.f * Scale, HUDFont, 1.1f * Scale);
	DrawText(HealthLine, FLinearColor::White, 24.f * Scale, Canvas->SizeY - 80.f * Scale, HUDFont, 1.1f * Scale);
	DrawText(TireLine, FLinearColor::White, 24.f * Scale, Canvas->SizeY - 52.f * Scale, HUDFont, 1.1f * Scale);

	if (Vehicle->bIsDestroyed)
	{
		DrawPrompt(TEXT("VEHICLE DESTROYED"), Scale);
	}
	else if (Vehicle->Occupant)
	{
		DrawPrompt(Vehicle->CanExit() ? TEXT("[E] Exit vehicle") : TEXT("Stop to exit  [E]"), Scale);
	}
}

void ADFHUD::DrawCharacterInfo(float Scale)
{
	ADFCharacter* Character = Cast<ADFCharacter>(GetOwningPawn());
	if (!Character)
	{
		return;
	}

	const FString HealthLine = FString::Printf(TEXT("HEALTH %d / %d"), FMath::CeilToInt(Character->Health), FMath::CeilToInt(Character->MaxHealth));
	DrawText(HealthLine, FLinearColor::White, 24.f * Scale, Canvas->SizeY - 52.f * Scale, HUDFont, 1.1f * Scale);

	const float CenterX = Canvas->SizeX * 0.5f;
	const float CenterY = Canvas->SizeY * 0.5f;
	const float Arm = 8.f * Scale;
	DrawLine(CenterX - Arm, CenterY, CenterX + Arm, CenterY, FLinearColor::White, 1.5f);
	DrawLine(CenterX, CenterY - Arm, CenterX, CenterY + Arm, FLinearColor::White, 1.5f);

	if (Character->IsDead())
	{
		DrawPrompt(TEXT("YOU DIED"), Scale);
	}
	else if (Character->FindNearestEnterableVehicle())
	{
		DrawPrompt(TEXT("[E] Enter vehicle"), Scale);
	}
}

void ADFHUD::DrawPrompt(const FString& Text, float Scale)
{
	float Width = 0.f;
	float Height = 0.f;
	GetTextSize(Text, Width, Height, HUDFont, 1.2f * Scale);
	DrawText(Text, FLinearColor(1.f, 0.85f, 0.2f), (Canvas->SizeX - Width) * 0.5f, Canvas->SizeY * 0.72f, HUDFont, 1.2f * Scale);
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS
