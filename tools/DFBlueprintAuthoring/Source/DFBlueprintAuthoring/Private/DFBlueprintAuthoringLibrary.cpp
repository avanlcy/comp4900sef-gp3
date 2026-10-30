#include "DFBlueprintAuthoringLibrary.h"

#include "Dom/JsonObject.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "EdGraphUtilities.h"
#include "Engine/Blueprint.h"
#include "Engine/SCS_Node.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/UserDefinedEnum.h"
#include "Engine/UserDefinedStruct.h"
#include "K2Node.h"
#include "K2Node_Event.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_FunctionResult.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/CompilerResultsLog.h"
#include "Kismet2/EnumEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Kismet2/StructureEditorUtils.h"
#include "Logging/TokenizedMessage.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/UObjectIterator.h"
#include "UserDefinedStructure/UserDefinedStructEditorData.h"
#include "WidgetBlueprint.h"
#include "Blueprint/WidgetTree.h"
#include "Components/PanelWidget.h"
#include "Components/Widget.h"

namespace
{
	template <class T>
	T* LoadByPath(const FString& Path)
	{
		T* Found = LoadObject<T>(nullptr, *Path);
		if (!Found)
		{
			Found = FindObject<T>(ANY_PACKAGE, *Path);
		}
		return Found;
	}

	bool ParseParam(const FString& Param, FName& OutName, FEdGraphPinType& OutType, FString& OutDefault, FString& OutError)
	{
		FString NameStr, Rest;
		if (!Param.Split(TEXT(":"), &NameStr, &Rest))
		{
			OutError = FString::Printf(TEXT("parameter '%s' is not Name:TypeSpec"), *Param);
			return false;
		}
		FString TypeStr = Rest;
		OutDefault.Empty();
		int32 EqIdx;
		if (Rest.FindChar(TEXT('='), EqIdx))
		{
			TypeStr = Rest.Left(EqIdx);
			OutDefault = Rest.Mid(EqIdx + 1);
		}
		OutName = FName(*NameStr.TrimStartAndEnd());
		return UDFBlueprintAuthoringLibrary::ParseTypeSpec(TypeStr, OutType, OutError);
	}

	FString TypeToString(const FEdGraphPinType& T)
	{
		FString S = T.PinCategory.ToString();
		if (T.PinSubCategoryObject.IsValid())
		{
			S += TEXT(":") + T.PinSubCategoryObject->GetPathName();
		}
		else if (!T.PinSubCategory.IsNone())
		{
			S += TEXT(":") + T.PinSubCategory.ToString();
		}
		if (T.ContainerType == EPinContainerType::Array)
		{
			S = TEXT("array<") + S + TEXT(">");
		}
		return S;
	}

	FString ToJson(const TSharedRef<FJsonObject>& Obj)
	{
		FString Out;
		TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
			TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Out);
		FJsonSerializer::Serialize(Obj, Writer);
		return Out;
	}

	UK2Node_FunctionEntry* FindEntry(UEdGraph* Graph)
	{
		TArray<UK2Node_FunctionEntry*> Entries;
		Graph->GetNodesOfClass(Entries);
		return Entries.Num() ? Entries[0] : nullptr;
	}
}

bool UDFBlueprintAuthoringLibrary::ParseTypeSpec(const FString& SpecIn, FEdGraphPinType& Out, FString& OutError)
{
	FString Spec = SpecIn.TrimStartAndEnd();
	Out = FEdGraphPinType();
	if (Spec.StartsWith(TEXT("array<")) && Spec.EndsWith(TEXT(">")))
	{
		Spec = Spec.Mid(6, Spec.Len() - 7);
		Out.ContainerType = EPinContainerType::Array;
	}
	FString Cat = Spec, Arg;
	Spec.Split(TEXT(":"), &Cat, &Arg);
	Cat = Cat.ToLower().TrimStartAndEnd();
	Arg = Arg.TrimStartAndEnd();

	if (Cat == TEXT("bool")) Out.PinCategory = UEdGraphSchema_K2::PC_Boolean;
	else if (Cat == TEXT("int")) Out.PinCategory = UEdGraphSchema_K2::PC_Int;
	else if (Cat == TEXT("int64")) Out.PinCategory = UEdGraphSchema_K2::PC_Int64;
	else if (Cat == TEXT("float")) Out.PinCategory = UEdGraphSchema_K2::PC_Float;
	else if (Cat == TEXT("string")) Out.PinCategory = UEdGraphSchema_K2::PC_String;
	else if (Cat == TEXT("name")) Out.PinCategory = UEdGraphSchema_K2::PC_Name;
	else if (Cat == TEXT("text")) Out.PinCategory = UEdGraphSchema_K2::PC_Text;
	else if (Cat == TEXT("byte")) Out.PinCategory = UEdGraphSchema_K2::PC_Byte;
	else if (Cat == TEXT("object") || Cat == TEXT("class"))
	{
		UClass* C = LoadByPath<UClass>(Arg);
		if (!C) { OutError = FString::Printf(TEXT("class not found: %s"), *Arg); return false; }
		Out.PinCategory = (Cat == TEXT("object")) ? UEdGraphSchema_K2::PC_Object : UEdGraphSchema_K2::PC_Class;
		Out.PinSubCategoryObject = C;
	}
	else if (Cat == TEXT("struct"))
	{
		UScriptStruct* S = LoadByPath<UScriptStruct>(Arg);
		if (!S) { OutError = FString::Printf(TEXT("struct not found: %s"), *Arg); return false; }
		Out.PinCategory = UEdGraphSchema_K2::PC_Struct;
		Out.PinSubCategoryObject = S;
	}
	else if (Cat == TEXT("enum"))
	{
		UEnum* E = LoadByPath<UEnum>(Arg);
		if (!E) { OutError = FString::Printf(TEXT("enum not found: %s"), *Arg); return false; }
		Out.PinCategory = UEdGraphSchema_K2::PC_Byte;
		Out.PinSubCategoryObject = E;
	}
	else
	{
		OutError = FString::Printf(TEXT("unknown type spec: %s"), *SpecIn);
		return false;
	}
	return true;
}

