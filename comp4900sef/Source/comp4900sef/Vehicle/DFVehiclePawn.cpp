// Dead Fire - COMP 4900SEF Group 3

#include "Vehicle/DFVehiclePawn.h"
#include "Vehicle/DFVehicleMovementComponent.h"
#include "Vehicle/DFWheelFront.h"
#include "Vehicle/DFWheelRear.h"
#include "Character/DFCharacter.h"
#include "Game/DFRaceGameMode.h"
#include "comp4900sef.h"
#include "Camera/CameraComponent.h"
#include "CollisionQueryParams.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/Controller.h"
#include "GameFramework/SpringArmComponent.h"
#include "UObject/ConstructorHelpers.h"
#include "VehicleWheel.h"
#include "WheeledVehicleMovementComponent4W.h"

#define LOCTEXT_NAMESPACE "DFVehiclePawn"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

const FName ADFVehiclePawn::LookUpBinding("LookUp");
const FName ADFVehiclePawn::LookRightBinding("Turn");

ADFVehiclePawn::ADFVehiclePawn(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer.SetDefaultSubobjectClass<UDFVehicleMovementComponent>(AWheeledVehicle::VehicleMovementComponentName))
{
	PrimaryActorTick.bCanEverTick = true;

	// Sedan from the engine's Vehicle template pack (free content, copied into /Game/Vehicle).
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> CarMesh(TEXT("/Game/Vehicle/Sedan/Sedan_SkelMesh.Sedan_SkelMesh"));
	if (CarMesh.Succeeded())
	{
		GetMesh()->SetSkeletalMesh(CarMesh.Object);
	}
	static ConstructorHelpers::FClassFinder<UObject> AnimBPClass(TEXT("/Game/Vehicle/Sedan/Sedan_AnimBP"));
	if (AnimBPClass.Succeeded())
	{
		GetMesh()->SetAnimationMode(EAnimationMode::AnimationBlueprint);
		GetMesh()->SetAnimInstanceClass(AnimBPClass.Class);
	}
	// Checkpoints are overlap triggers: the car's body has to report overlaps to pass them.
	GetMesh()->SetGenerateOverlapEvents(true);

	UWheeledVehicleMovementComponent4W* Vehicle4W = CastChecked<UWheeledVehicleMovementComponent4W>(GetVehicleMovement());
	check(Vehicle4W->WheelSetups.Num() == 4);

	static const FName WheelBones[4] = { TEXT("Wheel_Front_Left"), TEXT("Wheel_Front_Right"), TEXT("Wheel_Rear_Left"), TEXT("Wheel_Rear_Right") };
	for (int32 i = 0; i < 4; ++i)
	{
		Vehicle4W->WheelSetups[i].WheelClass = (i < 2) ? UDFWheelFront::StaticClass() : UDFWheelRear::StaticClass();
		Vehicle4W->WheelSetups[i].BoneName = WheelBones[i];
		Vehicle4W->WheelSetups[i].AdditionalOffset = FVector(0.f, (i % 2 == 0) ? -12.f : 12.f, 0.f);
	}

	// Arcade-leaning tuning: 4WD limited slip, automatic gearbox, lower centre of mass.
	Vehicle4W->MaxEngineRPM = 5700.0f;
	Vehicle4W->EngineSetup.TorqueCurve.GetRichCurve()->Reset();
	Vehicle4W->EngineSetup.TorqueCurve.GetRichCurve()->AddKey(0.0f, 400.0f);
	Vehicle4W->EngineSetup.TorqueCurve.GetRichCurve()->AddKey(1890.0f, 500.0f);
	Vehicle4W->EngineSetup.TorqueCurve.GetRichCurve()->AddKey(5730.0f, 400.0f);
	Vehicle4W->SteeringCurve.GetRichCurve()->Reset();
	Vehicle4W->SteeringCurve.GetRichCurve()->AddKey(0.0f, 1.0f);
	Vehicle4W->SteeringCurve.GetRichCurve()->AddKey(40.0f, 0.7f);
	Vehicle4W->SteeringCurve.GetRichCurve()->AddKey(120.0f, 0.6f);
	Vehicle4W->DifferentialSetup.DifferentialType = EVehicleDifferential4W::LimitedSlip_4W;
	Vehicle4W->DifferentialSetup.FrontRearSplit = 0.65f;
	Vehicle4W->TransmissionSetup.bUseGearAutoBox = true;
	Vehicle4W->TransmissionSetup.GearSwitchTime = 0.15f;
	Vehicle4W->TransmissionSetup.GearAutoBoxLatency = 1.0f;
	GetMesh()->BodyInstance.COMNudge = FVector(0.f, 0.f, -30.f);

	// Chase camera.
	SpringArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("SpringArm"));
	SpringArm->SetupAttachment(RootComponent);
	SpringArm->TargetOffset = FVector(0.f, 0.f, 200.f);
	SpringArm->SetRelativeRotation(FRotator(-15.f, 0.f, 0.f));
	SpringArm->TargetArmLength = 600.0f;
	SpringArm->bEnableCameraRotationLag = true;
	SpringArm->CameraRotationLagSpeed = 7.f;
	SpringArm->bInheritPitch = false;
	SpringArm->bInheritRoll = false;

	ChaseCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("ChaseCamera"));
	ChaseCamera->SetupAttachment(SpringArm, USpringArmComponent::SocketName);
	ChaseCamera->bUsePawnControlRotation = false;
	ChaseCamera->FieldOfView = 90.f;

	// In-car camera.
	InternalCameraBase = CreateDefaultSubobject<USceneComponent>(TEXT("InternalCameraBase"));
	InternalCameraBase->SetRelativeLocation(FVector(0.0f, -40.0f, 120.0f));
	InternalCameraBase->SetupAttachment(GetMesh());

	InternalCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("InternalCamera"));
	InternalCamera->bUsePawnControlRotation = false;
	InternalCamera->FieldOfView = 90.f;
	InternalCamera->SetupAttachment(InternalCameraBase);

	// Health defaults (spec section 4). Starting values are applied in PostInitializeComponents
	// so a Blueprint child's MaxHealth / TireMaxHealth take effect.
	MaxHealth = 100.f;
	TireMaxHealth = 30.f;
	BlownTireSpeedScale = 0.8f;
	TireHitRadius = 60.f;
	bIsDestroyed = false;
	LastDamageInstigator = nullptr;
	Tires.SetNum(4);
	for (int32 i = 0; i < 4; ++i)
	{
		Tires[i].BoneName = WheelBones[i];
	}
	ResetHealth();

	// Enter/exit defaults.
	ExitMaxSpeedKPH = 10.f;
	ExitSideOffset = 220.f;
	ExitUpOffset = 100.f;
	ExitBehindOffset = 350.f;
	ExitGroundSearchDistance = 300.f;
	ExitProbeRadius = 42.f;
	ExitProbeHalfHeight = 96.f;
	Occupant = nullptr;
	LastDriver = nullptr;

	bInCarCameraActive = false;
	bInReverseGear = false;
}

