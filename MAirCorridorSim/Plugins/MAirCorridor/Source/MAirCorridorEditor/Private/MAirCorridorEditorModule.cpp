#include "MAirCorridorEditorModule.h"

#include "MAirLandscapeImporter.h"

#include "Modules/ModuleManager.h"
#include "ToolMenus.h"
#include "DesktopPlatformModule.h"
#include "IDesktopPlatform.h"
#include "Framework/Application/SlateApplication.h"
#include "Landscape.h"
#include "LandscapeProxy.h"
#include "Materials/Material.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialExpressionScalarParameter.h"
#include "Materials/MaterialExpressionConstant.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "Misc/MessageDialog.h"
#include "Misc/Paths.h"
#include "Editor.h"
#include "LevelEditorViewport.h"

#define LOCTEXT_NAMESPACE "MAirCorridorEditor"

IMPLEMENT_MODULE(FMAirCorridorEditorModule, MAirCorridorEditor)

namespace
{
    /** The imagery index written beside the tiles, in MAirCorridor_Assets beside the project
     *  (or MAIRCORRIDOR_ASSETS). Override the file itself with MAIRCORRIDOR_IMAGERY. */
    FString DefaultImageryIndex()
    {
        FString Assets = FPlatformMisc::GetEnvironmentVariable(TEXT("MAIRCORRIDOR_ASSETS"));
        if (Assets.IsEmpty())
        {
            Assets = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("../MAirCorridor_Assets"));
        }
        return Assets / TEXT("naip_rect_066m/mcity_066m_naip.json");
    }

    void Tell(const FString& Message, bool bError)
    {
        // UE_LOG pastes its second argument onto ELogVerbosity::, so the verbosity has to be a
        // literal token here - a ternary does not compile.
        if (bError)
        {
            UE_LOG(LogTemp, Error, TEXT("[MAirCorridor] %s"), *Message);
        }
        else
        {
            UE_LOG(LogTemp, Log, TEXT("[MAirCorridor] %s"), *Message);
        }
        FMessageDialog::Open(EAppMsgType::Ok, FText::FromString(Message));
    }
}

void FMAirCorridorEditorModule::ImportLandscapePlan()
{
    IDesktopPlatform* Desktop = FDesktopPlatformModule::Get();
    if (!Desktop)
    {
        return;
    }
    TArray<FString> Picked;
    const void* Parent = FSlateApplication::Get().FindBestParentWindowHandleForDialogs(nullptr);
    if (!Desktop->OpenFileDialog(Parent,
            TEXT("Choose a landscape plan (the .json beside the .r16 heightmap)"),
            FPaths::ProjectDir(), TEXT(""), TEXT("Landscape plan (*.json)|*.json"),
            EFileDialogFlags::None, Picked) || Picked.Num() == 0)
    {
        return;
    }

    MAirLandscapeImporter::FPlan Plan;
    FString Error;
    if (!MAirLandscapeImporter::LoadPlan(Picked[0], Plan, Error))
    {
        // REFUSED BEFORE ANYTHING IS SPAWNED. A plan that does not describe a legal landscape would
        // otherwise produce an actor that exists, reports success, and is the wrong size.
        Tell(FString::Printf(TEXT("landscape plan rejected: %s"), *Error), true);
        return;
    }

    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!World)
    {
        Tell(TEXT("no editor world to build into"), true);
        return;
    }

    const int32 Expected = Plan.Segments.Num() ? Plan.Segments.Num() : 1;
    TArray<ALandscape*> Built;
    const int32 Made = MAirLandscapeImporter::ImportPlan(World, Plan, Built, Error);
    if (Made != Expected)
    {
        Tell(FString::Printf(TEXT("built %d of %d landscape(s), then stopped: %s"),
                             Made, Expected, *Error), true);
        return;
    }

    const int64 Total = Plan.Cells1m + Plan.Cells19Resampled + Plan.CellsNodata;
    FString Prov;
    if (Total > 0)
    {
        Prov = FString::Printf(TEXT(", %.1f%% at 1 m, %.1f%% resampled, %.1f%% nodata"),
                               100.0 * Plan.Cells1m / Total,
                               100.0 * Plan.Cells19Resampled / Total,
                               100.0 * Plan.CellsNodata / Total);
    }
    Tell(FString::Printf(TEXT("built %d landscape(s) from %s (%.0f m per quad%s)"),
                         Made, *FPaths::GetCleanFilename(Picked[0]),
                         Plan.QuadMetres, *Prov), false);
}