UEdGraph* UDFBlueprintAuthoringLibrary::FindGraph(UBlueprint* BP, FName GraphName)
{
	if (!BP) return nullptr;
	const FString Name = GraphName.ToString();
	if (Name == TEXT("EventGraph") && BP->UbergraphPages.Num() > 0)
	{
		return BP->UbergraphPages[0];
	}
	if (Name == TEXT("UserConstructionScript") || Name == TEXT("ConstructionScript"))
	{
		return FBlueprintEditorUtils::FindUserConstructionScript(BP);
	}
	TArray<UEdGraph*> All;
	BP->GetAllGraphs(All);
	for (UEdGraph* G : All)
	{
		if (G && G->GetFName() == GraphName) return G;
	}
	return nullptr;
}

UEdGraphNode* UDFBlueprintAuthoringLibrary::FindNode(UEdGraph* Graph, const FString& NodeId)
{
	if (!Graph) return nullptr;
	if (NodeId == TEXT("entry"))
	{
		return FindEntry(Graph);
	}
	if (NodeId == TEXT("result"))
	{
		TArray<UK2Node_FunctionResult*> Results;
		Graph->GetNodesOfClass(Results);
		return Results.Num() ? Results[0] : nullptr;
	}
	for (UEdGraphNode* N : Graph->Nodes)
	{
		if (N && N->GetName() == NodeId) return N;
	}
	return nullptr;
}

FString UDFBlueprintAuthoringLibrary::AddVariable(UBlueprint* BP, FName Name, const FString& TypeSpec, const FString& DefaultValue, const FString& Category, bool bInstanceEditable)
{
	FString OutError;
	if (!BP) { OutError = TEXT("null blueprint"); return TEXT("ERROR: ") + OutError; }
	if (FBlueprintEditorUtils::FindNewVariableIndex(BP, Name) != INDEX_NONE)
	{
		OutError = TEXT("exists");
		return OutError;
	}
	FEdGraphPinType Type;
	if (!ParseTypeSpec(TypeSpec, Type, OutError)) return TEXT("ERROR: ") + OutError;
	BP->Modify();
	if (!FBlueprintEditorUtils::AddMemberVariable(BP, Name, Type, DefaultValue))
	{
		OutError = TEXT("AddMemberVariable failed");
		return TEXT("ERROR: ") + OutError;
	}
	if (!Category.IsEmpty())
	{
		FBlueprintEditorUtils::SetBlueprintVariableCategory(BP, Name, nullptr, FText::FromString(Category), true);
	}
	FBlueprintEditorUtils::SetBlueprintOnlyEditableFlag(BP, Name, !bInstanceEditable);
	return OutError;
}

FString UDFBlueprintAuthoringLibrary::RemoveVariable(UBlueprint* BP, FName Name)
{
	FString OutError;
	if (!BP) { OutError = TEXT("null blueprint"); return TEXT("ERROR: ") + OutError; }
	if (FBlueprintEditorUtils::FindNewVariableIndex(BP, Name) == INDEX_NONE) { OutError = TEXT("not found"); return TEXT("ERROR: ") + OutError; }
	FBlueprintEditorUtils::RemoveMemberVariable(BP, Name);
	return OutError;
}

