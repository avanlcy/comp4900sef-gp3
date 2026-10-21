// Dead Fire - COMP 4900SEF Group 3

#include "Game/DFRaceGameState.h"

ADFRaceGameState::ADFRaceGameState()
{
	RemainingTime = 0.f;
	bRaceActive = false;
}

void ADFRaceGameState::AddTime(float Seconds)
{
	RemainingTime = FMath::Max(0.f, RemainingTime + Seconds);
}

FText ADFRaceGameState::GetRemainingTimeText() const
{
	const int32 TotalSeconds = FMath::Max(0, FMath::CeilToInt(RemainingTime));
	return FText::FromString(FString::Printf(TEXT("%d:%02d"), TotalSeconds / 60, TotalSeconds % 60));
}
