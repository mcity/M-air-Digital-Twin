#include "MAirLandscapeImporter.h"

#include "Landscape.h"
#include "LandscapeInfo.h"
#include "LandscapeProxy.h"
#include "LandscapeSubsystem.h"

#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Editor/EditorEngine.h"   // FActorLabelUtilities lives here in 5.7, not in Utils/

namespace
{
    /** Absolute path for a sidecar-relative filename, so the JSON stays portable. */
    FString Beside(const FString& JsonPath, const FString& Leaf)
    {
        return Leaf.IsEmpty() ? FString() : FPaths::Combine(FPaths::GetPath(JsonPath), Leaf);
    }

    double Num(const TSharedPtr<FJsonObject>& O, const TCHAR* Key, double Default = 0.0)
    {
        double V = Default;
        return O->TryGetNumberField(Key, V) ? V : Default;
    }

    FVector Vec3(const TSharedPtr<FJsonObject>& O, const TCHAR* Key, const FVector& Default)
    {
        const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
        if (!O->TryGetArrayField(Key, Arr) || !Arr || Arr->Num() < 3)
        {
            return Default;
        }
        return FVector((*Arr)[0]->AsNumber(), (*Arr)[1]->AsNumber(), (*Arr)[2]->AsNumber());
    }

    FIntPoint Int2(const TSharedPtr<FJsonObject>& O, const TCHAR* Key)
    {
        const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
        if (!O->TryGetArrayField(Key, Arr) || !Arr || Arr->Num() < 2)
        {
            return FIntPoint::ZeroValue;
        }
        return FIntPoint(static_cast<int32>((*Arr)[0]->AsNumber()),
                         static_cast<int32>((*Arr)[1]->AsNumber()));
    }

    void ReadCommon(const TSharedPtr<FJsonObject>& O, const FString& JsonPath,
                    MAirLandscapeImporter::FPlan& P)
    {
        O->TryGetStringField(TEXT("name"), P.Name);
        FString Leaf;
        if (O->TryGetStringField(TEXT("heightmap_r16"), Leaf))
        {
            P.HeightmapPath = Beside(JsonPath, Leaf);
        }
        if (O->TryGetStringField(TEXT("provenance"), Leaf))
        {
            P.ProvenancePath = Beside(JsonPath, Leaf);
        }
        P.Resolution = Int2(O, TEXT("resolution"));
        P.Components = Int2(O, TEXT("components"));
        P.SectionSizeQuads = static_cast<int32>(Num(O, TEXT("section_size_quads")));
        P.SectionsPerComponent = static_cast<int32>(Num(O, TEXT("sections_per_component")));
        P.ActorScale = Vec3(O, TEXT("actor_scale"), FVector(100.0, 100.0, 100.0));
        P.ActorLocationCm = Vec3(O, TEXT("actor_location_cm"), FVector::ZeroVector);
        P.ElevMinM = Num(O, TEXT("elev_min_m"));
        P.ElevMaxM = Num(O, TEXT("elev_max_m"));
        P.ElevMidM = Num(O, TEXT("elev_mid_m"));
        P.Cells1m = static_cast<int64>(Num(O, TEXT("cells_1m")));
        P.Cells19Resampled = static_cast<int64>(Num(O, TEXT("cells_19_resampled")));
        P.CellsNodata = static_cast<int64>(Num(O, TEXT("cells_nodata")));
        O->TryGetStringField(TEXT("height_decode"), P.HeightDecode);
    }

