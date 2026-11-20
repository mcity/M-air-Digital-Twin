/*
 * MAirStreamingLibrary.cpp - read and set the level's runtime partitions. See the header for why.
 *
 * Everything is done the way the World Settings details panel does it: the partition list is
 * edited in place, a new partition gets a fresh URuntimePartitionLHGrid with the engine's own
 * defaults, and a new HLOD setup gets its grid from URuntimePartition::CreateHLODRuntimePartition,
 * the call the engine itself uses. Only the values asked for are changed.
 */

#include "MAirStreamingLibrary.h"

#include "Engine/World.h"
#include "WorldPartition/HLOD/HLODLayer.h"
#include "WorldPartition/RuntimeHashSet/RuntimePartition.h"
#include "WorldPartition/RuntimeHashSet/RuntimePartitionLHGrid.h"
#include "WorldPartition/RuntimeHashSet/WorldPartitionRuntimeHashSet.h"
#include "WorldPartition/WorldPartition.h"
#include "WorldPartition/WorldPartitionRuntimeHash.h"

namespace
{
    UWorldPartitionRuntimeHashSet* HashSetOf(UWorld* World, FString& OutReport)
    {
        UWorldPartition* WorldPartition = World ? World->GetWorldPartition() : nullptr;
        if (!WorldPartition)
        {
            OutReport += TEXT("The world is not partitioned.\n");
            return nullptr;
        }
        // UWorldPartition::RuntimeHash is protected; its property is not.
        const FObjectProperty* Property = FindFProperty<FObjectProperty>(UWorldPartition::StaticClass(), TEXT("RuntimeHash"));
        UObject* Hash = Property ? Property->GetObjectPropertyValue_InContainer(WorldPartition) : nullptr;
        UWorldPartitionRuntimeHashSet* HashSet = Cast<UWorldPartitionRuntimeHashSet>(Hash);
        if (!HashSet)
        {
            OutReport += FString::Printf(TEXT("The runtime hash is %s, not a runtime hash set.\n"),
                                         Hash ? *Hash->GetClass()->GetName() : TEXT("missing"));
        }
        return HashSet;
    }

    TArray<FRuntimePartitionDesc>* PartitionsOf(UWorldPartitionRuntimeHashSet* HashSet)
    {
        // RuntimePartitions is private; the details panel edits it through this same property.
        const FArrayProperty* Property = FindFProperty<FArrayProperty>(UWorldPartitionRuntimeHashSet::StaticClass(), TEXT("RuntimePartitions"));
        return Property ? Property->ContainerPtrToValuePtr<TArray<FRuntimePartitionDesc>>(HashSet) : nullptr;
    }

    void SetCellSize(URuntimePartition* Partition, int32 CellSize)
    {
        // URuntimePartitionLHGrid::CellSize is private.
        if (const FNumericProperty* Property = CastField<FNumericProperty>(Partition->GetClass()->FindPropertyByName(TEXT("CellSize"))))
        {
            Property->SetIntPropertyValue(Property->ContainerPtrToValuePtr<void>(Partition), static_cast<uint64>(CellSize));
        }
    }

    FString Describe(const URuntimePartition* Partition)
    {
        if (!Partition)
        {
            return TEXT("no grid");
        }
        const URuntimePartitionLHGrid* Grid = Cast<URuntimePartitionLHGrid>(Partition);
        return FString::Printf(TEXT("%s, cell %s, loading range %d cm, block on slow streaming %s, HLOD index %d"),
                               *Partition->GetClass()->GetName(),
                               Grid ? *FString::Printf(TEXT("%u cm"), Grid->GetCellSize()) : TEXT("n/a"),
                               Partition->LoadingRange, Partition->bBlockOnSlowStreaming ? TEXT("yes") : TEXT("no"),
                               Partition->HLODIndex);
    }
}

FString UMAirStreamingLibrary::DescribeStreaming(UWorld* World)
{
    FString Out;
    UWorldPartitionRuntimeHashSet* HashSet = HashSetOf(World, Out);
    TArray<FRuntimePartitionDesc>* Partitions = HashSet ? PartitionsOf(HashSet) : nullptr;
    if (!Partitions)
    {
        return Out;
    }
    const UHLODLayer* DefaultLayer = World->GetWorldPartition()->GetDefaultHLODLayer();
    Out += FString::Printf(TEXT("%d runtime partitions; default HLOD layer %s\n"), Partitions->Num(),
                           DefaultLayer ? *DefaultLayer->GetPathName() : TEXT("none"));
    for (const FRuntimePartitionDesc& Desc : *Partitions)
    {
        Out += FString::Printf(TEXT("partition %s: %s; %d HLOD setups\n"), *Desc.Name.ToString(),
                               *Describe(Desc.MainLayer), Desc.HLODSetups.Num());
        for (const FRuntimePartitionHLODSetup& Setup : Desc.HLODSetups)
        {
            FString Layers;
#if WITH_EDITORONLY_DATA
            for (const UHLODLayer* Layer : Setup.HLODLayers)
            {
                Layers += (Layers.IsEmpty() ? TEXT("") : TEXT(", ")) + (Layer ? Layer->GetName() : FString(TEXT("none")));
            }
#endif
            Out += FString::Printf(TEXT("    HLOD setup %s (layers: %s; spatially loaded %s): %s\n"), *Setup.Name.ToString(),
                                   Layers.IsEmpty() ? TEXT("none") : *Layers, Setup.bIsSpatiallyLoaded ? TEXT("yes") : TEXT("no"),
                                   *Describe(Setup.PartitionLayer));
        }
    }
    return Out;
}

