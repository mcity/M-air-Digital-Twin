// MAirMcityViewSubsystem.h - M-City as the photogrammetric scan, or as the Mcity digital twin.
//
// Two representations of the same 1.6 km of ground: the scan (in the corridor level, the Nanite
// static mesh actor "M-City Scan (Nanite)" that Tools/unreal/place_scan_mesh.py put in place of the
// AMAirScanActor streamed from survey tiles; either is switched) and the digital twin (Mcity's authored McityMap level, github.com/mcity/M-Air-Digital-Twin,
// installed as the McityMap plugin at /McityMap). One is shown at a time.
//
// SWITCHING. In Play and in a packaged game, any of:
//   mair.McityView Scan | Twin | Toggle          the console
//   -MAirMcityView=Twin                          the command line, for the start
//   Saved/MAirCorridor/mcity_view.json           {"view": "twin"}, which the flight tools write
// The default is the scan, which is what the level showed before the twin existed.
//
// PLACING THE TWIN. Its level is geo-anchored: UE origin at lat 42.3005934157, lon -83.69928318881136
// (its OpenDRIVE geoReference, a transverse Mercator there), +X true north, +Y true east, Z sea-level
// elevation in centimetres. This level is UTM 17N measured from the landscape's north-west corner,
// with Z 0 at 235.998497 m. Fitted over the twin's extent, the twin goes in with a yaw of -88.1826
// deg (UTM grid convergence plus the axis turn) and a translation of (959207.9, 1089057.1, -23599.85)
// cm: worst residual 0.08 cm. UTM's scale factor here, 1.0002, is left out (a level cannot be
// scaled): at most 5 cm at the twin's far edge.
//
// The twin's main map is a persistent level with sublevels; each is loaded as a level instance at the
// same transform. The lights, sky, fog and post process the twin brings are removed once loaded, so the
// corridor keeps its one sun.
//
// WHAT IS UNDER THEM. The corridor has its own buildings and trees, from OpenStreetMap and the foliage
// placer, where the scan and the twin now stand. Those under both were deleted; those under one only
// are tagged (Tools/unreal/mcity_clear_level.py): an actor tagged MAirUnderScan is hidden, and does
// not collide, while the scan is shown, and one tagged MAirUnderTwin while the twin is. Applied at the
// start, on every switch, and to each level World Partition streams in after.
#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "MAirMcityViewSubsystem.generated.h"

class ULevelStreamingDynamic;

UENUM()
enum class EMAirMcityView : uint8
{
	Scan,
	Twin,
};

UCLASS()
class MAIRCORRIDORSCAN_API UMAirMcityViewSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

	/** Show the scan or the twin. */
	void SetView(EMAirMcityView View);
	EMAirMcityView GetView() const { return Current; }

private:
	void ShowScan(bool bShow);
	void LoadTwin();
	void UnloadTwin();
	void StripTwinEnvironment();
	void PollRequestFile();
	/** Hide what is under the M-City being shown, and show what is under the other: in one level, or all. */
	void ApplyUnderTags(ULevel* Only = nullptr);
	void OnLevelAdded(ULevel* Level, UWorld* World);

	EMAirMcityView Current = EMAirMcityView::Scan;
	bool bBegun = false;
	FDelegateHandle LevelAddedHandle;
	double NextPoll = 0.0;
	FString LastRequest;

	UPROPERTY(Transient)
	TArray<TObjectPtr<ULevelStreamingDynamic>> TwinLevels;
	TSet<FName> Stripped;
};
