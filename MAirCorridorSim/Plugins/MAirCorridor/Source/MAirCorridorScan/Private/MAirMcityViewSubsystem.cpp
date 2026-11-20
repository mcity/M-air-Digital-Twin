// MAirMcityViewSubsystem.cpp - see MAirMcityViewSubsystem.h.
#include "MAirMcityViewSubsystem.h"

#include "MAirScanActor.h"
#include "MAirScanMeshComponent.h"

#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/Level.h"
#include "Engine/LevelStreaming.h"
#include "Engine/LevelStreamingDynamic.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerStart.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "Lightmass/LightmassImportanceVolume.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

DEFINE_LOG_CATEGORY_STATIC(LogMAirMcity, Log, All);

namespace
{
	// The twin's main map, as the McityMap plugin mounts it.
	const TCHAR* TwinMainMap = TEXT("/McityMap/McityMap_Main");

	// The scan imported whole as a Nanite mesh (Tools/unreal/place_scan_mesh.py's MESH).
	const TCHAR* ScanMeshPath = TEXT("/MAirCorridor/Scan/20M16.");

	// The corridor's own buildings and trees under one M-City only (see the header).
	const FName UnderScanTag(TEXT("MAirUnderScan"));
	const FName UnderTwinTag(TEXT("MAirUnderTwin"));

	// Its frame onto this level's (see the header): fitted, worst residual 0.08 cm.
	const FVector TwinOffsetCm(959207.9, 1089057.1, -23599.85);
	constexpr double TwinYawDeg = -88.1826;

	// Sublevels the twin carries that are not the place itself: its own lighting, a splash screen,
	// and a level its authors marked for removal.
	bool IsSkippedSublevel(const FString& Name)
	{
		return Name.Contains(TEXT("Lighting")) || Name.Contains(TEXT("UnrealLights")) || Name.Contains(TEXT("SplashScreen"))
			|| Name.Contains(TEXT("TO_REMOVE"));
	}

	bool ParseView(const FString& Text, EMAirMcityView& Out)
	{
		if (Text.Equals(TEXT("twin"), ESearchCase::IgnoreCase) || Text.Equals(TEXT("digitaltwin"), ESearchCase::IgnoreCase))
		{
			Out = EMAirMcityView::Twin;
			return true;
		}
		if (Text.Equals(TEXT("scan"), ESearchCase::IgnoreCase))
		{
			Out = EMAirMcityView::Scan;
			return true;
		}
		return false;
	}

	FAutoConsoleCommandWithWorldAndArgs McityViewCommand(
		TEXT("mair.McityView"),
		TEXT("Show M-City as the photogrammetric scan or the Mcity digital twin: mair.McityView Scan | Twin | Toggle"),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			UMAirMcityViewSubsystem* S = World ? World->GetSubsystem<UMAirMcityViewSubsystem>() : nullptr;
			if (!S)
			{
				UE_LOG(LogMAirMcity, Warning, TEXT("[MAirMcity] only in Play or a game"));
				return;
			}
			EMAirMcityView V = S->GetView() == EMAirMcityView::Scan ? EMAirMcityView::Twin : EMAirMcityView::Scan;
			if (Args.Num() > 0 && !Args[0].Equals(TEXT("toggle"), ESearchCase::IgnoreCase) && !ParseView(Args[0], V))
			{
				UE_LOG(LogMAirMcity, Warning, TEXT("[MAirMcity] '%s': give Scan, Twin or Toggle"), *Args[0]);
				return;
			}
			S->SetView(V);
		}));
}

bool UMAirMcityViewSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UMAirMcityViewSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UMAirMcityViewSubsystem, STATGROUP_Tickables);
}

void UMAirMcityViewSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	bBegun = true;
	// Whatever the request file says now was for an earlier session; only a change is acted on.
	FFileHelper::LoadFileToString(LastRequest, *FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("MAirCorridor"), TEXT("mcity_view.json")));
	FString Arg;
	EMAirMcityView Start = EMAirMcityView::Scan;
	if (FParse::Value(FCommandLine::Get(), TEXT("MAirMcityView="), Arg) && ParseView(Arg, Start))
	{
		UE_LOG(LogMAirMcity, Display, TEXT("[MAirMcity] -MAirMcityView=%s"), *Arg);
	}
	Current = EMAirMcityView::Scan;
	LevelAddedHandle = FWorldDelegates::LevelAddedToWorld.AddUObject(this, &UMAirMcityViewSubsystem::OnLevelAdded);
	if (Start == EMAirMcityView::Twin)
	{
		SetView(EMAirMcityView::Twin);
	}
	else
	{
		ApplyUnderTags();
	}
}

