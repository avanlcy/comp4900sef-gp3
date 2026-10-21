// Dead Fire - COMP 4900SEF Group 3

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DFTrackSpline.generated.h"

class USplineComponent;
class USplineMeshComponent;
class UStaticMesh;
class UMaterialInterface;

/**
 * A race track drawn as a spline. Drop it in a level, drag the points, and the road
 * (and optional side barriers) regenerate automatically. Also answers "how far along
 * the track is this location" and "how far off the road is it" for checkpoints,
 * AI drivers and the off-track timer in later phases.
 */
UCLASS()
class COMP4900SEF_API ADFTrackSpline : public AActor
{
	GENERATED_BODY()

public:
	ADFTrackSpline();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Dead Fire|Track")
	USplineComponent* Spline;

	/** The track laps and progress are measured against. Shortcut roads set this to false. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Track")
	bool bIsMainTrack;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Track")
	UStaticMesh* RoadMesh;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Track")
	UMaterialInterface* RoadMaterial;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Track", meta = (ClampMin = "100.0"))
	float RoadWidth;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Track", meta = (ClampMin = "1.0"))
	float RoadThickness;

	/** Length (cm) of each road piece along the spline. Smaller pieces follow curves more closely. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Track", meta = (ClampMin = "100.0"))
	float PieceLength;

	/** Off by default: cars are allowed to leave the road. Enable for walled sections. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Track")
	bool bGenerateBarriers;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Track")
	UStaticMesh* BarrierMesh;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Track")
	UMaterialInterface* BarrierMaterial;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Track", meta = (ClampMin = "1.0"))
	float BarrierHeight;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Track", meta = (ClampMin = "1.0"))
	float BarrierThickness;

	/** Edge length (cm) of the mesh's native bounding cube. The engine's basic cube is 100. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Dead Fire|Track", meta = (ClampMin = "1.0"))
	float MeshNativeSize;

	/** Regenerates the road and barrier meshes from the spline. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Track")
	void RebuildTrack();

	/** Number of road pieces (one per PieceLength of spline). */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|Track")
	int32 GetSegmentCount() const;

	/** Road pieces plus barrier pieces. */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|Track")
	int32 GetGeneratedMeshCount() const;

	UFUNCTION(BlueprintPure, Category = "Dead Fire|Track")
	float GetTrackLength() const;

	/** Distance in cm from the start of the spline to the point closest to the location. */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|Track")
	float GetDistanceAlongTrack(const FVector& WorldLocation) const;

	/** Horizontal distance in cm from the location to the centre line (0 on the centre line). */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|Track")
	float GetLateralDistanceFromTrack(const FVector& WorldLocation) const;

	/** True when the location is within half the road width of the centre line. */
	UFUNCTION(BlueprintPure, Category = "Dead Fire|Track")
	bool IsOnRoad(const FVector& WorldLocation) const;

	UFUNCTION(BlueprintPure, Category = "Dead Fire|Track")
	FTransform GetTransformAtDistance(float Distance) const;

	/** Replaces every spline point (world space) and rebuilds the meshes. */
	UFUNCTION(BlueprintCallable, Category = "Dead Fire|Track")
	void SetPointsFromArray(const TArray<FVector>& WorldPoints, bool bClosedLoop);

	virtual void OnConstruction(const FTransform& Transform) override;

protected:
	// Saved with the level (not transient): a Play-In-Editor world is a copy of the editor
	// world that neither copies transient components nor reruns construction, and a cooked
	// build never runs it at all.
	UPROPERTY()
	TArray<USplineMeshComponent*> RoadMeshes;

	UPROPERTY()
	TArray<USplineMeshComponent*> BarrierMeshes;

	void ClearGenerated();
	USplineMeshComponent* AddPieceMesh(float StartDistance, float EndDistance, UStaticMesh* Mesh, UMaterialInterface* Material, const FVector2D& Offset, const FVector2D& Scale);
};