/* THE IMAGERY SCALE, SET FROM THE DATA RATHER THAN TYPED.
 *
 * The drape material addresses the photography by world position: UV = (WorldXY - UVOrigin) * UVScale,
 * and one UDIM tile must span exactly one UV unit.
 *
 * THE UNITS ARE READ FROM THE GRAPH, NOT ASSUMED, and that is the whole lesson of this function.
 * Unreal works in centimetres, so the obvious formula is 1 / (tile_px * metres_per_pixel * 100).
 * This material is not built that way: it multiplies world position by a constant 0.01 first, so
 * its scale is per METRE and the 100 must not be there. Assuming otherwise divided a correct
 * material by a hundred and smeared the imagery across the terrain.
 *
 * So the graph is inspected for that conversion constant and the formula follows it.
 */
void FMAirCorridorEditorModule::FixImageryScale()
{
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!World)
    {
        Tell(TEXT("no editor world"), true);
        return;
    }

    // The index that was written beside the imagery tiles.
    FString IndexPath = FPlatformMisc::GetEnvironmentVariable(TEXT("MAIRCORRIDOR_IMAGERY"));
    if (IndexPath.IsEmpty())
    {
        IndexPath = DefaultImageryIndex();
    }
    if (!FPaths::FileExists(IndexPath))
    {
        IDesktopPlatform* Desktop = FDesktopPlatformModule::Get();
        TArray<FString> Picked;
        if (!Desktop || !Desktop->OpenFileDialog(
                FSlateApplication::Get().FindBestParentWindowHandleForDialogs(nullptr),
                TEXT("Choose the imagery index written beside the tiles"), FPaths::ProjectDir(),
                TEXT(""), TEXT("Imagery index (*.json)|*.json"), EFileDialogFlags::None, Picked)
            || Picked.Num() == 0)
        {
            return;
        }
        IndexPath = Picked[0];
    }

    FString Text;
    TSharedPtr<FJsonObject> Root;
    if (!FFileHelper::LoadFileToString(Text, *IndexPath) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
    {
        Tell(FString::Printf(TEXT("cannot read %s"), *IndexPath), true);
        return;
    }
    double TilePx = 0.0, MetresPerPixel = 0.0;
    if (!Root->TryGetNumberField(TEXT("tile_px"), TilePx) ||
        !Root->TryGetNumberField(TEXT("metres_per_pixel"), MetresPerPixel) ||
        TilePx <= 0.0 || MetresPerPixel <= 0.0)
    {
        Tell(FString::Printf(TEXT("%s has no usable tile_px / metres_per_pixel"), *IndexPath), true);
        return;
    }

    ALandscape* Landscape = nullptr;
    for (TActorIterator<ALandscape> It(World); It; ++It) { Landscape = *It; break; }
    if (!Landscape || !Landscape->LandscapeMaterial)
    {
        Tell(TEXT("no Landscape with a material in this level, so there is nothing to correct."), true);
        return;
    }
    UMaterial* Mat = Landscape->LandscapeMaterial->GetMaterial();
    if (!Mat)
    {
        Tell(TEXT("the Landscape's material has no base material."), true);
        return;
    }

    /* Does the graph convert world position to metres before the scale? A constant 0.01 feeding a
     * multiply is how that is done, and its presence decides the units of both parameters. */
    bool bMetres = false;
    for (UMaterialExpression* Expression : Mat->GetExpressions())
    {
        if (const UMaterialExpressionConstant* C = Cast<UMaterialExpressionConstant>(Expression))
        {
            bMetres |= FMath::IsNearlyEqual(C->R, 0.01f, 1.e-6f);
        }
    }
    const double UnitsPerMetre = bMetres ? 1.0 : 100.0;
    const double Scale = 1.0 / (TilePx * MetresPerPixel * UnitsPerMetre);
    const FVector Corner = Landscape->GetActorLocation() * (bMetres ? 0.01 : 1.0);

    TMap<FName, double> Wanted;
    Wanted.Add(TEXT("UVScaleX"), Scale);
    Wanted.Add(TEXT("UVScaleY"), Scale);
    Wanted.Add(TEXT("UVOriginX"), Corner.X);
    Wanted.Add(TEXT("UVOriginY"), Corner.Y);

    FString Report;
    int32 Changed = 0, Found = 0;
    for (UMaterialExpression* Expression : Mat->GetExpressions())
    {
        UMaterialExpressionScalarParameter* Param = Cast<UMaterialExpressionScalarParameter>(Expression);
        const double* Want = Param ? Wanted.Find(Param->ParameterName) : nullptr;
        if (!Want)
        {
            continue;
        }
        ++Found;
        const float Old = Param->DefaultValue;
        const float New = static_cast<float>(*Want);
        Report += FString::Printf(TEXT("%s%s  %.10g  ->  %.10g%s"), LINE_TERMINATOR,
                                  *Param->ParameterName.ToString(), Old, New,
                                  FMath::IsNearlyEqual(Old, New) ? TEXT("   (unchanged)") : TEXT(""));
        if (!FMath::IsNearlyEqual(Old, New))
        {
            if (Changed == 0)
            {
                Mat->Modify();          // only once, and only if something really changes
            }
            Param->DefaultValue = New;
            ++Changed;
        }
    }

    if (Found == 0)
    {
        Tell(FString::Printf(TEXT("'%s' has no UVScaleX / UVScaleY / UVOriginX / UVOriginY "
                                  "parameters, so it is not the imagery material this corrects."),
                             *Mat->GetName()), true);
        return;
    }

    /* RECOMPILE ONLY IF SOMETHING CHANGED. PostEditChange on a material invalidates its cached
     * virtual texture pages, so the terrain drops to its coarsest mip and looks smeared until they
     * stream back. Doing that to report "nothing to do" is a lot of blur for no reason. */
    if (Changed > 0)
    {
        Mat->PostEditChange();
        Mat->MarkPackageDirty();
    }
    UE_LOG(LogTemp, Display, TEXT("[MAirCorridor] %s from %s: %s"), *Mat->GetName(), *IndexPath, *Report);

    Tell(FString::Printf(
        TEXT("Imagery material '%s' corrected from %s.\n\n")
        TEXT("%.0f px tiles at %.4g m per pixel, so one tile is %.0f %s across and "
             "UVScale = 1 / that = %.10g.\n\n")
        TEXT("%s\n\n")
        TEXT("%s"),
        *Mat->GetName(), *FPaths::GetCleanFilename(IndexPath), TilePx, MetresPerPixel,
        TilePx * MetresPerPixel * UnitsPerMetre, bMetres ? TEXT("metres (the graph converts)")
                                                        : TEXT("centimetres"),
        Scale, *Report.TrimStart(),
        Changed > 0 ? *FString::Printf(TEXT("%d parameter(s) changed. SAVE the material to keep it."), Changed)
                    : TEXT("Everything already matched, so the material was left untouched.")), false);
}

