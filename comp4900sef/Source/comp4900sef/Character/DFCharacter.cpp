// Dead Fire - COMP 4900SEF Group 3

#include "Character/DFCharacter.h"
#include "Vehicle/DFVehiclePawn.h"
#include "Weapons/DFWeaponComponent.h"
#include "comp4900sef.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/SphereComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Controller.h"
#include "GameFramework/SpringArmComponent.h"
#include "UObject/ConstructorHelpers.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

ADFCharacter::ADFCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	GetCapsuleComponent()->InitCapsuleSize(42.f, 96.0f);

	BaseTurnRate = 45.f;
	BaseLookUpRate = 45.f;

	// The controller rotates the camera, not the character.
	bUseControllerRotationPitch = false;
	bUseControllerRotationYaw = false;
	bUseControllerRotationRoll = false;

	GetCharacterMovement()->bOrientRotationToMovement = true;
	GetCharacterMovement()->RotationRate = FRotator(0.0f, 540.0f, 0.0f);
	GetCharacterMovement()->JumpZVelocity = 600.f;
	GetCharacterMovement()->AirControl = 0.2f;

	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(RootComponent);
	CameraBoom->TargetArmLength = 300.0f;
	CameraBoom->bUsePawnControlRotation = true;

	FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
	FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
	FollowCamera->bUsePawnControlRotation = false;

	// Only its radius is used (see FindNearestEnterableVehicle); it must never catch traces or overlaps.
	InteractionSphere = CreateDefaultSubobject<USphereComponent>(TEXT("InteractionSphere"));
	InteractionSphere->SetupAttachment(RootComponent);
	InteractionSphere->InitSphereRadius(300.f);
	InteractionSphere->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	InteractionSphere->SetGenerateOverlapEvents(false);

	// The engine's Pawn profile ignores Visibility; weapons trace on it, so the body must block it.
	GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);

	Weapon = CreateDefaultSubobject<UDFWeaponComponent>(TEXT("Weapon"));

	// Mannequin from the engine's template pack (free content, copied into /Game/Mannequin).
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyMesh(TEXT("/Game/Mannequin/Character/Mesh/SK_Mannequin.SK_Mannequin"));
	if (BodyMesh.Succeeded())
	{
		GetMesh()->SetSkeletalMesh(BodyMesh.Object);
	}
	static ConstructorHelpers::FClassFinder<UObject> AnimBPClass(TEXT("/Game/Mannequin/Animations/ThirdPerson_AnimBP"));
	if (AnimBPClass.Succeeded())
	{
		GetMesh()->SetAnimationMode(EAnimationMode::AnimationBlueprint);
		GetMesh()->SetAnimInstanceClass(AnimBPClass.Class);
	}
	GetMesh()->SetRelativeLocation(FVector(0.f, 0.f, -97.f));
	GetMesh()->SetRelativeRotation(FRotator(0.f, -90.f, 0.f));

	MaxHealth = 100.f;
	Health = MaxHealth;
	CurrentVehicle = nullptr;
	bIsStowed = false;
}

void ADFCharacter::PostInitializeComponents()
{
	Super::PostInitializeComponents();
	// After Blueprint defaults are applied, so a tuned MaxHealth is the starting health.
	Health = MaxHealth;
}

// ---- Input ------------------------------------------------------------------

void ADFCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	check(PlayerInputComponent);
	PlayerInputComponent->BindAction("Jump", IE_Pressed, this, &ACharacter::Jump);
	PlayerInputComponent->BindAction("Jump", IE_Released, this, &ACharacter::StopJumping);
	PlayerInputComponent->BindAction("Interact", IE_Pressed, this, &ADFCharacter::OnInteract);
	PlayerInputComponent->BindAction("Fire", IE_Pressed, this, &ADFCharacter::OnFire);

	PlayerInputComponent->BindAxis("MoveForward", this, &ADFCharacter::MoveForward);
	PlayerInputComponent->BindAxis("MoveRight", this, &ADFCharacter::MoveRight);
	PlayerInputComponent->BindAxis("Turn", this, &APawn::AddControllerYawInput);
	PlayerInputComponent->BindAxis("TurnRate", this, &ADFCharacter::TurnAtRate);
	PlayerInputComponent->BindAxis("LookUp", this, &APawn::AddControllerPitchInput);
	PlayerInputComponent->BindAxis("LookUpRate", this, &ADFCharacter::LookUpAtRate);
}

