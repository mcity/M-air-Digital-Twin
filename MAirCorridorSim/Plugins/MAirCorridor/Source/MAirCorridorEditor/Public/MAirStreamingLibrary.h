// MAirStreamingLibrary.h - the level's World Partition streaming setup, reachable from Python.
//
// WHY THIS EXISTS. How far out each kind of actor loads, and what stands in for it beyond that
// (its HLOD), is set by the runtime partitions of the level's runtime hash. In UE 5.7 none of
// those classes (UWorldPartitionRuntimeHashSet, URuntimePartition, URuntimePartitionLHGrid) is
// exposed to Python or Blueprint, and the partition list is a private property, so the only way
// to change them from a script is through reflection, here. Tools/unreal/corridor_streaming.py
// calls these two functions.
//
// WHAT WENT WRONG WITHOUT IT. Splitting the 100 merged building tiles into 73,403 buildings moved
// every building from a 2 to 4 km cell, which loads from kilometres away, into the smallest cells,
// which load only near the camera; and no actor in the level had an HLOD layer, so nothing stood
// in for a building past that. Buildings blinked in and out as the drone flew.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "MAirStreamingLibrary.generated.h"

class UHLODLayer;
class UWorld;

UCLASS()
class MAIRCORRIDOREDITOR_API UMAirStreamingLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /** The world's runtime partitions as text: each one's grid, cell size and loading range, and
     *  each HLOD setup's layers, cell size and loading range. Changes nothing. */
    UFUNCTION(BlueprintCallable, Category = "MAirCorridor|Streaming")
    static FString DescribeStreaming(UWorld* World);

    /** Create the runtime partition PartitionName (a grid) if the world has none of that name, and
     *  set its cell size and loading range in centimetres (0 keeps what is there). With an HLOD
     *  layer, make sure one of its HLOD setups holds that layer, with the HLOD cell size and
     *  loading range given. Actors join a partition through their Runtime Grid property; an actor
     *  with none is in the first partition. Marks the level dirty; saving is the caller's. */
    UFUNCTION(BlueprintCallable, Category = "MAirCorridor|Streaming")
    static bool SetRuntimePartition(UWorld* World, FName PartitionName, int32 CellSize, int32 LoadingRange,
                                    UHLODLayer* HLODLayer, int32 HLODCellSize, int32 HLODLoadingRange,
                                    FString& OutReport);
};
