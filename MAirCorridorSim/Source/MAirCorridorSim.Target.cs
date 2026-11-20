using UnrealBuildTool;

public class MAirCorridorSimTarget : TargetRules
{
	public MAirCorridorSimTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V6;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_7;
		ExtraModuleNames.Add("MAirCorridorSim");
	}
}
