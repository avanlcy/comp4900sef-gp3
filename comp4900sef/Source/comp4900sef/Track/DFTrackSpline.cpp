// Dead Fire - COMP 4900SEF Group 3

#include "Track/DFTrackSpline.h"
#include "comp4900sef.h"
#include "Components/SplineComponent.h"
#include "Components/SplineMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ADFTrackSpline::ADFTrackSpline()
{
	PrimaryActorTick.bCanEverTick = false;

	Spline = CreateDefaultSubobject<USplineComponent>(TEXT("Spline"));
	Spline->SetMobility(EComponentMobility::Static);
	Spline->SetClosedLoop(true);
	RootComponent = Spline;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> RoadMat(TEXT("/Game/VehicleAdv/Materials/MaterialInstances/BlackGrid.BlackGrid"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BarrierMat(TEXT("/Game/VehicleAdv/Materials/MaterialInstances/SolidOrange.SolidOrange"));

	bIsMainTrack = true;
	RoadMesh = CubeMesh.Succeeded() ? CubeMesh.Object : nullptr;
	RoadMaterial = RoadMat.Succeeded() ? RoadMat.Object : nullptr;
	RoadWidth = 1400.f;
	RoadThickness = 20.f;
	PieceLength = 1000.f;
	bGenerateBarriers = false;
	BarrierMesh = RoadMesh;
	BarrierMaterial = BarrierMat.Succeeded() ? BarrierMat.Object : nullptr;
	BarrierHeight = 80.f;
	BarrierThickness = 30.f;
	MeshNativeSize = 100.f;
}

void ADFTrackSpline::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	RebuildTrack();
}

void ADFTrackSpline::ClearGenerated()
{
	for (USplineMeshComponent* Mesh : RoadMeshes)
	{
		if (IsValid(Mesh))
		{
			Mesh->DestroyComponent();
		}
	}
	for (USplineMeshComponent* Mesh : BarrierMeshes)
	{
		if (IsValid(Mesh))
		{
			Mesh->DestroyComponent();
		}
	}
	RoadMeshes.Reset();
	BarrierMeshes.Reset();
}

USplineMeshComponent* ADFTrackSpline::AddPieceMesh(float StartDistance, float EndDistance, UStaticMesh* Mesh, UMaterialInterface* Material, const FVector2D& Offset, const FVector2D& Scale)
{
	if (!Mesh)
	{
		return nullptr;
	}
	// Short pieces with tangents scaled to their length follow the curve closely even with a
	// mesh that has no subdivisions along its length (the engine cube).
	const float Length = EndDistance - StartDistance;
	const FVector StartLocation = Spline->GetLocationAtDistanceAlongSpline(StartDistance, ESplineCoordinateSpace::Local);
	const FVector EndLocation = Spline->GetLocationAtDistanceAlongSpline(EndDistance, ESplineCoordinateSpace::Local);
	const FVector StartTangent = Spline->GetDirectionAtDistanceAlongSpline(StartDistance, ESplineCoordinateSpace::Local) * Length;
	const FVector EndTangent = Spline->GetDirectionAtDistanceAlongSpline(EndDistance, ESplineCoordinateSpace::Local) * Length;

	USplineMeshComponent* Piece = NewObject<USplineMeshComponent>(this);
	Piece->CreationMethod = EComponentCreationMethod::UserConstructionScript;
	Piece->SetMobility(EComponentMobility::Static);
	Piece->SetStaticMesh(Mesh);
	if (Material)
	{
		Piece->SetMaterial(0, Material);
	}
	Piece->SetForwardAxis(ESplineMeshAxis::X, false);
	Piece->SetStartAndEnd(StartLocation, StartTangent, EndLocation, EndTangent, false);
	Piece->SetStartScale(Scale, false);
	Piece->SetEndScale(Scale, false);
	Piece->SetStartOffset(Offset, false);
	Piece->SetEndOffset(Offset, false);
	Piece->SetCollisionProfileName(TEXT("BlockAll"));
	Piece->SetupAttachment(Spline);
	Piece->RegisterComponent();
	Piece->UpdateMesh();
	return Piece;
}

void ADFTrackSpline::RebuildTrack()
{
	ClearGenerated();
	if (!Spline || Spline->GetNumberOfSplinePoints() < 2)
	{
		return;
	}
	const float TrackLength = Spline->GetSplineLength();
	if (TrackLength <= KINDA_SMALL_NUMBER)
	{
		return;
	}

	const int32 NumPieces = FMath::Max(1, FMath::CeilToInt(TrackLength / FMath::Max(100.f, PieceLength)));
	const float Step = TrackLength / NumPieces;
	const float Unit = FMath::Max(1.f, MeshNativeSize);

	// The road slab's top surface sits on the spline; the slab hangs below it.
	const FVector2D RoadScale(RoadWidth / Unit, RoadThickness / Unit);
	const FVector2D RoadOffset(0.f, -RoadThickness * 0.5f);

	const FVector2D BarrierScale(BarrierThickness / Unit, BarrierHeight / Unit);
	const float BarrierLateral = RoadWidth * 0.5f + BarrierThickness * 0.5f;
	const float BarrierVertical = BarrierHeight * 0.5f;

	for (int32 Piece = 0; Piece < NumPieces; ++Piece)
	{
		const float StartDistance = Piece * Step;
		const float EndDistance = (Piece + 1) * Step;
		if (USplineMeshComponent* Road = AddPieceMesh(StartDistance, EndDistance, RoadMesh, RoadMaterial, RoadOffset, RoadScale))
		{
			RoadMeshes.Add(Road);
		}
		if (bGenerateBarriers)
		{
			UStaticMesh* Mesh = BarrierMesh ? BarrierMesh : RoadMesh;
			if (USplineMeshComponent* Left = AddPieceMesh(StartDistance, EndDistance, Mesh, BarrierMaterial, FVector2D(-BarrierLateral, BarrierVertical), BarrierScale))
			{
				BarrierMeshes.Add(Left);
			}
			if (USplineMeshComponent* Right = AddPieceMesh(StartDistance, EndDistance, Mesh, BarrierMaterial, FVector2D(BarrierLateral, BarrierVertical), BarrierScale))
			{
				BarrierMeshes.Add(Right);
			}
		}
	}
}

int32 ADFTrackSpline::GetSegmentCount() const
{
	return RoadMeshes.Num();
}

int32 ADFTrackSpline::GetGeneratedMeshCount() const
{
	return RoadMeshes.Num() + BarrierMeshes.Num();
}

float ADFTrackSpline::GetTrackLength() const
{
	return Spline ? Spline->GetSplineLength() : 0.f;
}

float ADFTrackSpline::GetDistanceAlongTrack(const FVector& WorldLocation) const
{
	if (!Spline)
	{
		return 0.f;
	}
	const float Key = Spline->FindInputKeyClosestToWorldLocation(WorldLocation);
	return Spline->GetDistanceAlongSplineAtSplineInputKey(Key);
}

float ADFTrackSpline::GetLateralDistanceFromTrack(const FVector& WorldLocation) const
{
	if (!Spline)
	{
		return 0.f;
	}
	const float Key = Spline->FindInputKeyClosestToWorldLocation(WorldLocation);
	const FVector Closest = Spline->GetLocationAtSplineInputKey(Key, ESplineCoordinateSpace::World);
	return FVector::Dist2D(Closest, WorldLocation);
}

bool ADFTrackSpline::IsOnRoad(const FVector& WorldLocation) const
{
	return Spline && Spline->GetNumberOfSplinePoints() >= 2 && GetLateralDistanceFromTrack(WorldLocation) <= RoadWidth * 0.5f;
}

FTransform ADFTrackSpline::GetTransformAtDistance(float Distance) const
{
	return Spline ? Spline->GetTransformAtDistanceAlongSpline(Distance, ESplineCoordinateSpace::World, false) : FTransform::Identity;
}

void ADFTrackSpline::SetPointsFromArray(const TArray<FVector>& WorldPoints, bool bClosedLoop)
{
	if (!Spline)
	{
		return;
	}
	Spline->ClearSplinePoints(false);
	for (const FVector& Point : WorldPoints)
	{
		Spline->AddSplinePoint(Point, ESplineCoordinateSpace::World, false);
	}
	Spline->SetClosedLoop(bClosedLoop, false);
	Spline->UpdateSpline();
	RebuildTrack();
}