void FMAirCorridorEditorModule::GoToScan()
{
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!World)
    {
        return;
    }
    /* FIND IT BY COMPONENT, not by class name. The scan is whatever actor carries the streaming
     * component, so this keeps working if it is renamed or put on a different actor. */
    AActor* Found = nullptr;
    FBox Bounds(ForceInit);
    for (TActorIterator<AActor> It(World); It; ++It)
    {
        for (const UActorComponent* C : It->GetComponents())
        {
            if (C && C->GetClass()->GetName().Contains(TEXT("MAirScanMeshComponent")))
            {
                Found = *It;
                Bounds = It->GetComponentsBoundingBox(true);
                break;
            }
        }
        if (Found)
        {
            break;
        }
    }
    if (!Found)
    {
        Tell(TEXT("There is no scan actor in this level. Drag an M-City Scan in from the Place "
                  "Actors panel, or load the World Partition region that holds it."), true);
        return;
    }

    GEditor->SelectNone(false, true);
    GEditor->SelectActor(Found, true, true);

    /* DRIVE THE CAMERA, DO NOT ASK IT TO FOCUS THE ACTOR. The scan actor sits at the origin and the
     * geometry hangs off it at its surveyed offset, so focusing the actor can frame 0,0,0 and show
     * empty sky. The streamed sections give a real bounding box; fly to the middle of that, high
     * enough to see all of it, looking down. */
    if (!Bounds.IsValid || Bounds.GetSize().IsNearlyZero())
    {
        Tell(TEXT("The scan actor is here but has no geometry loaded yet, so there is nothing to fly "
                  "to. Give it a moment to stream, then try again."), true);
        return;
    }
    const FVector Centre = Bounds.GetCenter();
    const double Span = FMath::Max(Bounds.GetSize().X, Bounds.GetSize().Y);
    const FVector Eye(Centre.X, Centre.Y - Span * 0.6, Centre.Z + Span * 0.6);
    for (FLevelEditorViewportClient* Client : GEditor->GetLevelViewportClients())
    {
        if (Client)
        {
            Client->SetViewLocation(Eye);
            Client->SetViewRotation((Centre - Eye).Rotation());
            Client->Invalidate();
        }
    }
    const FVector C = Bounds.GetCenter();
    UE_LOG(LogTemp, Display,
           TEXT("[MAirCorridor] scan '%s' is at X %.0f Y %.0f Z %.0f, %.0f x %.0f m"),
           *Found->GetActorNameOrLabel(), C.X, C.Y, C.Z,
           Bounds.GetSize().X / 100.0, Bounds.GetSize().Y / 100.0);
}

