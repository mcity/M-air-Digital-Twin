using UnrealBuildTool;

// An empty game module. It exists so that UnrealBuildTool has a target to build the plugins with:
// MAirCorridor and Project AirSim are C++ plugins and ship as source.
public class MAirCorridorSim : ModuleRules
{
	public MAirCorridorSim(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore" });
	}
}
