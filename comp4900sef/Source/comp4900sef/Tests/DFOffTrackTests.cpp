// Dead Fire - COMP 4900SEF Group 3
// Editor automation tests for the off-track timer and the per-racer tick.

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "DFTestUtils.h"
#include "Character/DFCharacter.h"
#include "Game/DFRaceGameMode.h"
#include "Game/DFRaceGameState.h"
#include "Game/DFRacerComponent.h"
#include "Player/DFPlayerController.h"
#include "Track/DFCheckpoint.h"
#include "Track/DFTrackSpline.h"
#include "Vehicle/DFVehiclePawn.h"
#include "Components/SplineComponent.h"
#include "Engine/EngineTypes.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

namespace
{
	/** Off every road: 3000 cm inside the main loop's first side, away from the shortcut road. */
	const FVector OffTrackSpot(10000.f, 3000.f, 0.f);

	/** Deep inside the loop, off the main road; the shortcut road (when a test builds one) runs through it. */
	const FVector InfieldSpot(10000.f, 5000.f, 0.f);

	/**
	 * A running race in a fresh editor world on a floor: GameMode and GameState (60 s left), the player,
	 * the main track (closed square loop 0,0 -> 20000,0 -> 20000,20000 -> 0,20000, road 1400 cm wide),
	 * gate 0 at the origin (the player's last checkpoint), and the player's car, off the road, with the
	 * on-foot character stowed inside.
	 */
	struct FDFOffTrackRace
	{
		UWorld* World = nullptr;
		ADFRaceGameMode* GameMode = nullptr;
		ADFRaceGameState* State = nullptr;
		ADFPlayerController* PC = nullptr;
		UDFRacerComponent* Racer = nullptr;
		ADFTrackSpline* Main = nullptr;
		ADFCheckpoint* Gate0 = nullptr;
		ADFCharacter* Char = nullptr;
		ADFVehiclePawn* Car = nullptr;

		bool SetUp(FAutomationTestBase& Test)
		{
			World = DFTests::NewTestWorld();
			DFTests::SpawnFloor(World);
			GameMode = DFTests::SpawnAt<ADFRaceGameMode>(World, FVector::ZeroVector);
			State = DFTests::SpawnAt<ADFRaceGameState>(World, FVector::ZeroVector);
			PC = DFTests::SpawnAt<ADFPlayerController>(World, FVector::ZeroVector);
			if (!Test.TestNotNull(TEXT("game mode"), GameMode) || !Test.TestNotNull(TEXT("game state"), State) || !Test.TestNotNull(TEXT("player"), PC))
			{
				return false;
			}
			Racer = UDFRacerComponent::FindOn(PC);
			if (!Test.TestNotNull(TEXT("racer"), Racer))
			{
				return false;
			}
			// Editor worlds run no BeginPlay: wire the GameState and start the race by hand.
			GameMode->GameState = State;
			State->bRaceActive = true;
			State->RemainingTime = 60.f;

			Main = DFTests::SpawnAt<ADFTrackSpline>(World, FVector::ZeroVector);
			Gate0 = DFTests::SpawnAt<ADFCheckpoint>(World, FVector::ZeroVector);
			if (!Test.TestNotNull(TEXT("main track"), Main) || !Test.TestNotNull(TEXT("gate 0"), Gate0))
			{
				return false;
			}
			Main->RoadWidth = 1400.f;
			Main->SetPointsFromArray({ FVector(0.f, 0.f, 0.f), FVector(20000.f, 0.f, 0.f), FVector(20000.f, 20000.f, 0.f), FVector(0.f, 20000.f, 0.f) }, true);
			Gate0->CheckpointIndex = 0;
			GameMode->RegisterCheckpoint(Gate0);
			GameMode->CollectLevelActors();

			Car = DFTests::SpawnAt<ADFVehiclePawn>(World, OffTrackSpot);
			Char = DFTests::SpawnAt<ADFCharacter>(World, OffTrackSpot + FVector(0.f, -250.f, 96.f));
			if (!Test.TestNotNull(TEXT("car"), Car) || !Test.TestNotNull(TEXT("character"), Char))
			{
				return false;
			}
			if (!Test.TestTrue(TEXT("character gets in"), Car->EnterVehicle(Char)))
			{
				return false;
			}
			PC->CurrentVehicle = Car;
			PC->OnFootCharacter = Char;
			Racer->LastCheckpoint = Gate0;
			return true;
		}

