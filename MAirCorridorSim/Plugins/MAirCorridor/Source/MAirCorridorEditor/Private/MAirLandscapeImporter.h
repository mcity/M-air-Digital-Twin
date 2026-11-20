// MAirLandscapeImporter - a heightmap too large for Unreal's own import becomes an ALandscape.
//
// WHY THIS EXISTS RATHER THAN THE LANDSCAPE MODE DIALOG. Unreal's import path wants to read the
// source raster itself, and a corridor-scale DSM is far past the size where that is possible - the
// file is in the gigabytes before it is a heightmap at all. So the resampling, the reprojection and
// the vertical range are all settled OUTSIDE the editor, and what arrives here is the finished
// article: a raw 16-bit heightmap and a small JSON beside it carrying the numbers an import needs.
// This reads that pair. Unreal never sees the oversized source.
//
// WHY NOT RETYPE THE NUMBERS BY HAND, which is the documented procedure. There are eleven of them -
// resolution, section size, sections per component, component counts, XY and Z scale, the actor's Z
// placement, the World Partition grid - and a single transposed digit produces terrain that is
// subtly the wrong size or the wrong height, with nothing in the level to compare it against. The
// numbers are already correct in a file; this reads them instead of asking someone to copy them.
//
// WHY C++ AND NOT AN EDITOR PYTHON SCRIPT. Unreal 5.7 exposes NO scriptable landscape import:
// Engine/Source/Editor/LandscapeEditor contains zero UFUNCTION declarations, so there is nothing for
// the editor's Python layer to call. The real entry points are ALandscapeProxy::Import
// (LandscapeProxy.h) and ULandscapeSubsystem::ChangeGridSize (LandscapeSubsystem.h), both editor-side
// C++. That is a fact about the engine, not a preference.
//
// THE SEQUENCE IS UNREAL'S OWN, followed deliberately rather than reconstructed: it mirrors
// LandscapeEditorDetailCustomization_NewLandscape.cpp - spawn ALandscape, set material and relative
// scale, set StaticLightingLOD from the vertex count, Import, then UpdateLayerInfoMap, then
// ChangeGridSize for World Partition. Doing it in a different order produces a landscape that looks
// right and has no LandscapeInfo, which fails later and somewhere else.
//
// THE SIDECAR, so this file stands on its own and the plan can be written by anything:
//
//     {
//       "name": "CorridorTerrain",
//       "heightmap_r16": "corridor.r16",     // beside the JSON; uint16, row-major, X fastest
//       "resolution": [8129, 4033],          // MUST equal quads*components + 1, both axes
//       "section_size_quads": 127,           // one of 7 / 15 / 31 / 63 / 127 / 255
//       "sections_per_component": 2,         // 1 or 2
//       "components": [32, 16],
//       "actor_scale": [100.0, 100.0, 100.0],
//       "actor_location_cm": [0.0, 0.0, 0.0],
//       "world_partition_grid_size": 4,      // 0 to leave the landscape unsplit
//       "quad_metres": 1.0,                  // reporting only
//       "elev_min_m": 95.1, "elev_max_m": 133.5, "elev_mid_m": 114.3,
//       "cells_1m": 0, "cells_19_resampled": 0, "cells_nodata": 0,   // provenance, reported back
//       "height_decode": "z_m = 95.1 + h/65535 * 38.4",
//       "segments": [ ... ]                  // optional: a ribbon, each entry its own landscape
//     }

#pragma once

#include "CoreMinimal.h"

class UWorld;
class ALandscape;

namespace MAirLandscapeImporter
{
    /** Everything the preparing tool computed, as read back from its sidecar. */
    struct FPlan
    {
        FString Name;
        FString HeightmapPath;        // absolute path to the .r16
        FString ProvenancePath;       // absolute path to the .provenance, may be empty
        FIntPoint Resolution = FIntPoint::ZeroValue;
        int32 SectionSizeQuads = 0;
        int32 SectionsPerComponent = 0;
        FIntPoint Components = FIntPoint::ZeroValue;
        int32 WorldPartitionGridSize = 4;
        FVector ActorScale = FVector(100.0, 100.0, 100.0);
        FVector ActorLocationCm = FVector::ZeroVector;
        double QuadMetres = 1.0;
        double ElevMinM = 0.0;
        double ElevMaxM = 0.0;
        double ElevMidM = 0.0;
        int64 Cells1m = 0;
        int64 Cells19Resampled = 0;
        int64 CellsNodata = 0;
        FString HeightDecode;
        FString Source;

        /** Segments, when the sidecar describes a ribbon rather than a single landscape. */
        TArray<FPlan> Segments;
    };

    /** Parse a sidecar. Returns false and fills OutError on any inconsistency - a plan that does not
     *  describe a legal landscape is refused here rather than half-built in the level. */
    bool LoadPlan(const FString& JsonPath, FPlan& Out, FString& OutError);

    /** Build one landscape from a plan. Returns the actor, or nullptr with OutError set. */
    ALandscape* ImportOne(UWorld* World, const FPlan& Plan, FString& OutError);

    /** Build every landscape a plan describes - one, or every segment of a ribbon. */
    int32 ImportPlan(UWorld* World, const FPlan& Plan, TArray<ALandscape*>& OutActors,
                     FString& OutError);
}
