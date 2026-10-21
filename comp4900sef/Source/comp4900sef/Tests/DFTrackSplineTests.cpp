// Dead Fire - COMP 4900SEF Group 3
// Editor automation tests for ADFTrackSpline.

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "DFTestUtils.h"
#include "Track/DFTrackSpline.h"
#include "CollisionQueryParams.h"
#include "Components/SplineComponent.h"
#include "Components/SplineMeshComponent.h"

namespace
{
	TArray<FVector> SquareLoop(float Side)
	{
		return { FVector(0.f, 0.f, 0.f), FVector(Side, 0.f, 0.f), FVector(Side, Side, 0.f), FVector(0.f, Side, 0.f) };
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFTrackClosedLoopTest, "DeadFire.Track.ClosedLoopGeneratesSegments", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFTrackClosedLoopTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFTrackSpline* Track = DFTests::SpawnAt<ADFTrackSpline>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("track"), Track)) return false;

	Track->SetPointsFromArray(SquareLoop(2000.f), true);

	// One road piece per PieceLength of spline (default 1000 cm), so a loop of 8+ m has 8+ pieces.
	TestTrue(TEXT("track has length"), Track->GetTrackLength() > 7000.f);
	const int32 Expected = FMath::CeilToInt(Track->GetTrackLength() / Track->PieceLength);
	TestEqual(TEXT("one road piece per piece length"), Track->GetSegmentCount(), Expected);
	TestTrue(TEXT("at least eight pieces"), Track->GetSegmentCount() >= 8);
	TestEqual(TEXT("no barriers by default"), Track->GetGeneratedMeshCount(), Track->GetSegmentCount());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFTrackBarriersTest, "DeadFire.Track.BarriersWhenEnabled", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFTrackBarriersTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFTrackSpline* Track = DFTests::SpawnAt<ADFTrackSpline>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("track"), Track)) return false;

	Track->bGenerateBarriers = true;
	Track->SetPointsFromArray(SquareLoop(2000.f), true);

	TestTrue(TEXT("road pieces generated"), Track->GetSegmentCount() >= 8);
	TestEqual(TEXT("road plus two barriers per piece"), Track->GetGeneratedMeshCount(), Track->GetSegmentCount() * 3);

	Track->bGenerateBarriers = false;
	Track->RebuildTrack();
	TestEqual(TEXT("rebuild without barriers"), Track->GetGeneratedMeshCount(), Track->GetSegmentCount());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFTrackTooFewPointsTest, "DeadFire.Track.TooFewPointsIsSafe", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFTrackTooFewPointsTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFTrackSpline* Track = DFTests::SpawnAt<ADFTrackSpline>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("track"), Track)) return false;

	Track->SetPointsFromArray({ FVector(100.f, 100.f, 0.f) }, true);
	TestEqual(TEXT("no meshes for a single point"), Track->GetGeneratedMeshCount(), 0);
	TestEqual(TEXT("no segments for a single point"), Track->GetSegmentCount(), 0);

	Track->SetPointsFromArray(TArray<FVector>(), true);
	TestEqual(TEXT("no meshes for no points"), Track->GetGeneratedMeshCount(), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFTrackDistanceTest, "DeadFire.Track.DistanceAlongTrackIsMonotonic", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFTrackDistanceTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFTrackSpline* Track = DFTests::SpawnAt<ADFTrackSpline>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("track"), Track)) return false;

	const TArray<FVector> Points = SquareLoop(4000.f);
	Track->SetPointsFromArray(Points, true);

	const float D0 = Track->GetDistanceAlongTrack(Points[0]);
	const float D1 = Track->GetDistanceAlongTrack(Points[1]);
	const float D2 = Track->GetDistanceAlongTrack(Points[2]);
	TestEqual(TEXT("start of track is zero"), D0, 0.f, 1.f);
	TestTrue(TEXT("second point further along"), D1 > D0 + 3000.f);
	TestTrue(TEXT("third point further still"), D2 > D1 + 3000.f);
	TestTrue(TEXT("within track length"), D2 <= Track->GetTrackLength());

	const FTransform Mid = Track->GetTransformAtDistance(D1 * 0.5f);
	TestTrue(TEXT("transform at distance lies on the first straight"), Mid.GetLocation().X > 500.f && Mid.GetLocation().X < 3500.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFTrackLateralTest, "DeadFire.Track.LateralDistance", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFTrackLateralTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFTrackSpline* Track = DFTests::SpawnAt<ADFTrackSpline>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("track"), Track)) return false;

	Track->SetPointsFromArray(SquareLoop(4000.f), true);

	// A point on the first straight and its sideways direction.
	const FVector OnLine = Track->Spline->GetLocationAtDistanceAlongSpline(2000.f, ESplineCoordinateSpace::World);
	const FVector Right = Track->Spline->GetRightVectorAtDistanceAlongSpline(2000.f, ESplineCoordinateSpace::World);

	TestEqual(TEXT("centre line is zero"), Track->GetLateralDistanceFromTrack(OnLine), 0.f, 5.f);
	TestEqual(TEXT("500 cm beside"), Track->GetLateralDistanceFromTrack(OnLine + Right * 500.f), 500.f, 30.f);
	TestTrue(TEXT("500 cm beside is still on a 1400 cm road"), Track->IsOnRoad(OnLine + Right * 500.f));
	TestFalse(TEXT("1000 cm beside is off the road"), Track->IsOnRoad(OnLine + Right * 1000.f));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDFTrackCurveTest, "DeadFire.Track.RoadFollowsCurve", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FDFTrackCurveTest::RunTest(const FString& Parameters)
{
	UWorld* World = DFTests::NewTestWorld();
	ADFTrackSpline* Track = DFTests::SpawnAt<ADFTrackSpline>(World, FVector::ZeroVector);
	if (!TestNotNull(TEXT("track"), Track)) return false;

	// A narrow road on a loop that bulges between its corners: the road must sit under the
	// spline where it curves, not only on straight lines between the control points.
	Track->RoadWidth = 300.f;
	Track->SetPointsFromArray(SquareLoop(4000.f), true);

	const float Distance = Track->GetTrackLength() * 0.125f; // middle of the first arc
	const FVector OnSpline = Track->Spline->GetLocationAtDistanceAlongSpline(Distance, ESplineCoordinateSpace::World);
	TestTrue(TEXT("the spline really bulges away from the straight line here"), FMath::Abs(OnSpline.Y) > 150.f);

	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(DFTrackTrace), false);
	const bool bHit = World->LineTraceSingleByChannel(Hit, OnSpline + FVector(0.f, 0.f, 200.f), OnSpline - FVector(0.f, 0.f, 200.f), ECC_Visibility, Params);
	TestTrue(TEXT("road found under the curved spline"), bHit);
	if (bHit)
	{
		TestTrue(TEXT("hit a road piece"), Hit.GetComponent() && Hit.GetComponent()->IsA<USplineMeshComponent>());
		TestEqual(TEXT("road surface at spline height"), Hit.ImpactPoint.Z, OnSpline.Z, 10.f);
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