    /** A plan that cannot describe a legal landscape is refused BEFORE anything is spawned. Unreal
     *  requires resolution == quads*components + 1 exactly; a mismatch produces an actor that exists,
     *  reports success, and is silently the wrong size. */
    bool Validate(const MAirLandscapeImporter::FPlan& P, FString& OutError)
    {
        if (P.Resolution.X <= 1 || P.Resolution.Y <= 1)
        {
            OutError = FString::Printf(TEXT("%s: resolution %dx%d is not a landscape"),
                                       *P.Name, P.Resolution.X, P.Resolution.Y);
            return false;
        }
        static const int32 Legal[] = { 7, 15, 31, 63, 127, 255 };
        bool bLegalSection = false;
        for (int32 S : Legal)
        {
            bLegalSection |= (P.SectionSizeQuads == S);
        }
        if (!bLegalSection)
        {
            OutError = FString::Printf(TEXT("%s: section size %d is not one of 7/15/31/63/127/255"),
                                       *P.Name, P.SectionSizeQuads);
            return false;
        }
        if (P.SectionsPerComponent != 1 && P.SectionsPerComponent != 2)
        {
            OutError = FString::Printf(TEXT("%s: sections per component must be 1 or 2, got %d"),
                                       *P.Name, P.SectionsPerComponent);
            return false;
        }
        const int32 Quads = P.SectionSizeQuads * P.SectionsPerComponent;
        const int32 WantX = Quads * P.Components.X + 1;
        const int32 WantY = Quads * P.Components.Y + 1;
        if (WantX != P.Resolution.X || WantY != P.Resolution.Y)
        {
            OutError = FString::Printf(
                TEXT("%s: %d quads x %d components + 1 = %dx%d, but the plan says %dx%d"),
                *P.Name, Quads, P.Components.X, WantX, WantY, P.Resolution.X, P.Resolution.Y);
            return false;
        }
        if (!IFileManager::Get().FileExists(*P.HeightmapPath))
        {
            OutError = FString::Printf(TEXT("%s: heightmap not found: %s"),
                                       *P.Name, *P.HeightmapPath);
            return false;
        }
        const int64 Expect = static_cast<int64>(P.Resolution.X) * P.Resolution.Y * 2;
        const int64 Actual = IFileManager::Get().FileSize(*P.HeightmapPath);
        if (Actual != Expect)
        {
            // A SHORT FILE IS THE FAILURE THAT LOOKS LIKE SUCCESS. Unreal would import whatever it
            // got and pad or truncate; the landscape would exist, and its southern edge would be
            // wrong with nothing to compare against.
            OutError = FString::Printf(
                TEXT("%s: heightmap is %lld bytes, expected %lld for %dx%d uint16"),
                *P.Name, Actual, Expect, P.Resolution.X, P.Resolution.Y);
            return false;
        }
        return true;
    }
}

namespace MAirLandscapeImporter
{

bool LoadPlan(const FString& JsonPath, FPlan& Out, FString& OutError)
{
    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *JsonPath))
    {
        OutError = FString::Printf(TEXT("cannot read %s"), *JsonPath);
        return false;
    }
    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        OutError = FString::Printf(TEXT("%s is not valid JSON"), *JsonPath);
        return false;
    }

    Out = FPlan();
    ReadCommon(Root, JsonPath, Out);
    Out.WorldPartitionGridSize = static_cast<int32>(Num(Root, TEXT("world_partition_grid_size"), 4.0));
    Out.QuadMetres = Num(Root, TEXT("quad_metres"), 1.0);
    Root->TryGetStringField(TEXT("source"), Out.Source);

    // A RIBBON SIDECAR CARRIES SEGMENTS. Each is its own landscape with its own transform, because
    // each hugs the route where it actually runs; they are not tiles of one grid.
    const TArray<TSharedPtr<FJsonValue>>* Segs = nullptr;
    if (Root->TryGetArrayField(TEXT("segments"), Segs) && Segs)
    {
        for (const TSharedPtr<FJsonValue>& V : *Segs)
        {
            const TSharedPtr<FJsonObject> O = V->AsObject();
            if (!O.IsValid())
            {
                continue;
            }
            FPlan S;
            ReadCommon(O, JsonPath, S);
            S.WorldPartitionGridSize = Out.WorldPartitionGridSize;
            S.QuadMetres = Out.QuadMetres;
            S.Source = Out.Source;
            Out.Segments.Add(MoveTemp(S));
        }
        if (Out.Segments.Num() == 0)
        {
            OutError = FString::Printf(TEXT("%s declares segments but none parsed"), *JsonPath);
            return false;
        }
    }

    // Validate every landscape this plan would build, before building any of them.
    const TArray<FPlan>& All = Out.Segments.Num() ? Out.Segments : TArray<FPlan>({ Out });
    for (const FPlan& P : All)
    {
        if (!Validate(P, OutError))
        {
            return false;
        }
    }
    return true;
}

