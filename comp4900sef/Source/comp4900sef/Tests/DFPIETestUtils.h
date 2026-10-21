// Dead Fire - COMP 4900SEF Group 3
// Shared helpers for the DeadFire.PIE.* Play-In-Editor tests: the play world, the player, real key
// input, frame-based waits and screenshots.

#pragma once

#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"

namespace DFPIE
{
	/** The running Play-In-Editor world, or null. */
	inline UWorld* PIEWorld()
	{
		for (const FWorldContext& Context : GEngine->GetWorldContexts())
		{
			if (Context.WorldType == EWorldType::PIE && Context.World())
			{
				return Context.World();
			}
		}
		return nullptr;
	}

	inline APlayerController* PlayerController()
	{
		UWorld* World = PIEWorld();
		return World ? UGameplayStatics::GetPlayerController(World, 0) : nullptr;
	}

	inline APawn* PlayerPawn()
	{
		UWorld* World = PIEWorld();
		return World ? UGameplayStatics::GetPlayerPawn(World, 0) : nullptr;
	}

	/** Sends a key event through the player controller, the way the keyboard would. */
	inline void Key(const FKey& Key, EInputEvent Event)
	{
		if (APlayerController* PC = PlayerController())
		{
			PC->InputKey(Key, Event, 1.f, false);
		}
	}
}

// Latent commands shared by the PIE tests; the Update() bodies are in DFPIETestUtils.cpp.

DEFINE_LATENT_AUTOMATION_COMMAND_TWO_PARAMETER(FDFPIEKey, FKey, KeyToPress, EInputEvent, Event);

/** Waits a number of engine frames (one Update per frame), independent of wall-clock throttling. */
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFPIEWaitFrames, int32, Frames);

/** Saves Saved/Screenshots/<platform>/<Name>.png of the play viewport, UMG widgets included. */
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FDFPIEScreenshot, FString, Name);

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
