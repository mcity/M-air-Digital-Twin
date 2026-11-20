// MAirTrafficActor.h - real aircraft overhead, flown in the level from an ADS-B feed.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Engine/StaticMesh.h"
#include "MAirTrafficActor.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

/**
 * One aircraft being flown in the level: what the feed last said about it, and what is drawing it.
 *
 * The position and the velocity are already in Unreal centimetres along this level's own axes when
 * they arrive, because the tool that fetches them owns the landscape's projection and this does
 * not. Everything here is arithmetic on a vector.
 */
USTRUCT()
struct FMAirTrafficAircraft
{
    GENERATED_BODY()

    UPROPERTY() FString Address;          // the ICAO 24 bit address, which is the identity
    UPROPERTY() FString Callsign;
    UPROPERTY() FName Class;              // light, large, heavy, rotorcraft, vehicle and so on
    UPROPERTY() float SpanMetres = 20.f;  // roughly how wide it is, for scaling a stand in shape

    UPROPERTY() FVector ReportedLocation = FVector::ZeroVector;
    UPROPERTY() FVector VelocityPerSecond = FVector::ZeroVector;
    UPROPERTY() float Yaw = 0.f;
    UPROPERTY() float AltitudeMetres = 0.f;
    UPROPERTY() float HeightAboveGroundMetres = 0.f;
    UPROPERTY() bool bOnGround = false;
    UPROPERTY() bool bOverLandscape = false;

    /** Seconds between the position being REPORTED and the snapshot being written. */
    UPROPERTY() float AgeAtSnapshot = 0.f;
    /** When this level last read it, in the world's own time, which is what ticking measures. */
    UPROPERTY() double ReadAtTime = 0.0;

    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> Mesh = nullptr;
    UPROPERTY(Transient) TObjectPtr<UTextRenderComponent> Label = nullptr;
};

/**
 * AMAirTrafficActor - flies the real traffic overhead, from a file the ADS-B tool keeps up to date.
 *
 * WHAT IT IS FOR. A flight planned over M-City shares the sky with real aircraft, and a plan made
 * without them is a plan made with one eye shut. Tools/adsb.py fetches them from the OpenSky
 * Network and writes a snapshot; this reads that snapshot and puts them in the level, moving, at
 * the right height, pointing the way they are going.
 *
 * WHY A FILE AND NOT A SOCKET. The fetching needs an OAuth2 token, a credit budget, a projection
 * and a datum decision, and all of that is already written, tested and documented in Python. A
 * level that reads one JSON file has nothing to get wrong, works the same in the editor as in a
 * packaged build, and can be driven from a recording when there is no network. Point this at the
 * file and run:
 *
 *     py -3.10 adsb.py --watch --snapshot %TEMP%/maircorridor_traffic.json
 *     py -3.10 adsb.py --replay traffic.jsonl --snapshot %TEMP%/maircorridor_traffic.json
 *
 * The flight planner and the launcher both write that same file, so the default here finds it
 * with nothing to set.
 *
 * MODELS ARE YOURS TO ASSIGN. A state vector never says "Boeing 737"; it says "large", if it says
 * anything at all. So ModelsByClass maps those few size classes onto whatever meshes you have, and
 * anything with no model assigned falls back to a plain shape scaled to the right size, which reads
 * far better in a view than a model of the wrong aircraft would.
 *
 * IT MOVES BETWEEN REPORTS. A position arrives every twenty seconds or so, because the feed has a
 * credit budget. Flying the aircraft on from there along its own track and vertical rate is what
 * makes the sky look alive rather than like a slide show, and it is honest for the few seconds
 * involved. An aircraft that stops being reported is removed rather than flown onwards on faith.
 */
UCLASS(Blueprintable, ClassGroup = (MAirCorridor), meta = (DisplayName = "M-Air Live Traffic"))
class MAIRCORRIDORTRAFFIC_API AMAirTrafficActor : public AActor
{
    GENERATED_BODY()

public:
    AMAirTrafficActor();

    // ---- the feed ---------------------------------------------------------------------------

