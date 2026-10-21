// Dead Fire - COMP 4900SEF Group 3

using UnrealBuildTool;

public class comp4900sef : ModuleRules
{
	public comp4900sef(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		// File-local helpers live in anonymous namespaces, which would collide once the module reaches the unity-build threshold.
		bUseUnity = false;

		// Sources are grouped in subfolders (Vehicle/, Character/, ...); include them from the module root.
		PublicIncludePaths.Add(ModuleDirectory);

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"PhysXVehicles",
			"UMG",
			"Slate",
			"SlateCore",
			"AIModule",
			"NavigationSystem"
		});

		// Editor-only dependency so the automation tests can reach the editor world.
		if (Target.bBuildEditor)
		{
			PrivateDependencyModuleNames.Add("UnrealEd");
		}
	}
}