// ---- Input ------------------------------------------------------------------

void ADFVehiclePawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);
	check(PlayerInputComponent);

	PlayerInputComponent->BindAxis("MoveForward", this, &ADFVehiclePawn::MoveForward);
	PlayerInputComponent->BindAxis("MoveRight", this, &ADFVehiclePawn::MoveRight);
	PlayerInputComponent->BindAxis(LookUpBinding);
	PlayerInputComponent->BindAxis(LookRightBinding);

	PlayerInputComponent->BindAction("Handbrake", IE_Pressed, this, &ADFVehiclePawn::OnHandbrakePressed);
	PlayerInputComponent->BindAction("Handbrake", IE_Released, this, &ADFVehiclePawn::OnHandbrakeReleased);
	PlayerInputComponent->BindAction("SwitchCamera", IE_Pressed, this, &ADFVehiclePawn::OnToggleCamera);
	PlayerInputComponent->BindAction("Interact", IE_Pressed, this, &ADFVehiclePawn::OnInteract);
}

void ADFVehiclePawn::MoveForward(float Val)
{
	if (bIsDestroyed)
	{
		return;
	}
	GetVehicleMovementComponent()->SetThrottleInput(Val * GetThrottleScale());
}

void ADFVehiclePawn::MoveRight(float Val)
{
	if (bIsDestroyed)
	{
		return;
	}
	GetVehicleMovementComponent()->SetSteeringInput(Val);
}

void ADFVehiclePawn::ReleaseControls()
{
	if (UWheeledVehicleMovementComponent* Movement = GetVehicleMovementComponent())
	{
		Movement->SetThrottleInput(0.f);
		Movement->SetSteeringInput(0.f);
		Movement->SetHandbrakeInput(true);
	}
}