FString UDFBlueprintAuthoringLibrary::AddFunction(UBlueprint* BP, FName Name, const TArray<FString>& Inputs, const TArray<FString>& Outputs, bool bPure, const FString& Category)
{
	FString OutError;
	if (!BP) { OutError = TEXT("null blueprint"); return TEXT("ERROR: ") + OutError; }
	if (FindGraph(BP, Name)) { OutError = TEXT("exists"); return OutError; }
	BP->Modify();
	UEdGraph* Graph = FBlueprintEditorUtils::CreateNewGraph(BP, Name, UEdGraph::StaticClass(), UEdGraphSchema_K2::StaticClass());
	if (!Graph) { OutError = TEXT("CreateNewGraph failed"); return TEXT("ERROR: ") + OutError; }
	FBlueprintEditorUtils::AddFunctionGraph<UClass>(BP, Graph, /*bIsUserCreated=*/ true, nullptr);
	UK2Node_FunctionEntry* Entry = FindEntry(Graph);
	if (!Entry) { OutError = TEXT("no entry node"); return TEXT("ERROR: ") + OutError; }
	if (bPure)
	{
		Entry->AddExtraFlags(FUNC_BlueprintPure);
	}
	if (!Category.IsEmpty())
	{
		Entry->MetaData.Category = FText::FromString(Category);
	}
	for (const FString& In : Inputs)
	{
		FName PName; FEdGraphPinType PType; FString PDefault;
		if (!ParseParam(In, PName, PType, PDefault, OutError)) return TEXT("ERROR: ") + OutError;
		UEdGraphPin* Pin = Entry->CreateUserDefinedPin(PName, PType, EGPD_Output);
		if (!Pin) { OutError = FString::Printf(TEXT("could not add input %s"), *In); return TEXT("ERROR: ") + OutError; }
		if (!PDefault.IsEmpty())
		{
			for (TSharedPtr<FUserPinInfo>& Info : Entry->UserDefinedPins)
			{
				if (Info->PinName == PName) { Entry->ModifyUserDefinedPinDefaultValue(Info, PDefault); }
			}
		}
	}
	if (Outputs.Num() > 0)
	{
		UK2Node_FunctionResult* Result = FBlueprintEditorUtils::FindOrCreateFunctionResultNode(Entry);
		if (!Result) { OutError = TEXT("no result node"); return TEXT("ERROR: ") + OutError; }
		for (const FString& Out : Outputs)
		{
			FName PName; FEdGraphPinType PType; FString PDefault;
			if (!ParseParam(Out, PName, PType, PDefault, OutError)) return TEXT("ERROR: ") + OutError;
			if (!Result->CreateUserDefinedPin(PName, PType, EGPD_Input)) { OutError = FString::Printf(TEXT("could not add output %s"), *Out); return TEXT("ERROR: ") + OutError; }
		}
	}
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
	return OutError;
}

FString UDFBlueprintAuthoringLibrary::AddLocalVariable(UBlueprint* BP, FName FunctionName, FName Name, const FString& TypeSpec, const FString& DefaultValue)
{
	FString OutError;
	UEdGraph* Graph = FindGraph(BP, FunctionName);
	if (!Graph) { return TEXT("ERROR: function graph not found: ") + FunctionName.ToString(); }
	if (FBlueprintEditorUtils::FindLocalVariable(BP, Graph, Name)) { return TEXT("exists"); }
	FEdGraphPinType Type;
	if (!ParseTypeSpec(TypeSpec, Type, OutError)) return TEXT("ERROR: ") + OutError;
	if (!FBlueprintEditorUtils::AddLocalVariable(BP, Graph, Name, Type, DefaultValue)) { return TEXT("ERROR: AddLocalVariable failed"); }
	return FString();
}

FString UDFBlueprintAuthoringLibrary::RemoveFunction(UBlueprint* BP, FName Name)
{
	FString OutError;
	UEdGraph* Graph = FindGraph(BP, Name);
	if (!Graph) { OutError = TEXT("not found"); return TEXT("ERROR: ") + OutError; }
	FBlueprintEditorUtils::RemoveGraph(BP, Graph, EGraphRemoveFlags::Recompile);
	return OutError;
}

FString UDFBlueprintAuthoringLibrary::AddEventDispatcher(UBlueprint* BP, FName Name, const TArray<FString>& Params)
{
	FString OutError;
	if (!BP) { OutError = TEXT("null blueprint"); return TEXT("ERROR: ") + OutError; }
	if (FBlueprintEditorUtils::FindNewVariableIndex(BP, Name) != INDEX_NONE) { OutError = TEXT("exists"); return OutError; }
	const UEdGraphSchema_K2* K2Schema = GetDefault<UEdGraphSchema_K2>();
	BP->Modify();
	FEdGraphPinType DelegateType;
	DelegateType.PinCategory = UEdGraphSchema_K2::PC_MCDelegate;
	if (!FBlueprintEditorUtils::AddMemberVariable(BP, Name, DelegateType)) { OutError = TEXT("AddMemberVariable failed"); return TEXT("ERROR: ") + OutError; }
	UEdGraph* NewGraph = FBlueprintEditorUtils::CreateNewGraph(BP, Name, UEdGraph::StaticClass(), UEdGraphSchema_K2::StaticClass());
	if (!NewGraph)
	{
		FBlueprintEditorUtils::RemoveMemberVariable(BP, Name);
		OutError = TEXT("CreateNewGraph failed");
		return TEXT("ERROR: ") + OutError;
	}
	NewGraph->bEditable = false;
	K2Schema->CreateDefaultNodesForGraph(*NewGraph);
	K2Schema->CreateFunctionGraphTerminators(*NewGraph, (UClass*)nullptr);
	K2Schema->AddExtraFunctionFlags(NewGraph, (FUNC_BlueprintCallable | FUNC_BlueprintEvent | FUNC_Public));
	K2Schema->MarkFunctionEntryAsEditable(NewGraph, true);
	BP->DelegateSignatureGraphs.Add(NewGraph);
	if (UK2Node_FunctionEntry* Entry = FindEntry(NewGraph))
	{
		for (const FString& P : Params)
		{
			FName PName; FEdGraphPinType PType; FString PDefault;
			if (!ParseParam(P, PName, PType, PDefault, OutError)) return TEXT("ERROR: ") + OutError;
			if (!Entry->CreateUserDefinedPin(PName, PType, EGPD_Output)) { OutError = FString::Printf(TEXT("could not add param %s"), *P); return TEXT("ERROR: ") + OutError; }
		}
	}
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
	return OutError;
}

