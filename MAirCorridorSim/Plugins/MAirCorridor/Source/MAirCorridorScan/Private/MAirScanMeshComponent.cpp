// MAirScanMeshComponent.cpp - the M-City scan loader. See the header.

#include "MAirScanMeshComponent.h"

#include "Async/Async.h"
#include "Dom/JsonObject.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "ImageCore.h"
#include "ImageUtils.h"
#include "Interfaces/IPluginManager.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ProceduralMeshComponent.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
/* The tile files are in the scan pipeline's own frame: METRES, Y-UP, right-handed. Unreal is CENTIMETRES, Z-UP,
 * left-handed. Unreal.X = x, Unreal.Y = z, Unreal.Z = y, times 100, so
 * the scan lands where the pipeline placed it. The swap has determinant -1, which is why triangle winding flips below. */
constexpr double MetresToUU = 100.0;

FORCEINLINE FVector ToUnreal(double X, double Y, double Z)
{
    return FVector(X * MetresToUU, Z * MetresToUU, Y * MetresToUU);
}

/* The placement onto the landscape (see bAlignToLandscape), captured BY VALUE so a worker thread never reads the
 * component. X/Y take the affine; normals take its inverse-transpose; Z shifts. The affine's determinant is positive,
 * so triangle winding is unchanged. */
struct FAlign
{
    bool bOn = false;
    double A11 = 1.0, A12 = 0.0, Tx = 0.0, A21 = 0.0, A22 = 1.0, Ty = 0.0, Dz = 0.0;

    FORCEINLINE FVector Apply(const FVector& P) const
    {
        if (!bOn)
        {
            return P;
        }
        return FVector(A11 * P.X + A12 * P.Y + Tx, A21 * P.X + A22 * P.Y + Ty, P.Z + Dz);
    }

    FORCEINLINE FVector ApplyNormal(const FVector& N) const
    {
        if (!bOn)
        {
            return N;
        }
        const double Det = A11 * A22 - A12 * A21;
        return FVector((A22 * N.X - A21 * N.Y) / Det, (-A12 * N.X + A11 * N.Y) / Det, N.Z);
    }

    /** The largest stretch the affine applies, so a tile's bounding radius stays conservative after it. */
    FORCEINLINE double MaxStretch() const
    {
        return bOn ? FMath::Max(FMath::Sqrt(A11 * A11 + A21 * A21), FMath::Sqrt(A12 * A12 + A22 * A22)) : 1.0;
    }
};

FAlign AlignOf(const UMAirScanMeshComponent& C)
{
    FAlign Al;
    Al.bOn = C.bAlignToLandscape;
    Al.A11 = C.AlignRowX.X; Al.A12 = C.AlignRowX.Y; Al.Tx = C.AlignRowX.Z;
    Al.A21 = C.AlignRowY.X; Al.A22 = C.AlignRowY.Y; Al.Ty = C.AlignRowY.Z;
    Al.Dz = C.AlignZOffsetCm;
    if (Al.bOn && FMath::Abs(Al.A11 * Al.A22 - Al.A12 * Al.A21) < 1e-9)
    {
        Al.bOn = false;   // a degenerate affine would collapse the scan to a line; refuse it rather than draw that
    }
    return Al;
}

/* ANCM blob header: magic, version, vertex count, index count, bbox; v2 adds submesh count and flags. */
constexpr int32 ANCM_HEADER_V1 = 4 + 12 + 24;
constexpr int32 ANCM_HEADER_V2 = ANCM_HEADER_V1 + 8;

/* The size must add up exactly: a header that disagrees with the file length is truncated or counted in the wrong
 * unit (index_count is INDICES, not triangles), and both would otherwise read back as plausible geometry. */
FORCEINLINE bool AncmSizeIsSane(int64 FileBytes, uint32 Version, uint32 VCount, uint32 ICount, uint32 SubCount,
                                uint32 Flags)
{
    if (ICount % 3 != 0)
    {
        return false;
    }
    int64 Expected = ((Version >= 2) ? ANCM_HEADER_V2 : ANCM_HEADER_V1)
        + (int64)VCount * 12 + (int64)VCount * 12 + (int64)VCount * 4 + (int64)ICount * 4;
    if (Version >= 2)
    {
        if (Flags & 1)
        {
            Expected += (int64)VCount * 8;
        }
        Expected += (int64)SubCount * 12;
    }
    return FileBytes == Expected;
}

