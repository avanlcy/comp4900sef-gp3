// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "Components/TextBlock.h"

/** Text helpers shared by the in-race HUD and the end-of-race summary widgets. */
namespace DFWidgetText
{
	/** Numbers on screen never use digit grouping: SCORE 1500, not SCORE 1,500. */
	inline FText Whole(int32 Value)
	{
		return FText::AsNumber(Value, &FNumberFormattingOptions::DefaultNoGrouping());
	}

	/** Sets the text of an element a designer layout may leave out (null is skipped). */
	inline void SetTextOf(UTextBlock* Block, const FText& Text)
	{
		if (Block)
		{
			Block->SetText(Text);
		}
	}

	/** Sets the colour of an element a designer layout may leave out (null is skipped). */
	inline void SetColorOf(UTextBlock* Block, const FLinearColor& Color)
	{
		if (Block)
		{
			Block->SetColorAndOpacity(FSlateColor(Color));
		}
	}
}