void ADFVehiclePawn::TeleportAndStop(const FTransform& Transform)
{
	// Location and rotation only, so a scaled transform never scales the car; TeleportPhysics moves the body along.
	SetActorLocationAndRotation(Transform.GetLocation(), Transform.GetRotation(), false, nullptr, ETeleportType::TeleportPhysics);
	GetMesh()->SetPhysicsLinearVelocity(FVector::ZeroVector);
	GetMesh()->SetPhysicsAngularVelocityInDegrees(FVector::ZeroVector);
	ReleaseControls();
}

void ADFVehiclePawn::OnHandbrakePressed()
{
	GetVehicleMovementComponent()->SetHandbrakeInput(true);
}

void ADFVehiclePawn::OnHandbrakeReleased()
{
	// A wreck keeps the handbrake DestroyVehicle pulled.
	if (bIsDestroyed)
	{
		return;
	}
	GetVehicleMovementComponent()->SetHandbrakeInput(false);
}

void ADFVehiclePawn::OnToggleCamera()
{
	EnableInCarView(!bInCarCameraActive);
}

void ADFVehiclePawn::OnInteract()
{
	ExitVehicle();
}

void ADFVehiclePawn::EnableInCarView(bool bState, bool bForce)
{
	if (bState != bInCarCameraActive || bForce)
	{
		bInCarCameraActive = bState;
		if (bState)
		{
			ChaseCamera->Deactivate();
			InternalCamera->Activate();
		}
		else
		{
			InternalCamera->Deactivate();
			ChaseCamera->Activate();
		}
	}
}

// ---- Lifecycle --------------------------------------------------------------

void ADFVehiclePawn::ResetHealth()
{
	Health = MaxHealth;
	for (FDFTireState& Tire : Tires)
	{
		Tire.MaxHealth = TireMaxHealth;
		Tire.Health = TireMaxHealth;
		Tire.bBlown = false;
	}
}

void ADFVehiclePawn::PostInitializeComponents()
{
	Super::PostInitializeComponents();
	// Runs after Blueprint defaults are applied, so tuned MaxHealth / TireMaxHealth become the starting values.
	ResetHealth();
}

void ADFVehiclePawn::PossessedBy(AController* NewController)
{
	Super::PossessedBy(NewController);
	LastDriver = NewController;
}

void ADFVehiclePawn::BeginPlay()
{
	Super::BeginPlay();
	EnableInCarView(false, true);
}

void ADFVehiclePawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	bInReverseGear = GetVehicleMovement()->GetCurrentGear() < 0;

	if (InputComponent && bInCarCameraActive)
	{
		FRotator HeadRotation = InternalCamera->GetRelativeRotation();
		HeadRotation.Pitch += InputComponent->GetAxisValue(LookUpBinding);
		HeadRotation.Yaw += InputComponent->GetAxisValue(LookRightBinding);
		InternalCamera->SetRelativeRotation(HeadRotation);
	}
}

// ---- Queries ----------------------------------------------------------------

float ADFVehiclePawn::GetSpeedKPH() const
{
	const UWheeledVehicleMovementComponent* Movement = GetVehicleMovement();
	return Movement ? FMath::Abs(Movement->GetForwardSpeed()) * 0.036f : 0.f;
}

FText ADFVehiclePawn::GetGearDisplayText() const
{
	const int32 Gear = GetVehicleMovement() ? GetVehicleMovement()->GetCurrentGear() : 0;
	if (Gear < 0)
	{
		return LOCTEXT("ReverseGear", "R");
	}
	if (Gear == 0)
	{
		return LOCTEXT("NeutralGear", "N");
	}
	return FText::AsNumber(Gear);
}

int32 ADFVehiclePawn::GetBlownTireCount() const
{
	int32 Count = 0;
	for (const FDFTireState& Tire : Tires)
	{
		Count += Tire.bBlown ? 1 : 0;
	}
	return Count;
}

float ADFVehiclePawn::GetThrottleScale() const
{
	return FMath::Pow(BlownTireSpeedScale, static_cast<float>(GetBlownTireCount()));
}

FVector ADFVehiclePawn::GetWheelWorldLocation(int32 TireIndex) const
{
	if (!Tires.IsValidIndex(TireIndex))
	{
		return GetActorLocation();
	}
	// Simulated wheel position when the PhysX vehicle exists (in game), bone position otherwise (editor, tests).
	const UWheeledVehicleMovementComponent* Movement = GetVehicleMovement();
	if (Movement && Movement->Wheels.IsValidIndex(TireIndex) && Movement->Wheels[TireIndex])
	{
		return Movement->Wheels[TireIndex]->Location;
	}
	return GetMesh()->GetBoneLocation(Tires[TireIndex].BoneName);
}

