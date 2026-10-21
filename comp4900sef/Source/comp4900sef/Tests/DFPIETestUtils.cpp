// Dead Fire - COMP 4900SEF Group 3

#include "Tests/DFPIETestUtils.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Engine/GameViewportClient.h"
#include "Framework/Application/SlateApplication.h"
#include "ImageUtils.h"
#include "Layout/WidgetPath.h"
#include "Misc/App.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"
#include "Widgets/SViewport.h"

bool FDFPIEKey::Update()
{
	DFPIE::Key(KeyToPress, Event);
	return true;
}

bool FDFPIEWaitFrames::Update()
{
	return --Frames <= 0;
}

bool FDFPIEScreenshot::Update()
{
	// The HUD and the summary are UMG widgets that Slate draws over the game viewport, so the engine's
	// viewport screenshot would miss them: capture the play viewport widget with its UI instead.
	UWorld* World = DFPIE::PIEWorld();
	UGameViewportClient* GameViewport = World ? World->GetGameViewport() : nullptr;
	const TSharedPtr<SViewport> ViewportWidget = GameViewport ? GameViewport->GetGameViewportWidget() : nullptr;
	FWidgetPath Path;
	TArray<FColor> Bitmap;
	FIntVector Size;
	if (FApp::CanEverRender() && ViewportWidget.IsValid()
		&& FSlateApplication::Get().GeneratePathToWidgetUnchecked(ViewportWidget.ToSharedRef(), Path)
		&& FSlateApplication::Get().TakeScreenshot(ViewportWidget.ToSharedRef(), Bitmap, Size))
	{
		for (FColor& Pixel : Bitmap)
		{
			Pixel.A = 255;
		}
		TArray<uint8> Png;
		FImageUtils::CompressImageArray(Size.X, Size.Y, Bitmap, Png);
		FFileHelper::SaveArrayToFile(Png, *(FPaths::ScreenShotDir() / Name + TEXT(".png")));
		return true;
	}
	// Headless (-NullRHI) nothing is drawn; the engine's request keeps the file name and gives a black image.
	FScreenshotRequest::RequestScreenshot(Name, false, false);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
