// MAirCorridorScan.Build.cs - the scan loader, and nothing else.
//
// Stock Unreal only: no other plugin, no terrain. It streams the M-City photogrammetric scan tiles (index.json +
// .ancm blobs + their source textures) produced by the scan pipeline.

using System.IO;
using UnrealBuildTool;

public class MAirCorridorScan : ModuleRules
{
    public MAirCorridorScan(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core", "CoreUObject", "Engine",
            "ProceduralMeshComponent",   // the tiles are drawn as procedural mesh sections
        });

        PrivateDependencyModuleNames.AddRange(new string[]
        {
            "Json",        // index.json
            "Projects",    // IPluginManager, to find this plugin's Content folder
            "ImageCore",   // decode + downscale the 8192-square scan textures
        });

        // The tile blobs and textures are not .uasset files, so a packaged build only carries them if they are
        // named here. This covers a copy placed under this plugin's Content/Scans.
        string ScanDir = Path.Combine(PluginDirectory, "Content", "Scans");
        if (Directory.Exists(ScanDir))
        {
            RuntimeDependencies.Add(Path.Combine(ScanDir, "..."), StagedFileType.NonUFS);
        }
    }
}