int32 ADFVehiclePawn::FindTireIndexForHit(FName BoneName, const FVector& ImpactPoint) const
{
	if (BoneName != NAME_None)
	{
		for (int32 i = 0; i < Tires.Num(); ++i)
		{
			if (Tires[i].BoneName == BoneName)
			{
				return i;
			}
		}
	}

	int32 Best = INDEX_NONE;
	float BestDistance = TireHitRadius;
	for (int32 i = 0; i < Tires.Num(); ++i)
	{
		const float Distance = FVector::Dist(GetWheelWorldLocation(i), ImpactPoint);
		if (Distance <= BestDistance)
		{
			BestDistance = Distance;
			Best = i;
		}
	}
	return Best;
}

bool ADFVehiclePawn::IsBelowExitSpeed(float KPH) const
{
	return FMath::Abs(KPH) < ExitMaxSpeedKPH;
}

bool ADFVehiclePawn::CanBeEntered() const
{
	return !bIsDestroyed && Occupant == nullptr;
}

bool ADFVehiclePawn::CanExit() const
{
	// Full velocity, not just forward speed: a car sliding sideways is still moving.
	const float SpeedKPH = GetVelocity().Size() * 0.036f;
	return Occupant != nullptr && !bIsDestroyed && IsBelowExitSpeed(SpeedKPH);
}

bool ADFVehiclePawn::IsExitSpotFree(const FVector& Candidate, FVector& OutGroundedLocation) const
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return false;
	}
	FCollisionQueryParams Params(SCENE_QUERY_STAT(DFExitSpot), false, this);
	if (Occupant)
	{
		Params.AddIgnoredActor(Occupant);
	}

	// 1. The way from the car to the spot must be clear, or the character would end up behind a wall.
	const FVector From = GetActorLocation() + FVector::UpVector * ExitUpOffset;
	FHitResult PathHit;
	if (World->SweepSingleByChannel(PathHit, From, Candidate, FQuat::Identity, ECC_Pawn, FCollisionShape::MakeSphere(ExitProbeRadius * 0.5f), Params))
	{
		return false;
	}

	// 2. There must be ground under the spot within a short drop.
	FHitResult GroundHit;
	const FVector Top = Candidate + FVector::UpVector * ExitProbeHalfHeight;
	const FVector Bottom = Candidate - FVector::UpVector * ExitGroundSearchDistance;
	if (!World->LineTraceSingleByChannel(GroundHit, Top, Bottom, ECC_Pawn, Params))
	{
		return false;
	}

	// 3. The character's capsule must fit standing on that ground.
	const FVector Grounded = GroundHit.ImpactPoint + FVector::UpVector * (ExitProbeHalfHeight + 2.f);
	const FCollisionShape Capsule = FCollisionShape::MakeCapsule(ExitProbeRadius, ExitProbeHalfHeight);
	if (World->OverlapBlockingTestByChannel(Grounded, FQuat::Identity, ECC_Pawn, Capsule, Params))
	{
		return false;
	}

	OutGroundedLocation = Grounded;
	return true;
}

bool ADFVehiclePawn::FindExitLocation(FVector& OutLocation) const
{
	const FVector Base = GetActorLocation();
	const FVector Up = FVector::UpVector * ExitUpOffset;
	const FVector Candidates[3] =
	{
		Base - GetActorRightVector() * ExitSideOffset + Up,   // driver side first
		Base + GetActorRightVector() * ExitSideOffset + Up,
		Base - GetActorForwardVector() * ExitBehindOffset + Up
	};
	for (const FVector& Candidate : Candidates)
	{
		FVector Grounded;
		if (IsExitSpotFree(Candidate, Grounded))
		{
			OutLocation = Grounded;
			return true;
		}
	}
	return false;
}

bool ADFVehiclePawn::EnterVehicle(ADFCharacter* Character)
{
	if (!Character || !CanBeEntered() || Character->IsInVehicle() || Character->IsDead())
	{
		return false;
	}

	Occupant = Character;
	Character->CurrentVehicle = this;
	Character->SetStowed(true, this);

	if (UWheeledVehicleMovementComponent* Movement = GetVehicleMovement())
	{
		Movement->SetHandbrakeInput(false);
	}

	// Hand control to the car. NPC cars never reach this: their characters have no controller.
	if (AController* CharacterController = Character->GetController())
	{
		CharacterController->Possess(this);
	}

	UE_LOG(LogDeadFire, Log, TEXT("%s entered %s"), *Character->GetName(), *GetName());
	OnOccupantEntered(Character);
	Character->OnEnteredVehicle(this);
	return true;
}