ALandscape* ImportOne(UWorld* World, const FPlan& Plan, FString& OutError)
{
    if (!World)
    {
        OutError = TEXT("no world");
        return nullptr;
    }

    TArray<uint8> Bytes;
    if (!FFileHelper::LoadFileToArray(Bytes, *Plan.HeightmapPath))
    {
        OutError = FString::Printf(TEXT("cannot read %s"), *Plan.HeightmapPath);
        return nullptr;
    }
    const int32 Count = Plan.Resolution.X * Plan.Resolution.Y;
    TArray<uint16> Heights;
    Heights.SetNumUninitialized(Count);
    FMemory::Memcpy(Heights.GetData(), Bytes.GetData(), static_cast<SIZE_T>(Count) * 2);
    Bytes.Empty();

    // The sequence below follows LandscapeEditorDetailCustomization_NewLandscape.cpp deliberately.
    ALandscape* Landscape = World->SpawnActor<ALandscape>(Plan.ActorLocationCm, FRotator::ZeroRotator);
    if (!Landscape)
    {
        OutError = FString::Printf(TEXT("%s: SpawnActor<ALandscape> failed"), *Plan.Name);
        return nullptr;
    }
    Landscape->SetActorRelativeScale3D(Plan.ActorScale);

    // Unreal's own heuristic, kept rather than invented: lightmass falls over on large landscapes
    // unless the lighting LOD backs off with vertex count.
    Landscape->StaticLightingLOD = FMath::DivideAndRoundUp(
        FMath::CeilLogTwo(static_cast<uint32>((Plan.Resolution.X * Plan.Resolution.Y) / (2048 * 2048) + 1)),
        static_cast<uint32>(2));

    TMap<FGuid, TArray<uint16>> HeightDataPerLayers;
    HeightDataPerLayers.Add(FGuid(), MoveTemp(Heights));
    TMap<FGuid, TArray<FLandscapeImportLayerInfo>> MaterialLayerDataPerLayers;
    MaterialLayerDataPerLayers.Add(FGuid(), TArray<FLandscapeImportLayerInfo>());

    Landscape->Import(FGuid::NewGuid(), 0, 0, Plan.Resolution.X - 1, Plan.Resolution.Y - 1,
                      Plan.SectionsPerComponent, Plan.SectionSizeQuads,
                      HeightDataPerLayers, *Plan.HeightmapPath,
                      MaterialLayerDataPerLayers, ELandscapeImportAlphamapType::Additive,
                      TArrayView<const FLandscapeLayer>());

    ULandscapeInfo* Info = Landscape->GetLandscapeInfo();
    if (!Info)
    {
        OutError = FString::Printf(TEXT("%s: imported but has no LandscapeInfo"), *Plan.Name);
        return nullptr;
    }
    FActorLabelUtilities::SetActorLabelUnique(Landscape, Plan.Name);
    Info->UpdateLayerInfoMap(Landscape);

    // WORLD PARTITION LAST. ChangeGridSize splits the landscape into streaming proxies, and it needs
    // a LandscapeInfo that already knows its components.
    if (Plan.WorldPartitionGridSize > 0)
    {
        if (ULandscapeSubsystem* Sub = World->GetSubsystem<ULandscapeSubsystem>())
        {
            Sub->ChangeGridSize(Info, static_cast<uint32>(Plan.WorldPartitionGridSize));
        }
    }

    UE_LOG(LogTemp, Log,
           TEXT("[MAirCorridor] landscape '%s': %dx%d, %dx%d components of %d quads x %d, scale %s, "
                "Z origin %.2f m, %s"),
           *Plan.Name, Plan.Resolution.X, Plan.Resolution.Y, Plan.Components.X, Plan.Components.Y,
           Plan.SectionSizeQuads, Plan.SectionsPerComponent, *Plan.ActorScale.ToString(),
           Plan.ElevMidM, *Plan.HeightDecode);
    return Landscape;
}

int32 ImportPlan(UWorld* World, const FPlan& Plan, TArray<ALandscape*>& OutActors, FString& OutError)
{
    const TArray<FPlan>& All = Plan.Segments.Num() ? Plan.Segments : TArray<FPlan>({ Plan });
    for (const FPlan& P : All)
    {
        ALandscape* A = ImportOne(World, P, OutError);
        if (!A)
        {
            // STOP AT THE FIRST FAILURE rather than carrying on. A half-built ribbon is worse than
            // none: the level looks populated and one segment of the route is missing.
            return OutActors.Num();
        }
        OutActors.Add(A);
    }
    return OutActors.Num();
}

}
