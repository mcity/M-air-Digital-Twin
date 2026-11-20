using UnrealBuildTool;

public class MAirCorridorSimEditorTarget : TargetRules
{
	public MAirCorridorSimEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V6;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_7;
		ExtraModuleNames.Add("MAirCorridorSim");
	}
}
