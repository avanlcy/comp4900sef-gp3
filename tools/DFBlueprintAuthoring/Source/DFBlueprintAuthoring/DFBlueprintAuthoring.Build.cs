using UnrealBuildTool;

public class DFBlueprintAuthoring : ModuleRules
{
	public DFBlueprintAuthoring(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine" });

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"UnrealEd",
			"BlueprintGraph",
			"KismetCompiler",
			"Kismet",
			"Json",
			"UMG",
			"UMGEditor",
		});
	}
}
