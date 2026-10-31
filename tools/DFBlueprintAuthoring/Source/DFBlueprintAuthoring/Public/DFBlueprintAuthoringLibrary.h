// Dead Fire authoring plugin: Python-callable Blueprint authoring for UE 4.27.
// Every function is static and BlueprintCallable so the editor's Python exposes it as
// unreal.DFBlueprintAuthoringLibrary.<snake_case_name>(...). Mutating functions return a string: empty on
// success, "exists" when the thing was already there, or "ERROR: ..." on failure (a bool return with an
// out-string would make the Python wrapper drop the message on failure). Compile returns
// "errors=N warnings=M" followed by one line per compiler message.
//
// TypeSpec grammar (used by every *Type* argument):
//   bool | int | int64 | float | string | name | text | byte
//   object:<class path>   e.g. object:/Script/Engine.Actor  or  object:/Game/DeadFire/Blueprints/BP_DFVehicle.BP_DFVehicle_C
//   class:<class path>    (a Class reference whose metaclass is the given class)
//   struct:<struct path>  e.g. struct:/Script/CoreUObject.Vector  or  struct:/Game/DeadFire/Data/S_DFTireState.S_DFTireState
//   enum:<enum path>      e.g. enum:/Game/DeadFire/Data/E_DFRaceEndReason.E_DFRaceEndReason
//   array<...>            any of the above as an array
// Parameter grammar ("Name:TypeSpec" or "Name:TypeSpec=Default") is used by AddFunction and AddEventDispatcher.
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "DFBlueprintAuthoringLibrary.generated.h"

class UBlueprint;
class UUserDefinedStruct;
class UUserDefinedEnum;
class UEdGraph;
class UEdGraphNode;
class UActorComponent;
class UWidget;
class UMaterialInterface;
class UFont;
class UFontFace;
struct FEdGraphPinType;

