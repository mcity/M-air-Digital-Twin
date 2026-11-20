// MAirTrafficActor.cpp - real aircraft overhead, flown in the level from an ADS-B feed.
#include "MAirTrafficActor.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformProcess.h"
#include "Misc/Paths.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/ConstructorHelpers.h"

DEFINE_LOG_CATEGORY_STATIC(LogMAirTraffic, Log, All);

namespace
{
    /** Unix seconds, to compare against the "fetched" field the tool writes. */
    double UnixNow()
    {
        return static_cast<double>(FDateTime::UtcNow().ToUnixTimestamp());
    }

    float JsonNumber(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, float Fallback = 0.f)
    {
        double Value = 0.0;
        return (Obj.IsValid() && Obj->TryGetNumberField(Field, Value))
            ? static_cast<float>(Value) : Fallback;
    }

    /** A three element array of numbers, which is how positions and velocities arrive. */
    bool JsonVector(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, FVector& Out)
    {
        const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
        if (!Obj.IsValid() || !Obj->TryGetArrayField(Field, Array) || !Array || Array->Num() < 3)
        {
            return false;
        }
        Out = FVector((*Array)[0]->AsNumber(), (*Array)[1]->AsNumber(), (*Array)[2]->AsNumber());
        return true;
    }
}

AMAirTrafficActor::AMAirTrafficActor()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = true;
    // The aircraft have to move in the editor viewport, not only in Play: planning a flight
    // around traffic means looking at the traffic while planning, with the game not running.
    PrimaryActorTick.bTickEvenWhenPaused = false;

    // The same file the planner and the launcher write: Python's tempfile and Unreal's user temp
    // folder are both the TEMP folder on Windows. A machine specific default here was the first
    // thing anyone else would have tripped over.
    SnapshotFile = FPaths::Combine(FPlatformProcess::UserTempDir(),
                                   TEXT("maircorridor_traffic.json"));

    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    RootComponent->SetMobility(EComponentMobility::Movable);

    // NOT SPATIALLY LOADED, and this is not optional. Traffic covers a box tens of kilometres
    // across while this actor sits at one point in it. Under World Partition an actor is filed
    // into the cell its own location falls in, so a spatially loaded one is simply absent unless
    // the viewer happens to be standing in that cell, and nothing appears. The scan actor in this
    // plugin learned the same lesson the hard way.
    // Editor-only data: World Partition files actors into cells when the level is saved, and a
    // packaged game only ever sees the result, so the game build has no such property.
#if WITH_EDITORONLY_DATA
    bIsSpatiallyLoaded = false;
#endif

    // Stand in shapes, so this works before anything is assigned. Both are engine content and
    // neither is redistributed by this plugin.
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(
        TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(
        TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    if (Sphere.Succeeded())
    {
        FallbackMesh = Sphere.Object;
    }
    if (Cylinder.Succeeded())
    {
        GroundVehicleMesh = Cylinder.Object;
    }

    // THE BUILT AIRCRAFT, one per class (Tools/blender/aircraft_builder.py from Tools/aircraft/
    // fleet.json, imported by Tools/unreal/import_aircraft.py): real dimensions, nose along +X.
    // Soft references, so a class whose model is missing simply falls back to the stand in shape.
    // An actor whose models were assigned in the level keeps its own.
    static const TCHAR* const Built[][2] = {
        {TEXT("light"), TEXT("light_cessna172")},
        {TEXT("small"), TEXT("small_kingair350")},
        {TEXT("large"), TEXT("large_b737")},
        {TEXT("heavy"), TEXT("heavy_b777")},
        {TEXT("fast"), TEXT("fast_t38")},
        {TEXT("rotorcraft"), TEXT("rotorcraft_bell407")},
        {TEXT("glider"), TEXT("glider_two_seat")},
        {TEXT("balloon"), TEXT("balloon_hot_air")},
        {TEXT("ultralight"), TEXT("ultralight")},
        {TEXT("uav"), TEXT("uav_fixed_wing")},
        {TEXT("vehicle"), TEXT("vehicle_airport_truck")},
    };
    for (const auto& Pair : Built)
    {
        ModelsByClass.Add(FName(Pair[0]), TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(
            FString::Printf(TEXT("/MAirCorridor/Aircraft/%s/%s.%s"), Pair[1], Pair[1], Pair[1]))));
    }
    GroundVehicleMesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(
        TEXT("/MAirCorridor/Aircraft/vehicle_airport_truck/vehicle_airport_truck.vehicle_airport_truck")));
}