/* Decode one tile blob into plain arrays. Runs on a worker thread, so nothing here touches a UObject. */
EMAirScanLoad DecodeAncm(const FString& Path, FMAirScanTileData& Out, const FAlign& Al)
{
    TArray<uint8> Bytes;
    if (!FFileHelper::LoadFileToArray(Bytes, *Path))
    {
        return EMAirScanLoad::FileMissing;
    }
    if (Bytes.Num() < ANCM_HEADER_V1)
    {
        return EMAirScanLoad::Truncated;
    }
    if (Bytes[0] != 'A' || Bytes[1] != 'N' || Bytes[2] != 'C' || Bytes[3] != 'M')
    {
        return EMAirScanLoad::NotAnAncmBlob;
    }
    const uint8* P = Bytes.GetData();
    uint32 Version = 0, VCount = 0, ICount = 0, SubCount = 1, Flags = 0;
    FMemory::Memcpy(&Version, P + 4, 4);
    FMemory::Memcpy(&VCount, P + 8, 4);
    FMemory::Memcpy(&ICount, P + 12, 4);
    if (Version < 1 || Version > 2)
    {
        return EMAirScanLoad::UnsupportedVersion;
    }
    if (Version >= 2)
    {
        if (Bytes.Num() < ANCM_HEADER_V2)
        {
            return EMAirScanLoad::Truncated;
        }
        FMemory::Memcpy(&SubCount, P + ANCM_HEADER_V1, 4);
        FMemory::Memcpy(&Flags, P + ANCM_HEADER_V1 + 4, 4);
    }
    if (VCount == 0 || ICount == 0)
    {
        return EMAirScanLoad::Empty;
    }
    if (!AncmSizeIsSane(Bytes.Num(), Version, VCount, ICount, SubCount, Flags))
    {
        return EMAirScanLoad::Truncated;
    }

    const int64 HeaderBytes = (Version >= 2) ? ANCM_HEADER_V2 : ANCM_HEADER_V1;
    const bool bHasUV = (Version >= 2) && (Flags & 1);
    const float* Pos = reinterpret_cast<const float*>(P + HeaderBytes);
    const float* Nrm = Pos + (int64)VCount * 3;
    const uint8* Col = reinterpret_cast<const uint8*>(Nrm + (int64)VCount * 3);
    const float* Uvs = bHasUV ? reinterpret_cast<const float*>(Col + (int64)VCount * 4) : nullptr;
    const uint32* Idx = reinterpret_cast<const uint32*>(
        bHasUV ? reinterpret_cast<const uint8*>(Uvs + (int64)VCount * 2) : Col + (int64)VCount * 4);
    const uint32* Subs = (Version >= 2) ? (Idx + (int64)ICount) : nullptr;

    Out.Verts.Reset(VCount);
    Out.Normals.Reset(VCount);
    Out.Colors.Reset(VCount);
    Out.UVs.Reset(bHasUV ? VCount : 0);
    Out.Tris.Reset(ICount);
    Out.Submeshes.Reset();
    for (uint32 i = 0; i < VCount; ++i)
    {
        Out.Verts.Add(Al.Apply(ToUnreal(Pos[i * 3 + 0], Pos[i * 3 + 1], Pos[i * 3 + 2])));
        Out.Normals.Add(Al.ApplyNormal(ToUnreal(Nrm[i * 3 + 0], Nrm[i * 3 + 1], Nrm[i * 3 + 2])).GetSafeNormal());
        Out.Colors.Add(FColor(Col[i * 4 + 0], Col[i * 4 + 1], Col[i * 4 + 2], Col[i * 4 + 3]));
        if (bHasUV)
        {
            // V flips: OBJ texture space runs up, Unreal's runs down.
            Out.UVs.Add(FVector2D(Uvs[i * 2 + 0], 1.0 - Uvs[i * 2 + 1]));
        }
    }
    // Winding flips with the determinant -1 axis map, or every face points away from the camera.
    for (uint32 t = 0; t + 2 < ICount; t += 3)
    {
        Out.Tris.Add((int32)Idx[t + 0]);
        Out.Tris.Add((int32)Idx[t + 2]);
        Out.Tris.Add((int32)Idx[t + 1]);
    }
    if (Subs)
    {
        for (uint32 k = 0; k < SubCount; ++k)
        {
            const int32 Mat = (int32)Subs[k * 3 + 0];
            const int32 First = (int32)Subs[k * 3 + 1];
            const int32 Count = (int32)Subs[k * 3 + 2];
            if (First >= 0 && Count > 0 && First + Count <= Out.Tris.Num())   // a run off the end is dropped
            {
                Out.Submeshes.Add(FIntVector(Mat, First, Count));
            }
        }
    }
    if (Out.Submeshes.Num() == 0)
    {
        Out.Submeshes.Add(FIntVector(0, 0, Out.Tris.Num()));
    }
    return EMAirScanLoad::Ok;
}

/* A tile's sections are keyed {tile x, section ordinal, tile z}. */
FORCEINLINE FIntVector SectionKey(const FMAirScanTile& T, int32 Section)
{
    return FIntVector(T.TileX, Section, T.TileZ);
}
}   // namespace

UMAirScanMeshComponent::UMAirScanMeshComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    bTickInEditor = true;   // stream in the editor viewport too, not only in Play
    LodDistancesM = { 150.0f, 300.0f, 600.0f };
}