FString UDFBlueprintAuthoringLibrary::AddStructMember(UUserDefinedStruct* Struct, const FString& Name, const FString& TypeSpec, const FString& DefaultValue)
{
	FString OutError;
	if (!Struct) { OutError = TEXT("null struct"); return TEXT("ERROR: ") + OutError; }
	FEdGraphPinType Type;
	if (!ParseTypeSpec(TypeSpec, Type, OutError)) return TEXT("ERROR: ") + OutError;
	bool bExists = false;
	for (const FStructVariableDescription& D : FStructureEditorUtils::GetVarDesc(Struct))
	{
		if (D.FriendlyName == Name) { bExists = true; }
	}
	if (!bExists)
	{
		if (!FStructureEditorUtils::AddVariable(Struct, Type)) { return TEXT("ERROR: AddVariable failed"); }
		const FGuid Guid = FStructureEditorUtils::GetVarDesc(Struct).Last().VarGuid;
		if (!FStructureEditorUtils::RenameVariable(Struct, Guid, Name)) { return TEXT("ERROR: RenameVariable failed"); }
		if (!DefaultValue.IsEmpty())
		{
			FStructureEditorUtils::ChangeVariableDefaultValue(Struct, Guid, DefaultValue);
		}
	}
	// Drop the factory's placeholder member now that a real one exists (the engine refuses to remove a struct's
	// last member, so this cannot happen before the first add).
	{
		TArray<FGuid> Placeholders;
		const TArray<FStructVariableDescription>& Descs = FStructureEditorUtils::GetVarDesc(Struct);
		for (const FStructVariableDescription& D : Descs)
		{
			if (D.FriendlyName.StartsWith(TEXT("MemberVar_")) && D.FriendlyName != Name) { Placeholders.Add(D.VarGuid); }
		}
		for (const FGuid& G : Placeholders)
		{
			if (FStructureEditorUtils::GetVarDesc(Struct).Num() > 1)
			{
				FStructureEditorUtils::RemoveVariable(Struct, G);
			}
		}
	}
	return bExists ? TEXT("exists") : FString();
}

FString UDFBlueprintAuthoringLibrary::DescribeStruct(UUserDefinedStruct* Struct)
{
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	if (!Struct) return ToJson(Root);
	Root->SetStringField(TEXT("name"), Struct->GetName());
	TArray<TSharedPtr<FJsonValue>> Members;
	for (const FStructVariableDescription& D : FStructureEditorUtils::GetVarDesc(Struct))
	{
		TSharedRef<FJsonObject> O = MakeShared<FJsonObject>();
		O->SetStringField(TEXT("display"), D.FriendlyName);
		O->SetStringField(TEXT("name"), D.VarName.ToString());
		O->SetStringField(TEXT("type"), TypeToString(D.ToPinType()));
		O->SetStringField(TEXT("default"), D.DefaultValue);
		Members.Add(MakeShared<FJsonValueObject>(O));
	}
	Root->SetArrayField(TEXT("members"), Members);
	return ToJson(Root);
}

FString UDFBlueprintAuthoringLibrary::AddEnumValue(UUserDefinedEnum* Enum, const FString& DisplayName)
{
	FString OutError;
	if (!Enum) { OutError = TEXT("null enum"); return TEXT("ERROR: ") + OutError; }
	const int32 Count = Enum->NumEnums() - 1; // last is _MAX
	for (int32 i = 0; i < Count; ++i)
	{
		if (Enum->GetDisplayNameTextByIndex(i).ToString() == DisplayName) { OutError = TEXT("exists"); return OutError; }
	}
	int32 Index;
	if (Count == 1 && Enum->GetDisplayNameTextByIndex(0).ToString().StartsWith(TEXT("NewEnumerator")))
	{
		Index = 0; // rename the factory placeholder
	}
	else
	{
		FEnumEditorUtils::AddNewEnumeratorForUserDefinedEnum(Enum);
		Index = Enum->NumEnums() - 2;
	}
	if (!FEnumEditorUtils::SetEnumeratorDisplayName(Enum, Index, FText::FromString(DisplayName)))
	{
		OutError = TEXT("SetEnumeratorDisplayName failed");
		return TEXT("ERROR: ") + OutError;
	}
	return OutError;
}

