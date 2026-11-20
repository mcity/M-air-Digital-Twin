// MAirScanMeshComponent.h - the M-City photogrammetric scan, streamed as mesh. The scan loader and nothing else.
//
// Depends on stock Unreal only. It reads the tile sets the scan
// pipeline writes - index.json, the .ancm tile blobs (one file per level of detail) and the scan's source
// textures - and streams them around the viewer: nearest tiles first, finer levels close, coarser far, decoded off
// the game thread.
//
// It is a SCENE component so the scan has a transform of its own: tiles attach beneath it, and moving the
// component moves the whole scan.

#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "Containers/Queue.h"
#include "HAL/ThreadSafeCounter.h"
#include "Templates/SharedPointer.h"
#include "MAirScanMeshComponent.generated.h"

class UProceduralMeshComponent;
class UMaterialInterface;
class UTexture2D;

/** One tile's entry from index.json - enough to decide whether it should be resident, and at which level. */
USTRUCT()
struct FMAirScanTile
{
    GENERATED_BODY()

    UPROPERTY() FString File;
    UPROPERTY() int32 TileX = 0;
    UPROPERTY() int32 TileZ = 0;
    UPROPERTY() int32 Triangles = 0;

    /** One entry per level, coarsest last; index 0 is the full-resolution mesh. */
    UPROPERTY() TArray<FString> LevelFiles;
    UPROPERTY() TArray<int32> LevelTriangles;

    /** Centre and radius in Unreal space, precomputed - the distance test runs against every tile every tick. */
    FVector UnrealCentre = FVector::ZeroVector;
    double RadiusUU = 0.0;
};

/** One tile decoded OFF the game thread - geometry only, no UObject anywhere in it. */
struct FMAirScanTileData
{
    int32 TileIndex = INDEX_NONE;
    TArray<FVector> Verts;
    TArray<FVector> Normals;
    TArray<FColor> Colors;
    TArray<FVector2D> UVs;
    TArray<int32> Tris;
    /** One run of the index buffer per source texture: {material id, first index, index count}. */
    TArray<FIntVector> Submeshes;
    int32 Generation = 0;
    int32 Level = 0;
    uint8 Result = 0;
};

/** Why a tile load stopped, so a failure is named rather than silent. */
UENUM()
enum class EMAirScanLoad : uint8
{
    Ok,
    FileMissing,
    NotAnAncmBlob,
    UnsupportedVersion,
    Truncated,
    Empty,
};

UCLASS(ClassGroup = (MAirCorridor), meta = (BlueprintSpawnableComponent))
class MAIRCORRIDORSCAN_API UMAirScanMeshComponent : public USceneComponent
{
    GENERATED_BODY()

public:
    UMAirScanMeshComponent();