namespace
{
    /**
     * THE SCAN'S OWN PHOTOGRAPHS WHEN NOTHING ELSE IS SET, loaded the first time they are needed.
     *
     * NOT IN THE CONSTRUCTOR, though that is where a default normally goes. A constructor runs while
     * the engine is still starting, and anything it loads then joins the permanent object pool,
     * which can never be deleted. A material in that pool cannot lose a node: deleting one asserts
     * !IsRooted() and takes the editor down. That was measured, not supposed: rebuilding this
     * material from a script crashed exactly that way while the constructor loaded it. Loading it
     * here, when a scan first draws, keeps it an ordinary asset that can be opened and edited.
     *
     * Nothing references it hard, so a packaged build only carries it if a level assigns it to
     * Texture Base Material, or the project cooks /MAirCorridor/Materials.
     */
    UMaterialInterface* PluginScanMaterial()
    {
        static TWeakObjectPtr<UMaterialInterface> Cached;
        if (!Cached.IsValid())
        {
            Cached = LoadObject<UMaterialInterface>(
                nullptr, TEXT("/MAirCorridor/Materials/M_MCityScan.M_MCityScan"), nullptr, LOAD_NoWarn);
        }
        return Cached.Get();
    }
}

UMaterialInterface* UMAirScanMeshComponent::PhotoMaterial() const
{
    return TextureBaseMaterial ? TextureBaseMaterial.Get() : PluginScanMaterial();
}

void UMAirScanMeshComponent::BeginPlay()
{
    Super::BeginPlay();
    EnsureLoaded();
}

void UMAirScanMeshComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    Teardown();
    Super::EndPlay(Reason);
}

void UMAirScanMeshComponent::OnRegister()
{
    Super::OnRegister();
    const UWorld* W = GetWorld();
    if (W && !W->IsGameWorld())
    {
        EnsureLoaded();
    }
}

void UMAirScanMeshComponent::OnUnregister()
{
    const UWorld* W = GetWorld();
    if (W && !W->IsGameWorld())
    {
        Teardown();
    }
    Super::OnUnregister();
}

bool UMAirScanMeshComponent::EnsureLoaded()
{
    if (bIndexLoaded && AttemptedDirectory == TilesDirectory)
    {
        return true;
    }
    if (bIndexAttempted && AttemptedDirectory == TilesDirectory)
    {
        return false;   // already tried this exact directory; retry only when it changes
    }
    bIndexAttempted = true;
    AttemptedDirectory = TilesDirectory;
    if (!DefaultMaterial)
    {
        DefaultMaterial = Material ? Material.Get() : LoadObject<UMaterialInterface>(
            nullptr, TEXT("/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial"));
    }
    bIndexLoaded = LoadIndex();
    if (bIndexLoaded)
    {
        /* WHERE IT IS, EVERY TIME. "The scan is not loading" and "the scan is somewhere else" look
         * identical from the camera, and the difference is a number nobody can see. The bounds are
         * known the moment the index is read, so they are printed then. */
        FVector Lo(TNumericLimits<double>::Max()), Hi(-TNumericLimits<double>::Max());
        for (const FMAirScanTile& T : Tiles)
        {
            Lo = Lo.ComponentMin(T.UnrealCentre - FVector(T.RadiusUU));
            Hi = Hi.ComponentMax(T.UnrealCentre + FVector(T.RadiusUU));
        }
        const FTransform& ToWorld = GetComponentTransform();
        const FVector WorldLo = ToWorld.TransformPosition(Lo);
        const FVector WorldHi = ToWorld.TransformPosition(Hi);
        const FVector WorldMid = (WorldLo + WorldHi) * 0.5;
        UE_LOG(LogTemp, Log,
               TEXT("[MAirScan] %d tiles indexed in %s. Centre world X %.0f Y %.0f Z %.0f, spanning "
                    "%.0f x %.0f m. %s"),
               Tiles.Num(), *ResolvedTilesDir, WorldMid.X, WorldMid.Y, WorldMid.Z,
               (WorldHi.X - WorldLo.X) / MetresToUU, (WorldHi.Y - WorldLo.Y) / MetresToUU,
               bLoadAllTiles ? TEXT("Loading every tile.")
                             : *FString::Printf(TEXT("Loading within %.0f m of the camera; tick "
                                                     "'Load All Tiles' to load the lot."), LoadRadiusM));
        if (MaterialTextures.Num() > 0 && !PhotoMaterial())
        {
            UE_LOG(LogTemp, Warning, TEXT("[MAirScan] the scan names %d texture(s) but TextureBaseMaterial is unset - "
                                          "drawing in vertex colour. Assign a material with a '%s' texture "
                                          "parameter to use them."),
                   MaterialTextures.Num(), *TextureParameterName.ToString());
        }
    }
    return bIndexLoaded;
}

bool UMAirScanMeshComponent::SectionsLost() const
{
    /* HAS SOMETHING TAKEN OUR GEOMETRY AWAY?
     *
     * The sections are ordinary components owned by the actor, so anything that tears the actor's
     * components down destroys them: starting Play, a simulator reinitialising the scene, a level
     * reload. `Sections` is a UPROPERTY, so those pointers become null, while `Resident` still says
     * every tile is loaded. The component then reports "148/148 tiles resident" for ever and draws
     * nothing, which is the most misleading state it can possibly be in.
     *
     * One dead section is enough to know it happened. */
    for (const TPair<FIntVector, TObjectPtr<UProceduralMeshComponent>>& Pair : Sections)
    {
        const UProceduralMeshComponent* M = Pair.Value.Get();
        if (!IsValid(M) || !M->IsRegistered())
        {
            return true;
        }
    }
    return false;
}