FString UDFBlueprintAuthoringLibrary::ImportNodes(UBlueprint* BP, FName GraphName, const FString& Text)
{
	FString OutReport;
	UEdGraph* Graph = FindGraph(BP, GraphName);
	if (!Graph) { OutReport = FString::Printf(TEXT("graph not found: %s"), *GraphName.ToString()); return TEXT("ERROR: ") + OutReport; }
	if (!FEdGraphUtilities::CanImportNodesFromText(Graph, Text)) { OutReport = TEXT("text cannot be imported into this graph"); return TEXT("ERROR: ") + OutReport; }
	Graph->Modify();
	TSet<UEdGraphNode*> Imported;
	FEdGraphUtilities::ImportNodesFromText(Graph, Text, Imported);
	// ImportNodesFromText already ran PostPasteNode + ReconstructNode on every node (FEdGraphUtilities::PostProcessPastedNodes).
	for (UEdGraphNode* Node : Imported)
	{
		Node->SetFlags(RF_Transactional);
		Node->CreateNewGuid();
		if (UK2Node_Event* EventNode = Cast<UK2Node_Event>(Node))
		{
			if (EventNode->bOverrideFunction)
			{
				TArray<UK2Node_Event*> Existing;
				FBlueprintEditorUtils::GetAllNodesOfClass<UK2Node_Event>(BP, Existing);
				for (UK2Node_Event* Other : Existing)
				{
					if (Other != EventNode && Other->bOverrideFunction && UK2Node_Event::AreEventNodesIdentical(EventNode, Other) && Other->IsAutomaticallyPlacedGhostNode())
					{
						Other->DestroyNode();
					}
				}
			}
		}
	}
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
	for (UEdGraphNode* Node : Imported)
	{
		Node->ReconstructNode();
	}
	// Reconstruction conforms DeterminesOutputType outputs (GetAllActorsOfClass, SpawnActor, ...) while allocating pins,
	// before the old pins' class/object defaults are copied over, so they fall back to the base class. Replay the
	// "user picked a class" notification for every pin carrying an object default.
	for (UEdGraphNode* Node : Imported)
	{
		TArray<UEdGraphPin*> WithObjectDefault;
		for (UEdGraphPin* Pin : Node->Pins)
		{
			if (Pin && Pin->DefaultObject && Pin->Direction == EGPD_Input)
			{
				WithObjectDefault.Add(Pin);
			}
		}
		for (UEdGraphPin* Pin : WithObjectDefault)
		{
			if (!Pin->IsPendingKill())
			{
				Node->PinDefaultValueChanged(Pin);
			}
		}
	}
	// Imported links never went through the schema, so wildcard/macro/array nodes have not adapted their pin
	// types to what they are connected to. Notify every linked pin the way a user-made connection would.
	for (UEdGraphNode* Node : Imported)
	{
		for (UEdGraphPin* Pin : Node->Pins)
		{
			if (Pin && Pin->LinkedTo.Num() > 0)
			{
				// NotifyPinConnectionListChanged is what the schema calls after TryCreateConnection; macro
				// instances and array functions override it to resolve wildcard pin types and reconstruct.
				if (UK2Node* K2Node = Cast<UK2Node>(Node))
				{
					K2Node->NotifyPinConnectionListChanged(Pin);
				}
				else
				{
					Node->PinConnectionListChanged(Pin);
				}
			}
		}
		// the schema calls this after the per-pin notifications; macro instances reconstruct here
		Node->NodeConnectionListChanged();
	}
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
	OutReport = FString::Printf(TEXT("imported %d nodes into %s"), Imported.Num(), *GraphName.ToString());
	return Imported.Num() > 0 ? OutReport : (TEXT("ERROR: no nodes imported; ") + OutReport);
}