void AMAirTrafficActor::BeginPlay()
{
    Super::BeginPlay();
    LastLookTime = 0.0;
}

void AMAirTrafficActor::EndPlay(const EEndPlayReason::Type Reason)
{
    TArray<FString> Addresses;
    Aircraft.GetKeys(Addresses);
    for (const FString& Address : Addresses)
    {
        Forget(Address);
    }
    Super::EndPlay(Reason);
}

void AMAirTrafficActor::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);

    const UWorld* W = GetWorld();
    const double Now = W ? W->GetRealTimeSeconds() : 0.0;
    if (Now - LastLookTime >= FMath::Max(0.25f, ReadEverySeconds))
    {
        LastLookTime = Now;
        ReadSnapshotIfChanged();
    }
    MoveEverything(DeltaSeconds);
}

bool AMAirTrafficActor::ReadSnapshotIfChanged()
{
    if (SnapshotFile.IsEmpty())
    {
        Status = TEXT("no snapshot file set");
        return false;
    }
    IFileManager& Files = IFileManager::Get();
    const FDateTime Written = Files.GetTimeStamp(*SnapshotFile);
    if (Written == FDateTime::MinValue())
    {
        Status = FString::Printf(TEXT("%s is not there. Run: py -3.10 adsb.py --watch --snapshot %s"),
                                 *SnapshotFile, *SnapshotFile);
        return false;
    }
    if (Written == SnapshotWritten)
    {
        return false;                   // nothing new, and reading it again would cost for nothing
    }

    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *SnapshotFile))
    {
        // A read that lands while the tool is replacing the file is normal and not worth a fuss:
        // the next look, two seconds later, gets it.
        return false;
    }
    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        Status = TEXT("the snapshot was not valid JSON");
        return false;
    }
    SnapshotWritten = Written;
    ++ReadCount;
    ApplySnapshot(Root);
    return true;
}