void UMAirScanMeshComponent::DropAll()
{
    // Workers may still be reading: bumping the generation makes whatever they produce be discarded.
    FlushGeneration.Increment();
    TSharedPtr<FMAirScanTileData, ESPMode::ThreadSafe> Drop;
    while (Ready.Dequeue(Drop)) { }
    InFlight.Reset();
    for (auto& Pair : Sections)
    {
        if (UProceduralMeshComponent* M = Pair.Value.Get())
        {
            if (IsValid(M))
            {
                M->DestroyComponent();
            }
        }
    }
    Sections.Empty();
    Resident.Reset();
    ResidentSections.Reset();
}

void UMAirScanMeshComponent::Teardown()
{
    DropAll();
    MaterialCache.Reset();
    DecodedTextures.Reset();
    Tiles.Reset();
    MaterialTextures.Reset();
    bIndexLoaded = false;
    bIndexAttempted = false;
    AttemptedDirectory.Reset();
}

FString UMAirScanMeshComponent::ResolveTilesDir(TArray<FString>& Tried) const
{
    Tried.Reset();
    if (TilesDirectory.IsEmpty())
    {
        return FString();
    }
    if (FPaths::IsRelative(TilesDirectory))
    {
        if (const TSharedPtr<IPlugin> Self = IPluginManager::Get().FindPlugin(TEXT("MAirCorridor")))
        {
            Tried.Add(FPaths::Combine(Self->GetContentDir(), TilesDirectory));
        }
        Tried.Add(FPaths::Combine(FPaths::ProjectContentDir(), TilesDirectory));
        // NO FALLBACK INTO ANOTHER PLUGIN. Searching some other plugin's Content folder would let a
        // scan load from a copy this plugin does not ship, so a missing tile set would look like
        // success on one machine and fail on the next. The tiles live here.
    }
    else
    {
        // A content-browser path, "/<Mount>/rest" - what you get copying a folder path in the editor. The mount
        // is a plugin name (or Game), and the rest lives under that plugin's (or the project's) Content folder.
        if (TilesDirectory.StartsWith(TEXT("/")))
        {
            FString Mount, Sub;
            if (!TilesDirectory.Mid(1).Split(TEXT("/"), &Mount, &Sub))
            {
                Mount = TilesDirectory.Mid(1);
            }
            FString Root;
            if (Mount == TEXT("Game"))
            {
                Root = FPaths::ProjectContentDir();
            }
            else if (const TSharedPtr<IPlugin> Pl = IPluginManager::Get().FindPlugin(Mount))
            {
                Root = Pl->GetContentDir();
            }
            if (!Root.IsEmpty())
            {
                Tried.Add(FPaths::Combine(Root, Sub));
            }
        }
        Tried.Add(TilesDirectory);

        // AN ABSOLUTE PATH IS ONE MACHINE'S PATH. Saved into a level ("J:/.../mcity_scan_mesh") it names nothing on
        // any other machine, so the tile set's own trailing folders are also looked for where this plugin keeps its
        // content - "Scans/mcity_scan_mesh" first, then "mcity_scan_mesh" - and the scan travels with the plugin.
        FString Normal = TilesDirectory;
        FPaths::NormalizeDirectoryName(Normal);
        TArray<FString> Parts;
        Normal.ParseIntoArray(Parts, TEXT("/"), true);
        const TSharedPtr<IPlugin> Self = IPluginManager::Get().FindPlugin(TEXT("MAirCorridor"));
        for (int32 Keep = FMath::Min(2, Parts.Num()); Keep >= 1; --Keep)
        {
            const FString Tail = FString::Join(TArrayView<const FString>(Parts).Right(Keep), TEXT("/"));
            if (Self.IsValid())
            {
                Tried.AddUnique(FPaths::Combine(Self->GetContentDir(), Tail));
            }
            Tried.AddUnique(FPaths::Combine(FPaths::ProjectContentDir(), Tail));
        }
    }
    for (const FString& C : Tried)
    {
        if (IFileManager::Get().FileExists(*FPaths::Combine(C, TEXT("index.json"))))
        {
            return C;
        }
    }
    return FString();
}

