using UnrealBuildTool;

public class MAirCorridorTraffic : ModuleRules
{
    public MAirCorridorTraffic(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core", "CoreUObject", "Engine",
        });

        PrivateDependencyModuleNames.AddRange(new string[]
        {
            "Json",   // the traffic snapshot that Tools/adsb.py writes
        });
    }
}