void UMAirMcityViewSubsystem::Deinitialize()
{
	FWorldDelegates::LevelAddedToWorld.Remove(LevelAddedHandle);
	TwinLevels.Reset();
	Super::Deinitialize();
}

void UMAirMcityViewSubsystem::OnLevelAdded(ULevel* Level, UWorld* World)
{
	if (World == GetWorld() && Level)
	{
		ApplyUnderTags(Level);
	}
}

void UMAirMcityViewSubsystem::ApplyUnderTags(ULevel* Only)
{
	int32 Hidden = 0, Shown = 0;
	auto Apply = [this, &Hidden, &Shown](AActor* A)
	{
		if (!A)
		{
			return;
		}
		const bool bUnderScan = A->ActorHasTag(UnderScanTag);
		const bool bUnderTwin = A->ActorHasTag(UnderTwinTag);
		if (!bUnderScan && !bUnderTwin)
		{
			return;
		}
		const bool bHide = (bUnderScan && Current == EMAirMcityView::Scan) || (bUnderTwin && Current == EMAirMcityView::Twin);
		A->SetActorHiddenInGame(bHide);
		A->SetActorEnableCollision(!bHide);
		++(bHide ? Hidden : Shown);
	};
	if (Only)
	{
		for (AActor* A : Only->Actors)
		{
			Apply(A);
		}
	}
	else if (UWorld* World = GetWorld())
	{
		for (TActorIterator<AActor> It(World); It; ++It)
		{
			Apply(*It);
		}
	}
	if (Hidden + Shown > 0)
	{
		UE_LOG(LogMAirMcity, Log, TEXT("[MAirMcity] under M-City%s%s: %d hidden, %d shown"), Only ? TEXT(", streamed in ") : TEXT(""),
			Only ? *Only->GetOuter()->GetName() : TEXT(""), Hidden, Shown);
	}
}

void UMAirMcityViewSubsystem::Tick(float DeltaTime)
{
	if (!bBegun)
	{
		return;
	}
	if (Current == EMAirMcityView::Twin)
	{
		StripTwinEnvironment();
	}
	const double Now = FPlatformTime::Seconds();
	if (Now >= NextPoll)
	{
		NextPoll = Now + 1.0;
		PollRequestFile();
	}
}

void UMAirMcityViewSubsystem::PollRequestFile()
{
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("MAirCorridor"), TEXT("mcity_view.json")))
		|| Text == LastRequest)
	{
		return;
	}
	LastRequest = Text;
	TSharedPtr<FJsonObject> J;
	FString ViewText;
	EMAirMcityView V = EMAirMcityView::Scan;
	if (FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), J) && J.IsValid()
		&& J->TryGetStringField(TEXT("view"), ViewText) && ParseView(ViewText, V))
	{
		SetView(V);
	}
}

void UMAirMcityViewSubsystem::SetView(EMAirMcityView View)
{
	if (View == Current && (View == EMAirMcityView::Scan || TwinLevels.Num() > 0))
	{
		return;
	}
	Current = View;
	if (View == EMAirMcityView::Twin)
	{
		ShowScan(false);
		LoadTwin();
	}
	else
	{
		UnloadTwin();
		ShowScan(true);
	}
	ApplyUnderTags();
	UE_LOG(LogMAirMcity, Display, TEXT("[MAirMcity] M-City is now the %s"), View == EMAirMcityView::Twin ? TEXT("digital twin") : TEXT("scan"));
}

void UMAirMcityViewSubsystem::ShowScan(bool bShow)
{
	int32 Found = 0;
	for (TActorIterator<AMAirScanActor> It(GetWorld()); It; ++It)
	{
		It->SetActorHiddenInGame(!bShow);
		It->SetActorEnableCollision(bShow);
		if (It->Scan)
		{
			// Hidden, it need not keep streaming tiles in around the viewer either.
			It->Scan->SetComponentTickEnabled(bShow);
		}
		++Found;
	}
	// The scan as one Nanite mesh (Tools/unreal/place_scan_mesh.py), which took the streamed actor's
	// place in the corridor level: an ordinary static mesh actor, known by its mesh.
	for (TActorIterator<AStaticMeshActor> It(GetWorld()); It; ++It)
	{
		const UStaticMeshComponent* C = It->GetStaticMeshComponent();
		const UStaticMesh* Mesh = C ? C->GetStaticMesh() : nullptr;
		if (Mesh && Mesh->GetPathName().StartsWith(ScanMeshPath))
		{
			It->SetActorHiddenInGame(!bShow);
			It->SetActorEnableCollision(bShow);
			++Found;
		}
	}
	if (Found == 0)
	{
		UE_LOG(LogMAirMcity, Warning, TEXT("[MAirMcity] no scan in this level to %s"), bShow ? TEXT("show") : TEXT("hide"));
	}
}