bool UMAirScanMeshComponent::LoadIndex()
{
    TArray<FString> Tried;
    ResolvedTilesDir = ResolveTilesDir(Tried);
    if (ResolvedTilesDir.IsEmpty())
    {
        UE_LOG(LogTemp, Warning, TEXT("[MAirScan] scan tiles '%s' not found (no index.json). Looked in:"),
               *TilesDirectory);
        for (const FString& T : Tried)
        {
            UE_LOG(LogTemp, Warning, TEXT("           %s"), *T);
        }
        return false;
    }

    FString Raw;
    const FString IndexPath = FPaths::Combine(ResolvedTilesDir, TEXT("index.json"));
    if (!FFileHelper::LoadFileToString(Raw, *IndexPath))
    {
        return false;
    }
    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        UE_LOG(LogTemp, Warning, TEXT("[MAirScan] %s is not readable JSON"), *IndexPath);
        return false;
    }

    MaterialTextures.Reset();
    const TArray<TSharedPtr<FJsonValue>>* Mats = nullptr;
    if (Root->TryGetArrayField(TEXT("materials"), Mats) && Mats)
    {
        for (const TSharedPtr<FJsonValue>& MV : *Mats)
        {
            const TSharedPtr<FJsonObject>* MO = nullptr;
            if (!MV.IsValid() || !MV->TryGetObject(MO) || !MO)
            {
                continue;
            }
            int32 Id = 0;
            FString Tex;
            (*MO)->TryGetNumberField(TEXT("id"), Id);
            (*MO)->TryGetStringField(TEXT("texture"), Tex);
            if (!Tex.IsEmpty())
            {
                MaterialTextures.Add(Id, Tex);
            }
        }
    }

    const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
    if (!Root->TryGetArrayField(TEXT("tiles"), Arr) || !Arr)
    {
        return false;
    }
    Tiles.Reset();
    for (const TSharedPtr<FJsonValue>& V : *Arr)
    {
        const TSharedPtr<FJsonObject>* O = nullptr;
        if (!V.IsValid() || !V->TryGetObject(O) || !O)
        {
            continue;
        }
        FMAirScanTile T;
        (*O)->TryGetStringField(TEXT("file"), T.File);
        (*O)->TryGetNumberField(TEXT("tile_x"), T.TileX);
        (*O)->TryGetNumberField(TEXT("tile_z"), T.TileZ);
        (*O)->TryGetNumberField(TEXT("triangles"), T.Triangles);
        if (T.File.IsEmpty())
        {
            continue;
        }
        FVector Mn = FVector::ZeroVector, Mx = FVector::ZeroVector;
        const TArray<TSharedPtr<FJsonValue>>* JMn = nullptr;
        const TArray<TSharedPtr<FJsonValue>>* JMx = nullptr;
        if ((*O)->TryGetArrayField(TEXT("min"), JMn) && JMn && JMn->Num() >= 3 &&
            (*O)->TryGetArrayField(TEXT("max"), JMx) && JMx && JMx->Num() >= 3)
        {
            Mn = FVector((*JMn)[0]->AsNumber(), (*JMn)[1]->AsNumber(), (*JMn)[2]->AsNumber());
            Mx = FVector((*JMx)[0]->AsNumber(), (*JMx)[1]->AsNumber(), (*JMx)[2]->AsNumber());
        }
        const TArray<TSharedPtr<FJsonValue>>* Lv = nullptr;
        if ((*O)->TryGetArrayField(TEXT("levels"), Lv) && Lv)
        {
            for (const TSharedPtr<FJsonValue>& LvV : *Lv)
            {
                const TSharedPtr<FJsonObject>* LO = nullptr;
                if (!LvV.IsValid() || !LvV->TryGetObject(LO) || !LO)
                {
                    continue;
                }
                FString LFile;
                int32 LTris = 0;
                (*LO)->TryGetStringField(TEXT("file"), LFile);
                (*LO)->TryGetNumberField(TEXT("triangles"), LTris);
                if (!LFile.IsEmpty())
                {
                    T.LevelFiles.Add(LFile);
                    T.LevelTriangles.Add(LTris);
                }
            }
        }
        if (T.LevelFiles.Num() == 0)   // an index written before levels existed: the tile's own file
        {
            T.LevelFiles.Add(T.File);
            T.LevelTriangles.Add(T.Triangles);
        }
        const FVector A = ToUnreal(Mn.X, Mn.Y, Mn.Z);
        const FVector B = ToUnreal(Mx.X, Mx.Y, Mx.Z);
        const FAlign Al = AlignOf(*this);
        T.UnrealCentre = Al.Apply((A + B) * 0.5);
        T.RadiusUU = (B - A).Size() * 0.5 * Al.MaxStretch();
        Tiles.Add(MoveTemp(T));
    }
    return Tiles.Num() > 0;
}

#if WITH_EDITOR
void UMAirScanMeshComponent::PostEditChangeProperty(FPropertyChangedEvent& Event)
{
    Super::PostEditChangeProperty(Event);
    // Every loaded tile was decoded under the old placement or tile set; drop them all and let the tick reload.
    Teardown();
}
#endif

bool UMAirScanMeshComponent::SetTilesDirectory(const FString& NewDirectory)
{
    Teardown();
    TilesDirectory = NewDirectory;
    return !NewDirectory.IsEmpty() && EnsureLoaded();
}

void UMAirScanMeshComponent::SetScanEnabled(bool bEnabled)
{
    if (bScanEnabled == bEnabled)
    {
        return;
    }
    bScanEnabled = bEnabled;
    if (!bEnabled)
    {
        DropAll();
    }
}

bool UMAirScanMeshComponent::ViewerLocation(FVector& Out) const
{
    const UWorld* W = GetWorld();
    if (!W)
    {
        return false;
    }
    if (const APlayerController* PC = W->GetFirstPlayerController())
    {
        if (const APawn* P = PC->GetPawn())
        {
            Out = P->GetActorLocation();
            return true;
        }
        FRotator R;
        PC->GetPlayerViewPoint(Out, R);
        return true;
    }
    if (W->ViewLocationsRenderedLastFrame.Num() > 0)   // the editor viewport
    {
        Out = W->ViewLocationsRenderedLastFrame[0];
        return true;
    }
    return false;
}

