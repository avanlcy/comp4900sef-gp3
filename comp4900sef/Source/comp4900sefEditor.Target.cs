// Dead Fire - COMP 4900SEF Group 3

using UnrealBuildTool;
using System.Collections.Generic;

public class comp4900sefEditorTarget : TargetRules
{
	public comp4900sefEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V2;
		ExtraModuleNames.Add("comp4900sef");
	}
}