void UMAirMcityViewSubsystem::LoadTwin()
{
	UWorld* World = GetWorld();
	if (!World || TwinLevels.Num() > 0)
	{
		return;
	}
	const FTransform Where(FRotator(0.0, TwinYawDeg, 0.0), TwinOffsetCm);

	// The main map, then every sublevel it streams, each as an instance at the same transform: an
	// instanced level does not bring its own sublevels with it.
	TArray<FString> Packages = { TwinMainMap };
	if (UWorld* Main = LoadObject<UWorld>(nullptr, *FString::Printf(TEXT("%s.%s"), TwinMainMap, *FPaths::GetBaseFilename(TwinMainMap))))
	{
		for (ULevelStreaming* L : Main->GetStreamingLevels())
		{
			if (!L)
			{
				continue;
			}
			FString Name = L->GetWorldAssetPackageName();
			Name.ReplaceInline(TEXT("/Game/McityMap"), TEXT("/McityMap"));   // the plugin's redirect, by hand
			if (!IsSkippedSublevel(Name))
			{
				Packages.AddUnique(Name);
			}
		}
	}
	else
	{
		UE_LOG(LogMAirMcity, Error, TEXT("[MAirMcity] the twin is not installed: no %s (the McityMap plugin)"), TwinMainMap);
		return;
	}

	if (Packages.Num() == 1)
	{
		// At runtime the map loaded only for its list may come back without it; these are the
		// sublevels McityMap 1.9.1's main map streams (from the map file itself), less the skipped.
		for (const TCHAR* Sub : { TEXT("McityMap_Terrain"), TEXT("McityMap_StaticProps"), TEXT("McityMap_OpenDrive"),
			TEXT("McityMap_StreetLights"), TEXT("McityMap_UECableActors"), TEXT("CarlaSigns"), TEXT("CarlaTrafficLights") })
		{
			Packages.Add(FString::Printf(TEXT("/McityMap/Sublevels/%s"), Sub));
		}
	}

	for (const FString& Package : Packages)
	{
		bool bOk = false;
		ULevelStreamingDynamic::FLoadLevelInstanceParams Params(World, Package, Where);
		Params.OptionalLevelNameOverride = nullptr;
		ULevelStreamingDynamic* L = ULevelStreamingDynamic::LoadLevelInstance(Params, bOk);
		if (bOk && L)
		{
			TwinLevels.Add(L);
		}
		UE_LOG(LogMAirMcity, Display, TEXT("[MAirMcity] %s %s"), bOk ? TEXT("loading") : TEXT("could not load"), *Package);
	}
	Stripped.Reset();
}

void UMAirMcityViewSubsystem::UnloadTwin()
{
	for (ULevelStreamingDynamic* L : TwinLevels)
	{
		if (L)
		{
			L->SetShouldBeVisible(false);
			L->SetShouldBeLoaded(false);
			L->SetIsRequestingUnloadAndRemoval(true);
		}
	}
	TwinLevels.Reset();
	Stripped.Reset();
}

void UMAirMcityViewSubsystem::StripTwinEnvironment()
{
	for (ULevelStreamingDynamic* L : TwinLevels)
	{
		ULevel* Level = L ? L->GetLoadedLevel() : nullptr;
		if (!Level || Stripped.Contains(L->GetFName()))
		{
			continue;
		}
		Stripped.Add(L->GetFName());
		int32 Removed = 0;
		for (AActor* A : Level->Actors)
		{
			if (A && (A->IsA<ADirectionalLight>() || A->IsA<ASkyLight>() || A->IsA<AExponentialHeightFog>()
				|| A->IsA<APostProcessVolume>() || A->IsA<ALightmassImportanceVolume>() || A->IsA<APlayerStart>()
				|| A->GetClass()->GetName().Contains(TEXT("SkyAtmosphere")) || A->GetClass()->GetName().Contains(TEXT("VolumetricCloud"))
				|| A->GetClass()->GetName().Contains(TEXT("BP_Sky"))))
			{
				A->Destroy();
				++Removed;
			}
		}
		// Where it landed, for checking the placement against the landscape.
		FBox Bounds(ForceInit);
		for (AActor* A : Level->Actors)
		{
			if (A && !A->IsPendingKillPending() && A->GetRootComponent())
			{
				const FBox B = A->GetComponentsBoundingBox(true);
				if (B.IsValid && B.GetExtent().GetMax() < 1.0e6)
				{
					Bounds += B;
				}
			}
		}
		UE_LOG(LogMAirMcity, Display, TEXT("[MAirMcity] %s loaded: %d actors, %d of its own lights/sky/fog removed; bounds %s"),
			*L->GetWorldAssetPackageName(), Level->Actors.Num(), Removed, Bounds.IsValid ? *Bounds.ToString() : TEXT("none"));
	}
}