FString UDFBlueprintAuthoringLibrary::ConnectPins(UBlueprint* BP, FName GraphName, const FString& NodeA, const FString& PinA, const FString& NodeB, const FString& PinB)
{
	FString OutError;
	UEdGraph* Graph = FindGraph(BP, GraphName);
	if (!Graph) { OutError = TEXT("graph not found"); return TEXT("ERROR: ") + OutError; }
	UEdGraphNode* A = FindNode(Graph, NodeA);
	UEdGraphNode* B = FindNode(Graph, NodeB);
	if (!A || !B) { OutError = FString::Printf(TEXT("node not found: %s"), !A ? *NodeA : *NodeB); return TEXT("ERROR: ") + OutError; }
	UEdGraphPin* PA = A->FindPin(FName(*PinA));
	UEdGraphPin* PB = B->FindPin(FName(*PinB));
	if (!PA || !PB)
	{
		FString Names;
		for (UEdGraphPin* P : (!PA ? A : B)->Pins) { Names += P->PinName.ToString() + TEXT(" "); }
		OutError = FString::Printf(TEXT("pin not found: %s (pins: %s)"), !PA ? *PinA : *PinB, *Names);
		return TEXT("ERROR: ") + OutError;
	}
	const UEdGraphSchema* Schema = Graph->GetSchema();
	const FPinConnectionResponse Response = Schema->CanCreateConnection(PA, PB);
	if (Response.Response == CONNECT_RESPONSE_DISALLOW)
	{
		OutError = Response.Message.ToString();
		return TEXT("ERROR: ") + OutError;
	}
	if (!Schema->TryCreateConnection(PA, PB)) { OutError = TEXT("TryCreateConnection failed"); return TEXT("ERROR: ") + OutError; }
	return OutError;
}

FString UDFBlueprintAuthoringLibrary::SetPinDefault(UBlueprint* BP, FName GraphName, const FString& NodeId, const FString& PinName, const FString& Value)
{
	FString OutError;
	UEdGraph* Graph = FindGraph(BP, GraphName);
	UEdGraphNode* Node = FindNode(Graph, NodeId);
	if (!Node) { OutError = TEXT("node not found"); return TEXT("ERROR: ") + OutError; }
	UEdGraphPin* Pin = Node->FindPin(FName(*PinName));
	if (!Pin) { OutError = TEXT("pin not found"); return TEXT("ERROR: ") + OutError; }
	Graph->GetSchema()->TrySetDefaultValue(*Pin, Value);
	return OutError;
}

FString UDFBlueprintAuthoringLibrary::ClearGraph(UBlueprint* BP, FName GraphName)
{
	FString OutError;
	UEdGraph* Graph = FindGraph(BP, GraphName);
	if (!Graph) { OutError = TEXT("graph not found"); return TEXT("ERROR: ") + OutError; }
	TArray<UEdGraphNode*> ToRemove;
	for (UEdGraphNode* N : Graph->Nodes)
	{
		if (N && !N->IsA<UK2Node_FunctionEntry>() && !N->IsA<UK2Node_FunctionResult>())
		{
			ToRemove.Add(N);
		}
	}
	for (UEdGraphNode* N : ToRemove)
	{
		FBlueprintEditorUtils::RemoveNode(BP, N, true);
	}
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
	return OutError;
}

FString UDFBlueprintAuthoringLibrary::DescribeBlueprint(UBlueprint* BP)
{
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	if (!BP) return ToJson(Root);
	Root->SetStringField(TEXT("name"), BP->GetName());
	Root->SetStringField(TEXT("parent"), BP->ParentClass ? BP->ParentClass->GetPathName() : TEXT(""));
	TArray<TSharedPtr<FJsonValue>> Vars;
	for (const FBPVariableDescription& V : BP->NewVariables)
	{
		TSharedRef<FJsonObject> O = MakeShared<FJsonObject>();
		O->SetStringField(TEXT("name"), V.VarName.ToString());
		O->SetStringField(TEXT("type"), TypeToString(V.VarType));
		O->SetStringField(TEXT("default"), V.DefaultValue);
		O->SetStringField(TEXT("category"), V.Category.ToString());
		O->SetBoolField(TEXT("instance_editable"), (V.PropertyFlags & CPF_DisableEditOnInstance) == 0);
		Vars.Add(MakeShared<FJsonValueObject>(O));
	}
	Root->SetArrayField(TEXT("variables"), Vars);
	auto GraphNames = [](const TArray<UEdGraph*>& Graphs)
	{
		TArray<TSharedPtr<FJsonValue>> Arr;
		for (UEdGraph* G : Graphs) { if (G) Arr.Add(MakeShared<FJsonValueString>(G->GetName())); }
		return Arr;
	};
	Root->SetArrayField(TEXT("functions"), GraphNames(BP->FunctionGraphs));
	Root->SetArrayField(TEXT("dispatchers"), GraphNames(BP->DelegateSignatureGraphs));
	Root->SetArrayField(TEXT("event_graphs"), GraphNames(BP->UbergraphPages));
	TArray<TSharedPtr<FJsonValue>> Comps;
	if (BP->SimpleConstructionScript)
	{
		for (USCS_Node* N : BP->SimpleConstructionScript->GetAllNodes())
		{
			if (!N) continue;
			TSharedRef<FJsonObject> O = MakeShared<FJsonObject>();
			O->SetStringField(TEXT("name"), N->GetVariableName().ToString());
			O->SetStringField(TEXT("class"), N->ComponentClass ? N->ComponentClass->GetPathName() : TEXT(""));
			Comps.Add(MakeShared<FJsonValueObject>(O));
		}
	}
	Root->SetArrayField(TEXT("components"), Comps);
	return ToJson(Root);
}

