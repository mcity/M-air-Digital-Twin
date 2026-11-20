// MAirCorridorEditor.Build.cs - the two edit-time importers, and the streaming setup scripts call
// (UMAirStreamingLibrary: World Partition's runtime partitions are not reachable from Python).
//
// STOCK UNREAL ONLY. No other plugin and no terrain streaming: every name below is an engine
// module, so this plugin builds and runs on its own.
//
// WHY A SEPARATE MODULE FROM MAirCorridorScan rather than more files in it. Everything in here is
// editor-only - file dialogs, asset import, ToolMenus - and MAirCorridorScan is Runtime. Folding
// these in would drag UnrealEd and Slate into a packaged game that cannot call any of it.
// "Type": "Editor" in the .uplugin is what keeps that honest, rather than a scattering of
// #if WITH_EDITOR.

using UnrealBuildTool;

public class MAirCorridorEditor : ModuleRules
{
    public MAirCorridorEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core", "CoreUObject", "Engine",
        });

        PrivateDependencyModuleNames.AddRange(new string[]
        {
            "Slate", "SlateCore",
            "UnrealEd",          // GEditor, the FBX import factories, FActorLabelUtilities
            "ToolMenus",         // the Tools menu
            "DesktopPlatform",   // the file and folder pickers
            "AssetTools",        // ImportAssetTasks - the tree and rock library arrives this way
            "AssetRegistry",
            "Projects",          // IPluginManager - where this plugin's own Content lives
            "Json",              // every input this module reads is a sidecar written by a tool
            "Landscape",         // ALandscapeProxy::Import and ULandscapeSubsystem::ChangeGridSize
                                 // are the ONLY way in - UE 5.7 declares no UFUNCTION anywhere in
                                 // Editor/LandscapeEditor, so this cannot be done from Python.
            "LandscapeEditor",   // FLandscapeImportLayerInfo and the import enums
        });
    }
}