int32 UMAirScanMeshComponent::DesiredLevel(int32 Index, double DistanceUU) const
{
    const int32 Last = Tiles[Index].LevelFiles.Num() - 1;
    const double D = FMath::Max(0.0, DistanceUU) / MetresToUU;
    for (int32 L = 0; L < LodDistancesM.Num(); ++L)
    {
        if (D < (double)LodDistancesM[L])
        {
            return FMath::Min(L, Last);
        }
    }
    return Last;
}

UMaterialInterface* UMAirScanMeshComponent::MaterialForId(int32 MaterialId)
{
    UMaterialInterface* Base = PhotoMaterial();
    if (!Base)
    {
        return nullptr;   // vertex colour
    }
    if (TObjectPtr<UMaterialInterface>* Found = MaterialCache.Find(MaterialId))
    {
        return Found->Get();
    }
    UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(Base, this);
    const FString* TexName = MaterialTextures.Find(MaterialId);
    if (MID && TexName && !TexName->IsEmpty())
    {
        // Decoded once per material and cached: the sources are 8192-square JPEGs, 268 MB each uncompressed.
        const FString Path = FPaths::Combine(ResolvedTilesDir, *TexName);
        TArray<uint8> Raw;
        FImage Img;
        if (FFileHelper::LoadFileToArray(Raw, *Path) && FImageUtils::DecompressImage(Raw.GetData(), Raw.Num(), Img))
        {
            UTexture2D* Tex = nullptr;
            const int32 Longest = FMath::Max(Img.SizeX, Img.SizeY);
            if (MaxTextureSizePx > 0 && Longest > MaxTextureSizePx)
            {
                const double Scale = (double)MaxTextureSizePx / (double)Longest;
                FImage Small;
                Img.ResizeTo(Small, FMath::Max(1, FMath::RoundToInt32(Img.SizeX * Scale)),
                             FMath::Max(1, FMath::RoundToInt32(Img.SizeY * Scale)), ERawImageFormat::BGRA8,
                             EGammaSpace::sRGB);
                Tex = FImageUtils::CreateTexture2DFromImage(Small);
            }
            else
            {
                Tex = FImageUtils::CreateTexture2DFromImage(Img);
            }
            if (Tex)
            {
                DecodedTextures.Add(Tex);
                MID->SetTextureParameterValue(TextureParameterName, Tex);
            }
        }
        else
        {
            UE_LOG(LogTemp, Warning, TEXT("[MAirScan] scan texture missing or unreadable: %s"), *Path);
        }
    }
    MaterialCache.Add(MaterialId, MID);
    return MID;
}

void UMAirScanMeshComponent::RequestTile(int32 Index, int32 Level)
{
    const FMAirScanTile& Tile = Tiles[Index];
    Level = FMath::Clamp(Level, 0, FMath::Max(0, Tile.LevelFiles.Num() - 1));
    const FString Path = FPaths::Combine(ResolvedTilesDir, Tile.LevelFiles[Level]);
    const int32 Gen = FlushGeneration.GetValue();
    TWeakObjectPtr<UMAirScanMeshComponent> WeakSelf(this);   // never a raw `this` across threads
    const FAlign Al = AlignOf(*this);                        // by value: the worker never reads the component

    InFlight.Add(Index);
    Async(EAsyncExecution::ThreadPool, [Path, Index, Level, Gen, WeakSelf, Al]()
    {
        TSharedPtr<FMAirScanTileData, ESPMode::ThreadSafe> Data = MakeShared<FMAirScanTileData, ESPMode::ThreadSafe>();
        Data->TileIndex = Index;
        Data->Generation = Gen;
        Data->Level = Level;
        Data->Result = (uint8)DecodeAncm(Path, *Data, Al);
        AsyncTask(ENamedThreads::GameThread, [Data, WeakSelf]()
        {
            UMAirScanMeshComponent* Self = WeakSelf.Get();
            if (Self && Self->FlushGeneration.GetValue() == Data->Generation)
            {
                Self->Ready.Enqueue(Data);
            }
        });
    });
}

void UMAirScanMeshComponent::InstallSection(const FIntVector& Key, const FMAirScanTileData& Data,
                                            const TArray<int32>& Tris, UMaterialInterface* Override)
{
    check(IsInGameThread());
    TObjectPtr<UProceduralMeshComponent>* Existing = Sections.Find(Key);
    UProceduralMeshComponent* Mesh = Existing ? Existing->Get() : nullptr;
    if (!Mesh)
    {
        // Transient: streamed geometry is never saved into the level.
        Mesh = NewObject<UProceduralMeshComponent>(GetOwner(), NAME_None,
                                                   RF_Transient | RF_DuplicateTransient | RF_TextExportTransient);
        Mesh->bUseAsyncCooking = bCreateCollision;   // must precede the first CreateMeshSection
        Mesh->SetCanEverAffectNavigation(false);
        Mesh->SetVisibleInRayTracing(false);
        Mesh->CastShadow = bCastShadows;
        Mesh->RegisterComponent();
        Mesh->AttachToComponent(this, FAttachmentTransformRules::KeepRelativeTransform);
        Sections.Add(Key, Mesh);
    }
    static const TArray<FProcMeshTangent> NoTangents;
    static const TArray<FVector2D> NoUVs;
    const bool bHasUV = Data.UVs.Num() == Data.Verts.Num();
    Mesh->CreateMeshSection(0, Data.Verts, Tris, Data.Normals, bHasUV ? Data.UVs : NoUVs, Data.Colors, NoTangents,
                            bCreateCollision);
    UMaterialInterface* Use = Override ? Override : (Material ? Material.Get() : DefaultMaterial.Get());
    if (Use)
    {
        Mesh->SetMaterial(0, Use);
    }
}