FString UDFBlueprintAuthoringLibrary::DescribeGraph(UBlueprint* BP, FName GraphName)
{
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	UEdGraph* Graph = FindGraph(BP, GraphName);
	if (!Graph) { Root->SetStringField(TEXT("error"), TEXT("graph not found")); return ToJson(Root); }
	Root->SetStringField(TEXT("graph"), Graph->GetName());
	TArray<TSharedPtr<FJsonValue>> Nodes;
	for (UEdGraphNode* N : Graph->Nodes)
	{
		if (!N) continue;
		TSharedRef<FJsonObject> O = MakeShared<FJsonObject>();
		O->SetStringField(TEXT("name"), N->GetName());
		O->SetStringField(TEXT("class"), N->GetClass()->GetName());
		O->SetStringField(TEXT("title"), N->GetNodeTitle(ENodeTitleType::ListView).ToString());
		O->SetNumberField(TEXT("x"), N->NodePosX);
		O->SetNumberField(TEXT("y"), N->NodePosY);
		if (N->bHasCompilerMessage) { O->SetStringField(TEXT("error"), N->ErrorMsg); }
		TArray<TSharedPtr<FJsonValue>> Pins;
		for (UEdGraphPin* P : N->Pins)
		{
			if (!P) continue;
			TSharedRef<FJsonObject> PO = MakeShared<FJsonObject>();
			PO->SetStringField(TEXT("name"), P->PinName.ToString());
			if (P->bHidden) PO->SetBoolField(TEXT("hidden"), true);
			// a pin the text named but the real signature does not have survives reconstruction only as an orphan
			if (P->bOrphanedPin) PO->SetBoolField(TEXT("orphaned"), true);
			PO->SetStringField(TEXT("dir"), P->Direction == EGPD_Input ? TEXT("in") : TEXT("out"));
			PO->SetStringField(TEXT("type"), TypeToString(P->PinType));
			if (!P->DefaultValue.IsEmpty()) PO->SetStringField(TEXT("default"), P->DefaultValue);
			if (P->DefaultObject) PO->SetStringField(TEXT("default_object"), P->DefaultObject->GetPathName());
			TArray<TSharedPtr<FJsonValue>> Links;
			for (UEdGraphPin* L : P->LinkedTo)
			{
				if (L && L->GetOwningNode()) Links.Add(MakeShared<FJsonValueString>(L->GetOwningNode()->GetName() + TEXT(".") + L->PinName.ToString()));
			}
			if (Links.Num()) PO->SetArrayField(TEXT("links"), Links);
			Pins.Add(MakeShared<FJsonValueObject>(PO));
		}
		O->SetArrayField(TEXT("pins"), Pins);
		Nodes.Add(MakeShared<FJsonValueObject>(O));
	}
	Root->SetArrayField(TEXT("nodes"), Nodes);
	return ToJson(Root);
}

FString UDFBlueprintAuthoringLibrary::AddComponent(UBlueprint* BP, FName Name, const FString& ClassPath, FName ParentComponent)
{
	FString OutError;
	if (!BP) { OutError = TEXT("null blueprint"); return TEXT("ERROR: ") + OutError; }
	USimpleConstructionScript* SCS = BP->SimpleConstructionScript;
	if (!SCS) { OutError = TEXT("blueprint has no construction script (not an actor?)"); return TEXT("ERROR: ") + OutError; }
	if (SCS->FindSCSNode(Name)) { OutError = TEXT("exists"); return OutError; }
	UClass* Class = LoadByPath<UClass>(ClassPath);
	if (!Class || !Class->IsChildOf(UActorComponent::StaticClass())) { OutError = FString::Printf(TEXT("component class not found: %s"), *ClassPath); return TEXT("ERROR: ") + OutError; }
	BP->Modify();
	USCS_Node* Node = SCS->CreateNode(Class, Name);
	if (!Node) { OutError = TEXT("CreateNode failed"); return TEXT("ERROR: ") + OutError; }
	USCS_Node* Parent = ParentComponent.IsNone() ? nullptr : SCS->FindSCSNode(ParentComponent);
	if (Parent)
	{
		Parent->AddChildNode(Node);
	}
	else
	{
		SCS->AddNode(Node);
	}
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
	return OutError;
}

UActorComponent* UDFBlueprintAuthoringLibrary::GetComponentTemplate(UBlueprint* BP, FName Name)
{
	if (!BP || !BP->SimpleConstructionScript) return nullptr;
	USCS_Node* Node = BP->SimpleConstructionScript->FindSCSNode(Name);
	return Node ? Node->ComponentTemplate : nullptr;
}