void AMAirTrafficActor::ApplySnapshot(const TSharedPtr<FJsonObject>& Root)
{
    SnapshotFetchedUnix = JsonNumber(Root, TEXT("fetched"), static_cast<float>(UnixNow()));
    const double Behind = FMath::Max(0.0, UnixNow() - SnapshotFetchedUnix);

    const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
    if (!Root->TryGetArrayField(TEXT("aircraft"), List) || !List)
    {
        Status = TEXT("the snapshot held no aircraft list");
        return;
    }

    const UWorld* W = GetWorld();
    const double Now = W ? W->GetRealTimeSeconds() : 0.0;
    TSet<FString> Present;
    int32 Shown = 0;

    for (const TSharedPtr<FJsonValue>& Value : *List)
    {
        const TSharedPtr<FJsonObject> Item = Value.IsValid() ? Value->AsObject() : nullptr;
        if (!Item.IsValid())
        {
            continue;
        }
        FVector Where;
        if (!JsonVector(Item, TEXT("unreal_cm"), Where))
        {
            continue;               // no altitude, so no place to put it: a position alone is not
        }                           // enough to draw an aircraft in a level
        const bool bGround = Item->HasField(TEXT("on_ground")) && Item->GetBoolField(TEXT("on_ground"));
        if (bGround && !bIncludeOnGround)
        {
            continue;
        }
        const bool bOver = !Item->HasField(TEXT("over_landscape"))
            || Item->GetBoolField(TEXT("over_landscape"));
        if (bOnlyOverLandscape && !bOver)
        {
            continue;
        }
        if (Shown >= MaxAircraft)
        {
            break;
        }

        FString Address;
        if (!Item->TryGetStringField(TEXT("icao24"), Address) || Address.IsEmpty())
        {
            continue;               // without an address there is no way to follow it between reports
        }
        ++Shown;
        Present.Add(Address);

        FMAirTrafficAircraft& One = Aircraft.FindOrAdd(Address);
        const bool bNew = !One.Mesh;
        One.Address = Address;
        Item->TryGetStringField(TEXT("callsign"), One.Callsign);
        FString Kind;
        if (Item->TryGetStringField(TEXT("class"), Kind))
        {
            One.Class = FName(*Kind);
        }
        One.SpanMetres = JsonNumber(Item, TEXT("span_m"), 20.f);
        One.ReportedLocation = Where;
        FVector Velocity = FVector::ZeroVector;
        JsonVector(Item, TEXT("unreal_velocity_cm_s"), Velocity);
        One.VelocityPerSecond = Velocity;
        One.Yaw = JsonNumber(Item, TEXT("unreal_yaw_deg"), One.Yaw);
        One.AltitudeMetres = JsonNumber(Item, TEXT("altitude_m"));
        One.HeightAboveGroundMetres = JsonNumber(Item, TEXT("agl_m"));
        One.bOnGround = bGround;
        One.bOverLandscape = bOver;
        One.AgeAtSnapshot = JsonNumber(Item, TEXT("age_s")) + static_cast<float>(Behind);
        One.ReadAtTime = Now;

        if (bNew || One.Mesh == nullptr)
        {
            Dress(One);
        }
    }

    // Anything the feed has stopped mentioning has either left the box or gone quiet. Either way
    // it is not known to be anywhere, so it goes rather than hanging in the sky.
    TArray<FString> Addresses;
    Aircraft.GetKeys(Addresses);
    for (const FString& Address : Addresses)
    {
        if (!Present.Contains(Address))
        {
            Forget(Address);
        }
    }

    const int32 Credits = static_cast<int32>(JsonNumber(Root, TEXT("credits_left"), -1.f));

    // THE FEED'S OWN HEALTH, as the tool reports it. A feed whose requests are failing keeps its
    // last good picture rather than writing an empty sky, so this is the only way to tell a quiet
    // sky from a broken feed, and it goes at the front of the status where it will be seen.
    FString Health;
    const TSharedPtr<FJsonObject>* HealthObj = nullptr;
    if (Root->TryGetObjectField(TEXT("health"), HealthObj) && HealthObj && HealthObj->IsValid())
    {
        FString State, Reason;
        (*HealthObj)->TryGetStringField(TEXT("state"), State);
        (*HealthObj)->TryGetStringField(TEXT("reason"), Reason);
        if (!State.IsEmpty() && State != TEXT("healthy"))
        {
            Health = FString::Printf(TEXT("FEED %s: %s. "), *State.ToUpper(), *Reason);
            UE_LOG(LogMAirTraffic, Warning, TEXT("traffic feed %s: %s"), *State, *Reason);
        }
    }
    Status = FString::Printf(
        TEXT("%s%d aircraft, read %d time(s), snapshot %.0f s old%s"),
        *Health, Aircraft.Num(), ReadCount, Behind,
        Credits >= 0 ? *FString::Printf(TEXT(", %d credits left"), Credits) : TEXT(""));
    UE_LOG(LogMAirTraffic, Verbose, TEXT("%s"), *Status);
}

void AMAirTrafficActor::MoveEverything(float DeltaSeconds)
{
    const UWorld* W = GetWorld();
    const double Now = W ? W->GetRealTimeSeconds() : 0.0;

    FVector Viewer;
    const bool bHaveViewer = bShowLabels && ViewerLocation(Viewer);

    TArray<FString> Stale;
    for (TPair<FString, FMAirTrafficAircraft>& Pair : Aircraft)
    {
        FMAirTrafficAircraft& One = Pair.Value;
        const float SinceReport = One.AgeAtSnapshot + static_cast<float>(Now - One.ReadAtTime);
        if (SinceReport > ForgetAfterSeconds)
        {
            Stale.Add(Pair.Key);
            continue;
        }
        if (!One.Mesh)
        {
            continue;
        }
        FVector Where = One.ReportedLocation;
        if (bDeadReckon)
        {
            Where += One.VelocityPerSecond * SinceReport;
        }
        One.Mesh->SetWorldLocationAndRotation(Where, FRotator(0.f, One.Yaw, 0.f));

        if (One.Label)
        {
            // The label sits above the aircraft and turns to face whoever is looking, because a
            // text component drawn edge on is an invisible text component.
            const FVector LabelAt = Where + FVector(0.f, 0.f, One.SpanMetres * 100.f * 0.45f);
            FRotator Facing(0.f, One.Yaw, 0.f);
            if (bHaveViewer)
            {
                Facing = (Viewer - LabelAt).Rotation();
                Facing.Pitch = 0.f;
                Facing.Roll = 0.f;
                Facing.Yaw += 180.f;        // text faces its own -X, so turn it around
            }
            One.Label->SetWorldLocationAndRotation(LabelAt, Facing);
            One.Label->SetVisibility(true);
        }
    }
    for (const FString& Address : Stale)
    {
        Forget(Address);
    }
}