bool UMAirStreamingLibrary::SetRuntimePartition(UWorld* World, FName PartitionName, int32 CellSize, int32 LoadingRange,
                                                UHLODLayer* HLODLayer, int32 HLODCellSize, int32 HLODLoadingRange,
                                                FString& OutReport)
{
    UWorldPartitionRuntimeHashSet* HashSet = HashSetOf(World, OutReport);
    TArray<FRuntimePartitionDesc>* Partitions = HashSet ? PartitionsOf(HashSet) : nullptr;
    if (!Partitions || PartitionName.IsNone())
    {
        return false;
    }
    HashSet->Modify();

    FRuntimePartitionDesc* Desc = Partitions->FindByPredicate([PartitionName](const FRuntimePartitionDesc& D) { return D.Name == PartitionName; });
    if (!Desc)
    {
        // As UWorldPartitionRuntimeHashSet::SetDefaultValues makes the first one.
        Desc = &Partitions->AddDefaulted_GetRef();
        Desc->Name = PartitionName;
        PRAGMA_DISABLE_DEPRECATION_WARNINGS
        Desc->Class = URuntimePartitionLHGrid::StaticClass();
        PRAGMA_ENABLE_DEPRECATION_WARNINGS
        URuntimePartitionLHGrid* Grid = NewObject<URuntimePartitionLHGrid>(HashSet, NAME_None, RF_Transactional);
        Grid->Name = PartitionName;
        Grid->SetDefaultValues();
        Desc->MainLayer = Grid;
        OutReport += FString::Printf(TEXT("created partition %s\n"), *PartitionName.ToString());
    }
    URuntimePartition* Main = Desc->MainLayer;
    if (!Main)
    {
        OutReport += FString::Printf(TEXT("partition %s has no grid\n"), *PartitionName.ToString());
        return false;
    }
    Main->Modify();
    if (CellSize > 0)
    {
        SetCellSize(Main, CellSize);
    }
    if (LoadingRange > 0)
    {
        Main->LoadingRange = LoadingRange;
    }

    if (HLODLayer)
    {
        FRuntimePartitionHLODSetup* Setup = nullptr;
#if WITH_EDITORONLY_DATA
        Setup = Desc->HLODSetups.FindByPredicate([HLODLayer](const FRuntimePartitionHLODSetup& S) { return S.HLODLayers.Contains(HLODLayer); });
#endif
        if (!Setup)
        {
            // Spatially loaded HLOD setups come first, one per HLOD level, and the engine keeps its
            // "Non-Spatially Loaded HLODs" setup (a persistent partition) last; a setup's index is
            // its HLOD level, so a new one goes in after the grids and before that.
            int32 Index = 0;
            while (Index < Desc->HLODSetups.Num() && Desc->HLODSetups[Index].PartitionLayer &&
                   Desc->HLODSetups[Index].PartitionLayer->IsA<URuntimePartitionLHGrid>())
            {
                ++Index;
            }
            Desc->HLODSetups.Insert(FRuntimePartitionHLODSetup(), Index);
            Setup = &Desc->HLODSetups[Index];
            Setup->Name = HLODLayer->GetFName();
#if WITH_EDITORONLY_DATA
            Setup->HLODLayers = { HLODLayer };
#endif
            Setup->PartitionLayer = Main->CreateHLODRuntimePartition(Index);
            Setup->PartitionLayer->Name = Setup->Name;
            OutReport += FString::Printf(TEXT("added HLOD setup %s to %s\n"), *Setup->Name.ToString(), *PartitionName.ToString());
        }
#if WITH_EDITORONLY_DATA
        Setup->RowDisplayName = Setup->Name;
#endif
        Setup->bIsSpatiallyLoaded = true;
        URuntimePartition* HLODGrid = Setup->PartitionLayer;
        HLODGrid->Modify();
        if (HLODCellSize > 0)
        {
            SetCellSize(HLODGrid, HLODCellSize);
        }
        if (HLODLoadingRange > 0)
        {
            HLODGrid->LoadingRange = HLODLoadingRange;
        }
        // As the engine sets an HLOD grid up: never hold the game waiting on a stand-in.
        HLODGrid->bBlockOnSlowStreaming = false;
        HLODGrid->bClientOnlyVisible = true;
    }

    HashSet->MarkPackageDirty();
    OutReport += DescribeStreaming(World);
    return true;
}