UWidget* UDFBlueprintAuthoringLibrary::ResetWidgetTree(UBlueprint* BP, const FString& RootClassPath, FName RootName)
{
	UWidgetBlueprint* WBP = Cast<UWidgetBlueprint>(BP);
	UClass* RootClass = LoadByPath<UClass>(RootClassPath);
	if (!WBP || !WBP->WidgetTree || !RootClass || !RootClass->IsChildOf(UPanelWidget::StaticClass()))
	{
		return nullptr;
	}
	WBP->Modify();
	WBP->WidgetTree->Modify();
	TArray<UWidget*> Existing;
	WBP->WidgetTree->GetAllWidgets(Existing);
	for (UWidget* W : Existing)
	{
		// move old widgets out of the tree's outer so their names can be reused
		W->Rename(*MakeUniqueObjectName(GetTransientPackage(), W->GetClass()).ToString(), GetTransientPackage(),
			REN_DontCreateRedirectors | REN_NonTransactional | REN_ForceNoResetLoaders);
	}
	WBP->WidgetTree->RootWidget = nullptr;
	UWidget* Root = WBP->WidgetTree->ConstructWidget<UWidget>(RootClass, RootName);
	WBP->WidgetTree->RootWidget = Root;
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WBP);
	return Root;
}

UWidget* UDFBlueprintAuthoringLibrary::AddWidget(UBlueprint* BP, FName Name, const FString& ClassPath, FName ParentName)
{
	UWidgetBlueprint* WBP = Cast<UWidgetBlueprint>(BP);
	UClass* WidgetClass = LoadByPath<UClass>(ClassPath);
	if (!WBP || !WBP->WidgetTree || !WidgetClass || !WidgetClass->IsChildOf(UWidget::StaticClass()))
	{
		return nullptr;
	}
	if (UWidget* Found = WBP->WidgetTree->FindWidget(Name))
	{
		return Found;
	}
	UPanelWidget* Parent = Cast<UPanelWidget>(ParentName.IsNone() ? WBP->WidgetTree->RootWidget : WBP->WidgetTree->FindWidget(ParentName));
	if (!Parent)
	{
		return nullptr;
	}
	WBP->WidgetTree->Modify();
	UWidget* W = WBP->WidgetTree->ConstructWidget<UWidget>(WidgetClass, Name);
	W->bIsVariable = true;
	Parent->AddChild(W);
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WBP);
	return W;
}

FString UDFBlueprintAuthoringLibrary::SetNodePosition(UBlueprint* BP, FName GraphName, const FString& NodeId, int32 X, int32 Y)
{
	UEdGraph* Graph = FindGraph(BP, GraphName);
	if (!Graph) { return TEXT("ERROR: graph not found: ") + GraphName.ToString(); }
	UEdGraphNode* Node = FindNode(Graph, NodeId);
	if (!Node) { return TEXT("ERROR: node not found: ") + NodeId; }
	Node->Modify();
	Node->NodePosX = X;
	Node->NodePosY = Y;
	return FString();
}

FString UDFBlueprintAuthoringLibrary::SetFunctionDescription(UBlueprint* BP, FName FunctionName, const FString& Description)
{
	UEdGraph* Graph = FindGraph(BP, FunctionName);
	if (!Graph) { return TEXT("ERROR: function graph not found: ") + FunctionName.ToString(); }
	UK2Node_FunctionEntry* Entry = FindEntry(Graph);
	if (!Entry) { return TEXT("ERROR: no entry node"); }
	Entry->Modify();
	Entry->MetaData.ToolTip = FText::FromString(Description);
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
	return FString();
}

FString UDFBlueprintAuthoringLibrary::FocusGraph(UBlueprint* BP, FName GraphName)
{
	UEdGraph* Graph = FindGraph(BP, GraphName);
	if (!Graph) { return TEXT("ERROR: graph not found: ") + GraphName.ToString(); }
	FKismetEditorUtilities::BringKismetToFocusAttentionOnObject(Graph);
	return FString();
}

FString UDFBlueprintAuthoringLibrary::Compile(UBlueprint* BP)
{
	FString OutMessages;
	if (!BP) { OutMessages = TEXT("null blueprint"); return TEXT("ERROR: ") + OutMessages; }
	FCompilerResultsLog Results;
	Results.bSilentMode = true;
	FKismetEditorUtilities::CompileBlueprint(BP, EBlueprintCompileOptions::None, &Results);
	OutMessages.Empty();
	for (const TSharedRef<FTokenizedMessage>& M : Results.Messages)
	{
		const EMessageSeverity::Type Sev = M->GetSeverity();
		if (Sev == EMessageSeverity::Error || Sev == EMessageSeverity::CriticalError)
		{
			OutMessages += FString::Printf(TEXT("[ERROR] %s\n"), *M->ToText().ToString());
		}
		else if (Sev == EMessageSeverity::Warning || Sev == EMessageSeverity::PerformanceWarning)
		{
			OutMessages += FString::Printf(TEXT("[WARN] %s\n"), *M->ToText().ToString());
		}
	}
	return FString::Printf(TEXT("errors=%d warnings=%d\n"), Results.NumErrors, Results.NumWarnings) + OutMessages;
}