    /**
     * The JSON file Tools/adsb.py keeps replacing. Defaults to maircorridor_traffic.json in the
     * user's temporary folder, which is where the planner and the launcher write it.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feed")
    FString SnapshotFile;

    /** How often to look at the file. Cheap: it is only read when its timestamp changes. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feed",
              meta = (ClampMin = "0.25", ClampMax = "30.0"))
    float ReadEverySeconds = 2.f;

    /** Fly each aircraft on from its last report along its own track, speed and vertical rate. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feed")
    bool bDeadReckon = true;

    /** Remove an aircraft whose last report is older than this. Nothing is flown on for ever. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feed",
              meta = (ClampMin = "5.0"))
    float ForgetAfterSeconds = 120.f;

    /** Aircraft and vehicles sitting on the ground. Off, because an airport has dozens. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feed")
    bool bIncludeOnGround = false;

    /** Only those over the landscape itself, rather than everything in the fetched box. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feed")
    bool bOnlyOverLandscape = false;

    /** A ceiling, so a busy box cannot spawn hundreds of components. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feed", meta = (ClampMin = "1"))
    int32 MaxAircraft = 80;

    // ---- how it looks -----------------------------------------------------------------------

    /**
     * A mesh for each class the feed reports: light, small, large, heavy, fast, rotorcraft,
     * glider, balloon, parachutist, ultralight, uav, spacecraft, vehicle, obstacle, unknown.
     * Leave one out and it gets FallbackMesh at the right size.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Models")
    TMap<FName, TSoftObjectPtr<UStaticMesh>> ModelsByClass;

    /** Used for any class with no model of its own. A sphere by default. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Models")
    TSoftObjectPtr<UStaticMesh> FallbackMesh;

    /** Used for anything on the surface rather than in the air. A cylinder by default. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Models")
    TSoftObjectPtr<UStaticMesh> GroundVehicleMesh;

    /**
     * Scale each mesh so it is as wide as the aircraft it stands for. On, because a model of
     * unknown size is the normal case and a marker of the wrong size is worse than a wrong shape.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Models")
    bool bScaleToSpan = true;

    /** A multiplier on top of that, for when a correct size is too subtle to see. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Models",
              meta = (ClampMin = "0.1", ClampMax = "50.0"))
    float ExtraScale = 1.f;

    /** Callsign and height, drawn beside each aircraft and turned to face the viewer. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Models")
    bool bShowLabels = true;

    /** Label height in centimetres. These are read from kilometres away, so it is not small. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Models", meta = (ClampMin = "10.0"))
    float LabelSize = 400.f;

    /** How many aircraft are being flown right now, and when the feed was last written. */
    UFUNCTION(BlueprintCallable, Category = "Feed")
    int32 GetAircraftCount() const { return Aircraft.Num(); }

    UFUNCTION(BlueprintCallable, Category = "Feed")
    FString GetFeedStatus() const { return Status; }

    // ---- AActor -----------------------------------------------------------------------------
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual bool ShouldTickIfViewportsOnly() const override { return true; }
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
    /** Read the snapshot if it has changed since last time. Returns true when it was re-read. */
    bool ReadSnapshotIfChanged();
    void ApplySnapshot(const TSharedPtr<class FJsonObject>& Root);
    void MoveEverything(float DeltaSeconds);
    void Forget(const FString& Address);

    UStaticMesh* MeshFor(const FMAirTrafficAircraft& One) const;
    void Dress(FMAirTrafficAircraft& One);
    bool ViewerLocation(FVector& Out) const;

    // Transient for the same reason the components are: what is in the sky right now is not
    // part of the level and has no business being saved into it.
    UPROPERTY(Transient) TMap<FString, FMAirTrafficAircraft> Aircraft;
    UPROPERTY(Transient) FString Status = TEXT("not read yet");

    double LastLookTime = 0.0;
    FDateTime SnapshotWritten = FDateTime::MinValue();
    double SnapshotFetchedUnix = 0.0;
    int32 ReadCount = 0;
};
