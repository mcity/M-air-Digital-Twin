// MAirCorridorEditorModule.h - "Tools > M-Air Corridor" : the two importers that build this scene.
//
// WHAT THIS MODULE IS FOR. The corridor reaches Unreal as three things, and two of them need an
// edit-time step that stock Unreal does not offer:
//
//   * THE LANDSCAPE. A USGS 3DEP DSM is far too large for the Landscape mode dialog - the source
//     raster for this corridor is in the gigabytes, past the point where Unreal's own import will
//     take it - so the heightmap is prepared outside the editor as a raw .r16 plus a sidecar of
//     the eleven numbers an import needs, and read back here. See MAirLandscapeImporter.h.
//   * THE TREES AND ROCKS. A generated library of FBX plus a surveyed set of positions, placed as
//     instances and traced onto the Landscape. See MAirFoliagePlacer.cpp.
//   * THE SCAN, which needs nothing from this module: AMAirScanActor streams the M-City
//     photogrammetric tiles at runtime, straight out of this plugin's own Content/Scans.
//
// THIS MODULE DEPENDS ON NOTHING BUT THE ENGINE. Every include below it is an engine header.
// The inputs both importers read are produced by the scripts in Tools/ - see Tools/README.md.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleInterface.h"

class FMAirCorridorEditorModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;

private:
    void RegisterMenus();

    /** Read a plan written by unreal_landscape.py and build the Landscape(s) it describes, so no
     *  import number is ever retyped by hand. */
    void ImportLandscapePlan();

    /** Import the generated tree and rock library and place it: the SURVEYED trees exactly where
     *  the OSM data records them, and a scatter inside the wood, scrub, park and grass polygons at
     *  per-layer densities. Every instance is traced onto the Landscape - the survey carries no
     *  height that means anything here. */
    void PlaceCorridorFoliage();

    /** Set the imagery material's UVScale and UVOrigin from the imagery index, which is the only
     *  place the correct numbers exist and far too precise to type into a details field. */
    void FixImageryScale();

    /** Put the editor camera on the M-City scan. It is 1.6 km across in a 65 km world, which is
     *  easy to fly past without ever seeing it. */
    void GoToScan();

    TArray<FName> RegisteredMenus;
};