UStaticMesh* AMAirTrafficActor::MeshFor(const FMAirTrafficAircraft& One) const
{
    if (const TSoftObjectPtr<UStaticMesh>* Assigned = ModelsByClass.Find(One.Class))
    {
        if (UStaticMesh* Mesh = Assigned->LoadSynchronous())
        {
            return Mesh;
        }
    }
    if (One.bOnGround || One.Class == FName(TEXT("vehicle")) || One.Class == FName(TEXT("obstacle")))
    {
        if (UStaticMesh* Mesh = GroundVehicleMesh.LoadSynchronous())
        {
            return Mesh;
        }
    }
    return FallbackMesh.LoadSynchronous();
}

void AMAirTrafficActor::Dress(FMAirTrafficAircraft& One)
{
    UStaticMesh* Mesh = MeshFor(One);
    if (!Mesh)
    {
        return;
    }

    // TRANSIENT, DELIBERATELY. These components are made while the level is open and must never
    // be written into it: an actor saved with forty aircraft attached would bake this afternoon's
    // traffic into the map for ever.
    UStaticMeshComponent* Component = NewObject<UStaticMeshComponent>(
        this, NAME_None, RF_Transient);
    Component->SetMobility(EComponentMobility::Movable);
    Component->SetupAttachment(RootComponent);
    Component->SetStaticMesh(Mesh);
    // Nothing should ever collide with or trace against these: they are a picture of traffic, and
    // a drone's own sensors must not see them as obstacles that are not there.
    Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Component->SetCanEverAffectNavigation(false);
    Component->bCastDynamicShadow = false;
    Component->RegisterComponent();

    if (bScaleToSpan)
    {
        // Make the model as wide as the aircraft it stands for, whatever size it was authored at.
        // FVector is double precision in UE5, so the extents and the floor have to agree on a
        // type before Max3 will take them.
        const FBoxSphereBounds Bounds = Mesh->GetBounds();
        const float Widest = static_cast<float>(
            FMath::Max3(Bounds.BoxExtent.X, Bounds.BoxExtent.Y, 1.0) * 2.0);
        const float Wanted = FMath::Max(1.f, One.SpanMetres) * 100.f;
        Component->SetWorldScale3D(FVector(Wanted / Widest * FMath::Max(0.1f, ExtraScale)));
    }
    else
    {
        Component->SetWorldScale3D(FVector(FMath::Max(0.1f, ExtraScale)));
    }
    One.Mesh = Component;

    if (bShowLabels)
    {
        UTextRenderComponent* Text = NewObject<UTextRenderComponent>(
            this, NAME_None, RF_Transient);
        Text->SetMobility(EComponentMobility::Movable);
        Text->SetupAttachment(RootComponent);
        Text->SetHorizontalAlignment(EHTA_Center);
        Text->SetWorldSize(FMath::Max(10.f, LabelSize));
        Text->SetTextRenderColor(FColor(255, 214, 92));
        Text->SetText(FText::FromString(FString::Printf(
            TEXT("%s\n%.0f m"),
            One.Callsign.IsEmpty() ? *One.Address : *One.Callsign,
            One.bOverLandscape ? One.HeightAboveGroundMetres : One.AltitudeMetres)));
        Text->RegisterComponent();
        One.Label = Text;
    }
}

void AMAirTrafficActor::Forget(const FString& Address)
{
    if (FMAirTrafficAircraft* One = Aircraft.Find(Address))
    {
        if (One->Mesh)
        {
            One->Mesh->DestroyComponent();
            One->Mesh = nullptr;
        }
        if (One->Label)
        {
            One->Label->DestroyComponent();
            One->Label = nullptr;
        }
        Aircraft.Remove(Address);
    }
}

bool AMAirTrafficActor::ViewerLocation(FVector& Out) const
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