    /**
     * The tile set to load. A relative path is looked for under this plugin's Content folder and then the
     * project's; an absolute path, or a content-browser "/Mount/rest" path, is used as given. Nowhere else -
     * in particular no other plugin, so a set that is missing from here fails here.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan")
    FString TilesDirectory = TEXT("Scans/mcity_scan_mesh");

    /** Where TilesDirectory actually resolved to. Empty until the index loads. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Scan")
    FString ResolvedTilesDir;

    /** How far from the viewer a tile stays resident at any level, in metres. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan")
    double LoadRadiusM = 1500.0;

    /**
     * Load every tile, whatever the load radius says, so the whole scan is simply there.
     *
     * The radius exists because a scan can be larger than anything that should be resident at once,
     * and for flying over it a tile you cannot see is wasted memory. It is the wrong behaviour while
     * looking FOR the scan: an empty viewport looks the same whether the scan is far away, missing,
     * or in the wrong place. With this on, every tile loads, distant ones still at their coarsest
     * level of detail, so the thing can be seen and judged.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan")
    bool bLoadAllTiles = true;

    /** Distance in metres at which each level gives way to the next, nearest first. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan")
    TArray<float> LodDistancesM;

    /** Hysteresis in metres before a loaded tile is dropped, so a viewer on a boundary does not thrash. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan")
    double UnloadMarginM = 64.0;

    /** Tile reads allowed in flight on the worker pool at once. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan")
    int32 MaxInFlight = 8;

    /** Decoded tiles installed per tick - creating mesh sections is game-thread work. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan")
    int32 MaxInstallsPerTick = 2;

    /** The longest edge a scan texture is kept at, in texels (the sources are 8192 square). 0 keeps the source. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan", meta = (ClampMin = "0"))
    int32 MaxTextureSizePx = 2048;

    /** Vertex-colour material. Left null, the engine's VertexColorMaterial is used. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan")
    TObjectPtr<UMaterialInterface> Material;

    /**
     * A material with a texture parameter, to draw the scan's own photographs. Left None, the plugin's
     * Materials/M_MCityScan is used. Vertex colour only appears if neither is available.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan")
    TObjectPtr<UMaterialInterface> TextureBaseMaterial;

    /** The texture parameter on TextureBaseMaterial the scan's image is bound to. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan")
    FName TextureParameterName = FName("BaseColor");

    /** Collision on the scan geometry. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan")
    bool bCreateCollision = true;

    /**
     * Whether the scan casts shadows. Off by default: the photographs already hold the shadows of the day
     * they were taken, the default material is unlit so the scan receives none, and every camera a drone
     * carries keeps shadow maps of its own, so a shadow-casting scan is drawn once more per camera per frame
     * for nothing anyone sees on it. Turn it on for the scan's shadows to fall on vehicles and aircraft.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan")
    bool bCastShadows = false;

    /**
     * PUT THE SCAN ON THE MAIRCORRIDOR LANDSCAPE. The tiles are in the scan pipeline's own survey frame (EPSG:5070 Albers,
     * the corridor grid); the landscape is UTM 17N (EPSG:26917) measured from its north-west corner. Between those two
     * map grids the mapping is an AFFINE - turned about 9.2 degrees and slightly skewed, because Albers stretches
     * north-south differently from east-west - and no actor transform can hold a skew, so it is applied to every vertex
     * as tiles load. Fitted over the whole scan: worst residual 1.3 cm. With this on, leave the actor at 0,0,0 with no
     * rotation and a scale of 1.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan|Placement")
    bool bAlignToLandscape = true;

    /** X' = X * AlignRowX.X + Y * AlignRowX.Y + AlignRowX.Z, centimetres, scan-local to landscape. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan|Placement")
    FVector AlignRowX = FVector(0.9938986151, -0.1611426338, 758265.7154);

    /** Y' = X * AlignRowY.X + Y * AlignRowY.Y + AlignRowY.Z, centimetres, scan-local to landscape. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan|Placement")
    FVector AlignRowY = FVector(0.1598422385, 0.9806417355, -538143.4506);

    /**
     * Z' = Z + this, centimetres. Scan heights are elevation - 162.672 m and the landscape's Z is elevation x 100, so this
     * is 162.672 m plus the 1.38 m by which this landscape's elevation model sits above the scan's ground (the peak of
     * 63,693 vertex-by-vertex differences around the Mcity M).
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scan|Placement")
    float AlignZOffsetCm = 16404.7f;

#if WITH_EDITOR
    /** A placement or tile-set edit reloads the tiles, so what is on screen always matches the numbers. */
    virtual void PostEditChangeProperty(FPropertyChangedEvent& Event) override;
#endif

    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void OnRegister() override;
    virtual void OnUnregister() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType,
                               FActorComponentTickFunction* ThisTickFunction) override;

    /** Tiles currently on screen. */
    UFUNCTION(BlueprintCallable, Category = "Scan")
    int32 ResidentTiles() const { return Resident.Num(); }

    /** Tiles the index knows about. */
    UFUNCTION(BlueprintCallable, Category = "Scan")
    int32 KnownTiles() const { return Tiles.Num(); }

    /** Point the loader at a different tile set. Drops everything and re-reads the index. */
    UFUNCTION(BlueprintCallable, Category = "Scan")
    bool SetTilesDirectory(const FString& NewDirectory);

    /** Show or hide the scan. Hiding drops the tiles rather than freezing them. */
    UFUNCTION(BlueprintCallable, Category = "Scan")
    void SetScanEnabled(bool bEnabled);

private:
    UPROPERTY(Transient) TArray<FMAirScanTile> Tiles;
    /** Tile section key -> its mesh component. */
    UPROPERTY(Transient) TMap<FIntVector, TObjectPtr<UProceduralMeshComponent>> Sections;
    /** Material id -> the material bound to that id's texture. */
    UPROPERTY(Transient) TMap<int32, TObjectPtr<UMaterialInterface>> MaterialCache;
    /** Decoded textures, owned here so they are collected with the component. */
    UPROPERTY(Transient) TArray<TObjectPtr<UTexture2D>> DecodedTextures;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> DefaultMaterial;

    TMap<int32, FString> MaterialTextures;   // material id -> texture file name, from the index
    TMap<int32, int32> Resident;             // tile index -> installed level
    TMap<int32, int32> ResidentSections;     // tile index -> sections it has up
    TSet<int32> InFlight;
    TQueue<TSharedPtr<FMAirScanTileData, ESPMode::ThreadSafe>, EQueueMode::Mpsc> Ready;
    FThreadSafeCounter FlushGeneration;

    FString AttemptedDirectory;
    bool bWarnedNoViewer = false;
    bool bWarnedSectionsLost = false;

    /** True when a section this component installed has been destroyed by something else. */
    bool SectionsLost() const;
    bool bIndexAttempted = false;
    bool bIndexLoaded = false;
    bool bScanEnabled = true;
    int32 DiagLoaded = 0;
    int32 DiagFailed = 0;
    double LastReportTime = 0.0;

    bool EnsureLoaded();
    void Teardown();
    void DropAll();
    bool LoadIndex();
    FString ResolveTilesDir(TArray<FString>& Tried) const;
    void RequestTile(int32 Index, int32 Level);
    int32 DesiredLevel(int32 Index, double DistanceUU) const;
    void InstallReady(int32 Budget);
    bool ViewerLocation(FVector& Out) const;
    UMaterialInterface* MaterialForId(int32 MaterialId);
    /** Texture Base Material, or the plugin's own scan material when that is unset. */
    UMaterialInterface* PhotoMaterial() const;
    void InstallSection(const FIntVector& Key, const FMAirScanTileData& Data, const TArray<int32>& Tris,
                        UMaterialInterface* Override);
    void RemoveSection(const FIntVector& Key);
};