		/** Editor worlds run no physics, so a moved car stays exactly where it is put. */
		void PlaceCar(const FVector& Location)
		{
			Car->SetActorLocation(Location);
		}

		/** One frame of the player's racer, as Tick runs it, with the given pawn. */
		void Tick(APawn* Pawn, float DeltaSeconds)
		{
			GameMode->TickRacer(PC, Pawn, DeltaSeconds);
		}
	};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFOffTrackOnRoadTest, "DeadFire.OffTrack.OnRoadResetsTimer", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFOffTrackOnRoadTest::RunTest(const FString& Parameters)
{
	FDFOffTrackRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFVehiclePawn* Car = Race.Car;

	// The loop's sides bow outwards between the corners (the spline's automatic tangents): at X = 10000
	// the centre line runs at about Y = -2500, not 0. So the spots are measured from the spline itself.
	const FVector Probe(10000.f, 0.f, 0.f);
	const FVector OnLine = Race.Main->Spline->FindLocationClosestToWorldLocation(Probe, ESplineCoordinateSpace::World);
	const FVector Across = Race.Main->Spline->FindRightVectorClosestToWorldLocation(Probe, ESplineCoordinateSpace::World);
	const FVector OnRoad = OnLine + Across * 300.f;
	const FVector OffRoad = OnLine + Across * 1500.f;
	TestEqual(TEXT("on-road spot is 300 cm from the centre line"), Race.Main->GetLateralDistanceFromTrack(OnRoad), 300.f, 30.f);
	TestEqual(TEXT("off-road spot is 1500 cm from the centre line (beyond 700 + 500)"), Race.Main->GetLateralDistanceFromTrack(OffRoad), 1500.f, 30.f);

	Race.PlaceCar(OnRoad);
	Race.Tick(Car, 1.f);
	TestEqual(TEXT("on the road the timer does not run"), Race.Racer->OffTrackSeconds, 0.f);
	TestEqual(TEXT("progress measured along the main track"), Race.Racer->DistanceAlongTrack, Race.Main->GetDistanceAlongTrack(OnRoad), 1.f);

	Race.PlaceCar(OffRoad);
	for (int32 Frame = 0; Frame < 3; ++Frame)
	{
		Race.Tick(Car, 1.f);
	}
	TestEqual(TEXT("three seconds off the road"), Race.Racer->OffTrackSeconds, 3.f);

	Race.PlaceCar(OnRoad);
	Race.Tick(Car, 1.f);
	TestEqual(TEXT("back on the road the timer resets"), Race.Racer->OffTrackSeconds, 0.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFOffTrackGraceTest, "DeadFire.OffTrack.GraceRespawnsWithoutDeath", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFOffTrackGraceTest::RunTest(const FString& Parameters)
{
	FDFOffTrackRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFVehiclePawn* Car = Race.Car;

	Race.PlaceCar(OffTrackSpot);
	for (int32 Frame = 0; Frame < 4; ++Frame)
	{
		Race.Tick(Car, 1.1f);
	}
	TestEqual(TEXT("4.4 s off the road"), Race.Racer->OffTrackSeconds, 4.4f, 0.001f);
	TestEqual(TEXT("not put back before the grace runs out"), Car->GetActorLocation(), OffTrackSpot);

	Race.Tick(Car, 1.1f);
	TestEqual(TEXT("timer reset by the respawn"), Race.Racer->OffTrackSeconds, 0.f);
	TestEqual(TEXT("the same car is kept (it is intact)"), Race.PC->CurrentVehicle, Car);
	TestTrue(TEXT("put back at the last checkpoint (gate 0, at the origin)"), FVector::Dist2D(Car->GetActorLocation(), FVector::ZeroVector) <= 300.f);
	TestEqual(TEXT("leaving the road costs no life"), Race.Racer->Deaths, 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFOffTrackOnFootTest, "DeadFire.OffTrack.OnFootDoesNotCount", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFOffTrackOnFootTest::RunTest(const FString& Parameters)
{
	FDFOffTrackRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFCharacter* Char = Race.Char;

	// The player got out off the road, with the car's timer already running, and walks the infield.
	Race.Car->EjectOccupant();
	if (!TestFalse(TEXT("character on foot"), Char->IsInVehicle())) return false;
	Char->SetActorLocation(InfieldSpot);
	Race.Racer->OffTrackSeconds = 3.f;

	Race.Tick(Char, 10.f);
	TestEqual(TEXT("on foot the timer does not run"), Race.Racer->OffTrackSeconds, 0.f);
	TestEqual(TEXT("character not moved"), Char->GetActorLocation(), InfieldSpot);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFOffTrackShortcutTest, "DeadFire.OffTrack.ShortcutRoadCountsAsTrack", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFOffTrackShortcutTest::RunTest(const FString& Parameters)
{
	FDFOffTrackRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFRaceGameMode* GameMode = Race.GameMode;
	TestFalse(TEXT("without the shortcut the spot is off every road"), GameMode->IsOnAnyTrack(InfieldSpot));

	ADFTrackSpline* Shortcut = DFTests::SpawnAt<ADFTrackSpline>(Race.World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("shortcut"), Shortcut)) return false;
	Shortcut->bIsMainTrack = false;
	Shortcut->SetPointsFromArray({ FVector(5000.f, 5000.f, 0.f), FVector(15000.f, 5000.f, 0.f) }, false);
	GameMode->CollectLevelActors();
	TestEqual(TEXT("both roads collected"), GameMode->Tracks.Num(), 2);
	TestEqual(TEXT("the loop stays the main track"), GameMode->MainTrack, Race.Main);

	Race.PlaceCar(InfieldSpot);
	TestTrue(TEXT("a shortcut road counts as track"), GameMode->IsOnAnyTrack(InfieldSpot));
	Race.Tick(Race.Car, 1.f);
	TestEqual(TEXT("the timer does not run on a shortcut"), Race.Racer->OffTrackSeconds, 0.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFOffTrackWreckTest, "DeadFire.OffTrack.WreckStopsTheTimer", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFOffTrackWreckTest::RunTest(const FString& Parameters)
{
	FDFOffTrackRace Race;
	if (!Race.SetUp(*this)) return false;
	ADFVehiclePawn* Car = Race.Car;

	Race.PlaceCar(OffTrackSpot);
	Race.Tick(Car, 1.f);
	Race.Tick(Car, 1.f);
	TestEqual(TEXT("two seconds off the road"), Race.Racer->OffTrackSeconds, 2.f);

	Car->TakeDamage(1000.f, FDamageEvent(), nullptr, nullptr);
	if (!TestTrue(TEXT("car wrecked"), Car->bIsDestroyed)) return false;
	// Well past the grace: only the death respawn may move a wreck.
	Race.Tick(Car, 10.f);
	TestEqual(TEXT("a wreck stops the timer"), Race.Racer->OffTrackSeconds, 0.f);
	TestEqual(TEXT("the wreck is not put back"), Car->GetActorLocation(), OffTrackSpot);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFOffTrackNoTracksTest, "DeadFire.OffTrack.NoTracksNoPenalty", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFOffTrackNoTracksTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFRaceGameMode* GameMode = DFTests::SpawnAt<ADFRaceGameMode>(World, FVector::ZeroVector);
	ADFPlayerController* PC = DFTests::SpawnAt<ADFPlayerController>(World, FVector::ZeroVector);
	const FVector FarAway(99999.f, 99999.f, 0.f);
	ADFVehiclePawn* Car = DFTests::SpawnAt<ADFVehiclePawn>(World, FarAway);
	if (!TestNotNull(TEXT("game mode"), GameMode) || !TestNotNull(TEXT("player"), PC) || !TestNotNull(TEXT("car"), Car)) return false;
	UDFRacerComponent* Racer = UDFRacerComponent::FindOn(PC);
	if (!TestNotNull(TEXT("racer"), Racer)) return false;

	GameMode->CollectLevelActors();
	TestEqual(TEXT("no tracks in the level"), GameMode->Tracks.Num(), 0);
	TestNull(TEXT("no main track"), GameMode->MainTrack);
	TestTrue(TEXT("without tracks every spot counts as track"), GameMode->IsOnAnyTrack(FarAway));

	GameMode->TickRacer(PC, Car, 10.f);
	TestEqual(TEXT("the timer never runs"), Racer->OffTrackSeconds, 0.f);
	return true;
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