UCLASS()
class DFBLUEPRINTAUTHORING_API UDFBlueprintAuthoringLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Adds a member variable. Idempotent: an existing variable of that name is left alone and reported in OutError. */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString AddVariable(UBlueprint* Blueprint, FName Name, const FString& TypeSpec, const FString& DefaultValue, const FString& Category, bool bInstanceEditable);

	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString RemoveVariable(UBlueprint* Blueprint, FName Name);

	/** Adds a function graph with the given inputs/outputs ("Name:TypeSpec[=Default]"). Idempotent on the name. */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString AddFunction(UBlueprint* Blueprint, FName Name, const TArray<FString>& Inputs, const TArray<FString>& Outputs, bool bPure, const FString& Category);

	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString RemoveFunction(UBlueprint* Blueprint, FName Name);

	/** Adds a local variable to a function graph (nodes reference it with MemberScope = function name). */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString AddLocalVariable(UBlueprint* Blueprint, FName FunctionName, FName Name, const FString& TypeSpec, const FString& DefaultValue);

	/** Adds an event dispatcher with the given parameters ("Name:TypeSpec"). Idempotent on the name. */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString AddEventDispatcher(UBlueprint* Blueprint, FName Name, const TArray<FString>& Params);

	/** Adds a member to a user-defined struct (the factory's placeholder MemberVar_0 is removed on the first call). */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString AddStructMember(UUserDefinedStruct* Struct, const FString& Name, const FString& TypeSpec, const FString& DefaultValue);

	/** JSON: members of a user-defined struct with their display name and real (GUID-suffixed) property name. */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString DescribeStruct(UUserDefinedStruct* Struct);

	/** Adds an enumerator (the factory's placeholder NewEnumerator0 is renamed on the first call). */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString AddEnumValue(UUserDefinedEnum* Enum, const FString& DisplayName);

	/**
	 * Imports nodes from the editor's clipboard text into a graph ("EventGraph", "UserConstructionScript", a function name
	 * or a dispatcher name), then reconstructs them so pins match the real signatures. Links inside the text are kept.
	 */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString ImportNodes(UBlueprint* Blueprint, FName GraphName, const FString& Text);

	/** Connects two pins. Node ids are object names from the import ("K2Node_CallFunction_0"), or "entry" / "result" for a function's terminators. */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString ConnectPins(UBlueprint* Blueprint, FName GraphName, const FString& NodeA, const FString& PinA, const FString& NodeB, const FString& PinB);

	/** Sets a pin's default value (literal text) on a node. */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString SetPinDefault(UBlueprint* Blueprint, FName GraphName, const FString& Node, const FString& Pin, const FString& Value);

	/** Removes every node from a graph except function entry/result terminators (used before re-importing a regenerated graph). */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString ClearGraph(UBlueprint* Blueprint, FName GraphName);

	/** JSON: variables (name, type, default, category), functions, dispatchers, graphs, components (name, class, socket). */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString DescribeBlueprint(UBlueprint* Blueprint);

	/** JSON: nodes with class, title, pins (name, direction, type, default, links) and any node error. */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString DescribeGraph(UBlueprint* Blueprint, FName GraphName);

	/** Adds a component to the Blueprint's construction script (root when ParentComponent is None). Idempotent on the name. */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString AddComponent(UBlueprint* Blueprint, FName Name, const FString& ClassPath, FName ParentComponent);

	/**
	 * Sets the socket (or bone) of its parent that a construction-script component attaches to (the SCS node's
	 * AttachToName); None clears it. "exists" when it already attaches there.
	 */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString SetComponentSocket(UBlueprint* Blueprint, FName Name, FName Socket);

	/** The component's template object, so Python can set_editor_property on it. */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static UActorComponent* GetComponentTemplate(UBlueprint* Blueprint, FName Name);

	/**
	 * Spawns a Landscape in the context object's world from a raw heightmap: Size x Size little-endian uint16 samples,
	 * row-major with the row index along Y, 32768 = the actor's Z (world Z = (h - 32768) / 128 * Scale.Z). Location is
	 * the actor location, i.e. vertex (0, 0); Scale.X/Y is the quad size in cm. Size must be 126 * N + 1 (components of
	 * 2 x 2 sections of 63 quads). Uses ALandscape::Import with a new GUID, no weight layers and no edit layers, so
	 * heights and collision exist when it returns; sets the landscape material and the actor label.
	 */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString CreateLandscapeFromRaw(UObject* WorldContextObject, const FString& RawPath, int32 Size, FVector Location, FVector Scale, UMaterialInterface* Material, const FString& Label);

	/** Makes Face the default typeface entry ("Default") of a runtime composite font. "exists" when it already is. */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString SetFontFace(UFont* Font, UFontFace* Face);

	/**
	 * Widget Blueprints: empties the designer tree and gives it a fresh root panel (e.g. /Script/UMG.CanvasPanel).
	 * Returns the root so Python can set its properties.
	 */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static UWidget* ResetWidgetTree(UBlueprint* WidgetBlueprint, const FString& RootClassPath, FName RootName);

	/**
	 * Widget Blueprints: adds a widget of ClassPath under the named panel (None = the root) and marks it "Is Variable",
	 * so graphs can use it by name. Returns the widget; Python sets its properties and its Slot's layout.
	 */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static UWidget* AddWidget(UBlueprint* WidgetBlueprint, FName Name, const FString& ClassPath, FName ParentName);

	/** Compiles; returns true when there are no errors. OutMessages holds every compiler message. */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString Compile(UBlueprint* Blueprint);

	/** Moves a node (object name, or "entry" / "result" for a function's terminators) to a graph position; the generator lays graphs out itself. */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString SetNodePosition(UBlueprint* Blueprint, FName GraphName, const FString& Node, int32 X, int32 Y);

	/** Sets a function's description (the tooltip shown in My Blueprint and on call nodes). */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString SetFunctionDescription(UBlueprint* Blueprint, FName FunctionName, const FString& Description);

	/** Opens the Blueprint editor on the named graph (for looking at a generated graph or taking a screenshot of it). */
	UFUNCTION(BlueprintCallable, Category = "DF Authoring")
	static FString FocusGraph(UBlueprint* Blueprint, FName GraphName);

	// helpers (not exposed)
	static bool ParseTypeSpec(const FString& Spec, FEdGraphPinType& OutType, FString& OutError);
	static UEdGraph* FindGraph(UBlueprint* Blueprint, FName GraphName);
	static UEdGraphNode* FindNode(UEdGraph* Graph, const FString& NodeId);
};