void FMAirCorridorEditorModule::RegisterMenus()
{
    FToolMenuOwnerScoped Owner(this);
    UToolMenu* Tools = UToolMenus::Get()->ExtendMenu("LevelEditor.MainMenu.Tools");
    if (!Tools)
    {
        return;
    }

    // ITS OWN SECTION, under its own name. Another plugin extending the same menu gets its own, and
    // the two do not merge into an unattributable pile of entries.
    FToolMenuSection& Section =
        Tools->AddSection("MAirCorridor", LOCTEXT("MAirSection", "M-Air Corridor"));

    auto Add = [&Section](const TCHAR* Id, const FText& Label, const FText& Tip,
                          TFunction<void()> Fn)
    {
        Section.AddMenuEntry(FName(Id), Label, Tip, FSlateIcon(),
                             FUIAction(FExecuteAction::CreateLambda(MoveTemp(Fn))));
    };

    Add(TEXT("MAirImportLandscape"),
        LOCTEXT("ImportLandscape", "Build Unreal Landscape from Plan..."),
        LOCTEXT("ImportLandscapeTip",
                "Pick the .json beside a prepared .r16 heightmap and build the Landscape actor(s) it "
                "describes - resolution, section size, components, scale, Z placement and World "
                "Partition grid all come from the file. This is how a DSM far too large for Unreal's "
                "own import becomes terrain: the oversized source is never opened by the editor. "
                "Unreal owns the terrain from here; nothing is voxelised or streamed by us."),
        [this]() { ImportLandscapePlan(); });

    Add(TEXT("MAirGoToScan"),
        LOCTEXT("GoToScan", "Go to the M-City Scan"),
        LOCTEXT("GoToScanTip",
                "Select the scan actor and put the camera on it. The scan is 1.6 km across in a 65 km "
                "world, so flying to it by eye mostly means flying past it."),
        [this]() { GoToScan(); });

    Add(TEXT("MAirImageryScale"),
        LOCTEXT("ImageryScale", "Fix Imagery Scale from Index"),
        LOCTEXT("ImageryScaleTip",
                "Set the landscape imagery material's UVScale and UVOrigin from the index written "
                "beside the imagery tiles. The scale is 1 / (tile pixels x metres per pixel x 100), "
                "and the 100 is Unreal's centimetres: computing it per metre leaves the photography "
                "sliding across the terrain as you move away from the origin. Too precise to type, "
                "so it is written straight into the material."),
        [this]() { FixImageryScale(); });

    Add(TEXT("MAirPlaceFoliage"),
        LOCTEXT("PlaceFoliage", "Place Corridor Trees and Rocks"),
        LOCTEXT("PlaceFoliageTip",
                "Import the generated tree and rock library and place it: the SURVEYED trees exactly "
                "where the OSM data records them, and a scatter inside the wood, scrub, park and "
                "grass polygons at per-layer densities. Every instance is traced onto the Landscape, "
                "which is the only surface treated as ground: nothing is planted on a building roof, "
                "and a point under a crown already placed is skipped, which thins the scatter."),
        [this]() { PlaceCorridorFoliage(); });

    RegisteredMenus.Add("LevelEditor.MainMenu.Tools");
}

void FMAirCorridorEditorModule::StartupModule()
{
    UToolMenus::RegisterStartupCallback(
        FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FMAirCorridorEditorModule::RegisterMenus));
}

void FMAirCorridorEditorModule::ShutdownModule()
{
    UToolMenus::UnRegisterStartupCallback(this);
    UToolMenus::UnregisterOwner(this);
}

#undef LOCTEXT_NAMESPACE