bool ADFVehiclePawn::ExitVehicle()
{
	if (!CanExit())
	{
		return false;
	}
	FVector ExitLocation;
	if (!FindExitLocation(ExitLocation))
	{
		UE_LOG(LogDeadFire, Log, TEXT("%s: no free spot to exit"), *GetName());
		return false;
	}

	ADFCharacter* Character = Occupant;

	// Park the car so it does not roll away on its own.
	ReleaseControls();

	Occupant = nullptr;
	Character->CurrentVehicle = nullptr;
	// Move first, then restore collision, so the character never overlaps anything at the car's position.
	Character->DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
	Character->SetActorLocationAndRotation(ExitLocation, FRotator(0.f, GetActorRotation().Yaw, 0.f), false, nullptr, ETeleportType::TeleportPhysics);
	Character->SetStowed(false, nullptr);

	if (AController* MyController = GetController())
	{
		MyController->Possess(Character);
	}

	UE_LOG(LogDeadFire, Log, TEXT("%s exited %s"), *Character->GetName(), *GetName());
	OnOccupantExited(Character);
	Character->OnExitedVehicle(this);
	return true;
}

void ADFVehiclePawn::EjectOccupant()
{
	ADFCharacter* Character = Occupant;
	if (!Character)
	{
		return;
	}
	Occupant = nullptr;
	Character->CurrentVehicle = nullptr;
	Character->SetStowed(false, nullptr);
	UE_LOG(LogDeadFire, Log, TEXT("%s ejected from %s"), *Character->GetName(), *GetName());
}

// ---- Damage -----------------------------------------------------------------

float ADFVehiclePawn::TakeDamage(float DamageAmount, FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser)
{
	if (bIsDestroyed || DamageAmount <= 0.f)
	{
		return 0.f;
	}

	// Lets the generic AnyDamage/PointDamage Blueprint events fire; the amount is not altered by the base class.
	Super::TakeDamage(DamageAmount, DamageEvent, EventInstigator, DamageCauser);

	LastDamageInstigator = EventInstigator;

	int32 TireIndex = INDEX_NONE;
	if (DamageEvent.IsOfType(FPointDamageEvent::ClassID))
	{
		const FPointDamageEvent* PointEvent = static_cast<const FPointDamageEvent*>(&DamageEvent);
		TireIndex = FindTireIndexForHit(PointEvent->HitInfo.BoneName, PointEvent->HitInfo.ImpactPoint);
	}

	if (TireIndex != INDEX_NONE)
	{
		ApplyTireDamage(TireIndex, DamageAmount);
	}
	else
	{
		ApplyBodyDamage(DamageAmount);
	}
	OnVehicleDamaged(DamageAmount, TireIndex);
	return DamageAmount;
}

void ADFVehiclePawn::ApplyTireDamage(int32 TireIndex, float Damage)
{
	FDFTireState& Tire = Tires[TireIndex];
	if (Tire.bBlown)
	{
		return;
	}
	Tire.Health = FMath::Max(0.f, Tire.Health - Damage);
	if (Tire.Health <= 0.f)
	{
		Tire.bBlown = true;
		UE_LOG(LogDeadFire, Log, TEXT("%s: tire %d (%s) blown"), *GetName(), TireIndex, *Tire.BoneName.ToString());
		OnTireBlown(TireIndex);
	}
}

void ADFVehiclePawn::ApplyBodyDamage(float Damage)
{
	Health = FMath::Max(0.f, Health - Damage);
	if (Health <= 0.f)
	{
		DestroyVehicle();
	}
}

void ADFVehiclePawn::DestroyVehicle()
{
	if (bIsDestroyed)
	{
		return;
	}
	bIsDestroyed = true;
	ReleaseControls();
	UE_LOG(LogDeadFire, Log, TEXT("%s destroyed"), *GetName());
	OnVehicleDestroyed();
	OnDestroyedDelegate.Broadcast(this, LastDamageInstigator);

	// The race counts the death (the driver's, or the last driver's for a parked car) and the kill.
	UWorld* World = GetWorld();
	if (ADFRaceGameMode* GameMode = World ? World->GetAuthGameMode<ADFRaceGameMode>() : nullptr)
	{
		GameMode->NotifyVehicleDestroyed(this, LastDamageInstigator);
	}
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS

#undef LOCTEXT_NAMESPACE