void UMAirScanMeshComponent::RemoveSection(const FIntVector& Key)
{
    TObjectPtr<UProceduralMeshComponent> Found;
    if (Sections.RemoveAndCopyValue(Key, Found) && Found)
    {
        Found->DestroyComponent();
    }
}

void UMAirScanMeshComponent::InstallReady(int32 Budget)
{
    TSharedPtr<FMAirScanTileData, ESPMode::ThreadSafe> Data;
    while (Budget > 0 && Ready.Dequeue(Data))
    {
        if (!Data.IsValid() || !Tiles.IsValidIndex(Data->TileIndex))
        {
            continue;
        }
        const int32 Index = Data->TileIndex;
        InFlight.Remove(Index);
        const FMAirScanTile& T = Tiles[Index];

        // A level swap can change the section count; sections the new level does not replace must go.
        const int32 WasSections = ResidentSections.FindRef(Index);
        for (int32 s = Data->Submeshes.Num(); s < WasSections; ++s)
        {
            RemoveSection(SectionKey(T, s));
        }
        if ((EMAirScanLoad)Data->Result != EMAirScanLoad::Ok)
        {
            ++DiagFailed;
            Resident.Add(Index, Data->Level);   // do not retry a broken file every tick; name it once
            UE_LOG(LogTemp, Warning, TEXT("[MAirScan] tile %s failed to decode (reason %d)"), *T.File,
                   (int32)Data->Result);
            continue;
        }
        const int32 NumSub = Data->Submeshes.Num();
        for (int32 s = 0; s < NumSub; ++s)
        {
            const FIntVector& Sub = Data->Submeshes[s];
            TArray<int32> SubTris;
            if (NumSub == 1)
            {
                SubTris = Data->Tris;
            }
            else
            {
                SubTris.Append(Data->Tris.GetData() + Sub.Y, Sub.Z);
            }
            InstallSection(SectionKey(T, s), *Data, SubTris, MaterialForId(Sub.X));
        }
        ResidentSections.Add(Index, NumSub);
        Resident.Add(Index, Data->Level);
        ++DiagLoaded;
        --Budget;
    }
}