void ADFCharacter::TurnAtRate(float Rate)
{
	AddControllerYawInput(Rate * BaseTurnRate * GetWorld()->GetDeltaSeconds());
}

void ADFCharacter::LookUpAtRate(float Rate)
{
	AddControllerPitchInput(Rate * BaseLookUpRate * GetWorld()->GetDeltaSeconds());
}

void ADFCharacter::MoveForward(float Value)
{
	if (Controller != nullptr && Value != 0.0f)
	{
		const FRotator YawRotation(0, Controller->GetControlRotation().Yaw, 0);
		AddMovementInput(FRotationMatrix(YawRotation).GetUnitAxis(EAxis::X), Value);
	}
}

void ADFCharacter::MoveRight(float Value)
{
	if (Controller != nullptr && Value != 0.0f)
	{
		const FRotator YawRotation(0, Controller->GetControlRotation().Yaw, 0);
		AddMovementInput(FRotationMatrix(YawRotation).GetUnitAxis(EAxis::Y), Value);
	}
}

void ADFCharacter::OnInteract()
{
	TryEnterVehicle(nullptr);
}

void ADFCharacter::OnFire()
{
	Fire();
}

// ---- Behaviour --------------------------------------------------------------

bool ADFCharacter::IsInVehicle() const
{
	return CurrentVehicle != nullptr;
}

bool ADFCharacter::IsDead() const
{
	return Health <= 0.f;
}

ADFVehiclePawn* ADFCharacter::FindNearestEnterableVehicle() const
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return nullptr;
	}
	// A level has at most a handful of cars, so a direct scan is cheaper and more
	// predictable than relying on overlap events (which do not run in editor worlds).
	const float Radius = InteractionSphere->GetScaledSphereRadius();
	const FVector Here = GetActorLocation();
	ADFVehiclePawn* Best = nullptr;
	float BestDistance = Radius;
	for (TActorIterator<ADFVehiclePawn> It(World); It; ++It)
	{
		ADFVehiclePawn* Vehicle = *It;
		if (!Vehicle->CanBeEntered())
		{
			continue;
		}
		const float Distance = FVector::Dist(Here, Vehicle->GetActorLocation());
		if (Distance <= BestDistance)
		{
			BestDistance = Distance;
			Best = Vehicle;
		}
	}
	return Best;
}

bool ADFCharacter::TryEnterVehicle(ADFVehiclePawn* Vehicle)
{
	if (IsDead() || IsInVehicle())
	{
		return false;
	}
	if (!Vehicle)
	{
		Vehicle = FindNearestEnterableVehicle();
	}
	return Vehicle != nullptr && Vehicle->EnterVehicle(this);
}

void ADFCharacter::SetStowed(bool bStowed, AActor* AttachTo)
{
	bIsStowed = bStowed;
	if (bStowed)
	{
		GetCharacterMovement()->StopMovementImmediately();
		GetCharacterMovement()->DisableMovement();
		SetActorEnableCollision(false);
		SetActorHiddenInGame(true);
		SetActorTickEnabled(false);
		if (AttachTo)
		{
			AttachToActor(AttachTo, FAttachmentTransformRules::SnapToTargetNotIncludingScale);
		}
	}
	else
	{
		DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
		SetActorHiddenInGame(false);
		SetActorEnableCollision(true);
		SetActorTickEnabled(true);
		GetCharacterMovement()->SetMovementMode(MOVE_Walking);
	}
}

bool ADFCharacter::Fire()
{
	if (IsDead() || IsInVehicle() || !Weapon)
	{
		return false;
	}
	FHitResult Hit;
	return Weapon->Fire(FollowCamera->GetComponentLocation(), FollowCamera->GetForwardVector(), Hit);
}

float ADFCharacter::TakeDamage(float DamageAmount, FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser)
{
	if (IsDead() || DamageAmount <= 0.f)
	{
		return 0.f;
	}
	Super::TakeDamage(DamageAmount, DamageEvent, EventInstigator, DamageCauser);

	Health = FMath::Max(0.f, Health - DamageAmount);
	OnCharacterDamaged(DamageAmount);
	if (Health <= 0.f)
	{
		UE_LOG(LogDeadFire, Log, TEXT("%s died"), *GetName());
		OnCharacterDied();
	}
	return DamageAmount;
}

PRAGMA_ENABLE_DEPRECATION_WARNINGS
