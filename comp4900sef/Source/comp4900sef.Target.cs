// Dead Fire - COMP 4900SEF Group 3

using UnrealBuildTool;
using System.Collections.Generic;

public class comp4900sefTarget : TargetRules
{
	public comp4900sefTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V2;
		ExtraModuleNames.Add("comp4900sef");
	}
}