void UMAirScanMeshComponent::TickComponent(float DeltaTime, ELevelTick TickType,
                                           FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
    if (!bScanEnabled || !EnsureLoaded())
    {
        return;
    }
    /* REBUILD WHAT WAS TAKEN. Cheap: a pointer test per installed section, and it only ever fires
     * once per teardown, after which the tiles stream back in on the following ticks. */
    if (Sections.Num() > 0 && SectionsLost())
    {
        if (!bWarnedSectionsLost)
        {
            bWarnedSectionsLost = true;
            UE_LOG(LogTemp, Warning,
                   TEXT("[MAirScan] the scan's mesh sections were destroyed by something outside this "
                        "component (starting Play and a simulator reinitialising the scene both do "
                        "it). Rebuilding all %d tiles."), Tiles.Num());
        }
        DropAll();
    }

    InstallReady(FMath::Max(1, MaxInstallsPerTick));

    /* NO VIEWER IS NOT A REASON TO DRAW NOTHING.
     *
     * This used to return here, which is the quietest possible failure: no tiles load, no diagnostic
     * is printed, and the viewport is empty with a log that says the index loaded fine. A viewer
     * position is only needed to decide WHICH tiles are near enough and at what level of detail.
     * When every tile is wanted anyway, the component's own position answers both, so the scan loads
     * whether or not anything has told us where the camera is. */
    FVector Viewer;
    if (!ViewerLocation(Viewer))
    {
        if (!bLoadAllTiles)
        {
            if (!bWarnedNoViewer)
            {
                bWarnedNoViewer = true;
                UE_LOG(LogTemp, Warning,
                       TEXT("[MAirScan] no camera position is available, so nothing can be streamed "
                            "around it. Tick 'Load All Tiles' to load the scan regardless."));
            }
            return;
        }
        Viewer = GetComponentLocation();
    }
    // Tiles are in the component's frame; measure the viewer in that frame too, so moving the component
    // moves the whole scan without breaking which tiles are near.
    const FVector Local = GetComponentTransform().InverseTransformPosition(Viewer);
    // bLoadAllTiles makes the radius infinite rather than special-casing every test below it.
    const double Everything = TNumericLimits<double>::Max() * 0.25;
    const double LoadUU = bLoadAllTiles ? Everything : LoadRadiusM * MetresToUU;
    const double DropUU = bLoadAllTiles ? Everything : (LoadRadiusM + UnloadMarginM) * MetresToUU;

    TArray<int32> ToDrop;
    for (const TPair<int32, int32>& R : Resident)
    {
        if (Tiles.IsValidIndex(R.Key) &&
            FVector::Dist(Local, Tiles[R.Key].UnrealCentre) - Tiles[R.Key].RadiusUU > DropUU)
        {
            ToDrop.Add(R.Key);
        }
    }
    for (int32 i : ToDrop)
    {
        const int32 N = FMath::Max(1, ResidentSections.FindRef(i));
        for (int32 s = 0; s < N; ++s)
        {
            RemoveSection(SectionKey(Tiles[i], s));
        }
        ResidentSections.Remove(i);
        Resident.Remove(i);
    }

    // Nearest missing (or wrong-level) tiles first, up to the in-flight cap.
    int32 Slots = FMath::Max(1, MaxInFlight) - InFlight.Num();
    while (Slots-- > 0)
    {
        int32 Best = INDEX_NONE, BestLevel = 0;
        double BestD = TNumericLimits<double>::Max();
        for (int32 i = 0; i < Tiles.Num(); ++i)
        {
            if (InFlight.Contains(i))
            {
                continue;
            }
            const double D = FVector::Dist(Local, Tiles[i].UnrealCentre) - Tiles[i].RadiusUU;
            if (D > LoadUU || D >= BestD)
            {
                continue;
            }
            const int32 Want = DesiredLevel(i, D);
            const int32* Have = Resident.Find(i);
            if (!Have || *Have != Want)
            {
                BestD = D;
                Best = i;
                BestLevel = Want;
            }
        }
        if (Best == INDEX_NONE)
        {
            break;
        }
        RequestTile(Best, BestLevel);
    }

    const double Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
    if (Resident.Num() == 0 && InFlight.Num() == 0 && Tiles.Num() > 0 && Now - LastReportTime > 5.0)
    {
        // NOTHING IN RANGE, said out loud rather than shown as an empty viewport. The scan hangs off this component
        // at its surveyed offset, so an actor dropped where the camera happened to be moves the whole scan
        // kilometres away from that camera.
        LastReportTime = Now;
        double Nearest = TNumericLimits<double>::Max();
        FVector Sum = FVector::ZeroVector;
        for (const FMAirScanTile& T : Tiles)
        {
            Nearest = FMath::Min(Nearest, FVector::Dist(Local, T.UnrealCentre) - T.RadiusUU);
            Sum += T.UnrealCentre;
        }
        const FVector WorldCentre = GetComponentTransform().TransformPosition(Sum / (double)Tiles.Num());
        UE_LOG(LogTemp, Warning, TEXT("[MAirScan] nothing to load: the camera is %.2f km from the nearest scan tile "
                                      "(load radius %.0f m). The scan's centre is at world X %.0f Y %.0f Z %.0f (cm). "
                                      "Fly there, or tick 'Load All Tiles' on this component to load the whole scan "
                                      "wherever the camera is."),
               FMath::Max(0.0, Nearest) / (MetresToUU * 1000.0), LoadRadiusM, WorldCentre.X, WorldCentre.Y,
               WorldCentre.Z);
    }
    if (DiagLoaded + DiagFailed > 0 && Now - LastReportTime > 5.0)
    {
        LastReportTime = Now;
        int64 Tris = 0;
        for (const TPair<int32, int32>& R : Resident)
        {
            if (Tiles.IsValidIndex(R.Key) && Tiles[R.Key].LevelTriangles.IsValidIndex(R.Value))
            {
                Tris += Tiles[R.Key].LevelTriangles[R.Value];
            }
        }
        /* WHAT THE ENGINE HAS, not what this component believes. The counts above come from the
         * index: they say what SHOULD be loaded and prove nothing about the scene. These come from
         * the components themselves, so an empty viewport can be told apart from empty geometry. */
        int32 Comps = 0, Secs = 0;
        FBox Box(ForceInit);
        for (const TPair<FIntVector, TObjectPtr<UProceduralMeshComponent>>& Pair : Sections)
        {
            UProceduralMeshComponent* M = Pair.Value.Get();
            if (!IsValid(M))
            {
                continue;
            }
            ++Comps;
            Secs += M->GetNumSections();
            if (M->IsRegistered())
            {
                Box += M->Bounds.GetBox();
            }
        }
        UE_LOG(LogTemp, Log, TEXT("[MAirScan] %d/%d tiles resident, %d in flight, %lld triangles (%d loaded, %d failed)"),
               Resident.Num(), Tiles.Num(), InFlight.Num(), Tris, DiagLoaded, DiagFailed);
        UE_LOG(LogTemp, Log,
               TEXT("[MAirScan] in the scene: %d mesh component(s), %d section(s), visible %d, bounds %s"),
               Comps, Secs, IsVisible() ? 1 : 0,
               Box.IsValid ? *FString::Printf(TEXT("X %.0f..%.0f Y %.0f..%.0f Z %.0f..%.0f"),
                                              Box.Min.X, Box.Max.X, Box.Min.Y, Box.Max.Y, Box.Min.Z, Box.Max.Z)
                           : TEXT("NONE - nothing registered has any"));
    }
}
