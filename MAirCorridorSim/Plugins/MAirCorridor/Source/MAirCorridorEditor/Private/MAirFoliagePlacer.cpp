/*
 * MAirFoliagePlacer.cpp - put the generated trees and rocks on the corridor.
 *
 * The tree library comes from friggog/tree-gen and the rocks from a vertex-coloured generator;
 * see the Credits section of the repository README.
 *
 * WHAT IT READS. corridor_scene.json (extract_scene_features.py) carries the OSM survey in
 * landscape coordinates: 6,893 individual TREES with real recorded positions, plus wood, scrub,
 * grass and park POLYGONS to scatter inside. trees.json and rocks.json describe the generated
 * library - which mesh, how tall, what real-world size a rock of that type should be.
 *
 * A SURVEYED TREE IS NOT A SCATTER POINT. natural=tree is a tree somebody stood next to and
 * recorded; those are placed exactly where the data says, and where the survey names a genus that
 * beats any species roll. Scattering is for polygons, where the data says "wood here" without
 * saying which stems - so the two paths are separate and only the second is random.
 *
 * INSTANCED, AND HERE IT ACTUALLY PAYS. The buildings could not benefit: 73,404 unique meshes are
 * 73,404 batches however they are grouped. Trees and rocks are the opposite - a library of 72
 * meshes repeated hundreds of thousands of times - which is exactly what a hierarchical instanced
 * component is for. One component per mesh, every placement an instance in it.
 *
 * HEIGHT IS TRACED, NEVER CARRIED. Same rule as the buildings and for the same reason: the OSM
 * survey has no Z that means anything against this Landscape. Every instance is dropped from
 * above and put where it lands ON THE LANDSCAPE, which is the only thing treated as ground.
 *
 * WHAT IS ALREADY STANDING DECIDES WHETHER TO PLANT. A point under a building roof is refused
 * outright, and a point under a crown this run has already placed is refused too, which thins the
 * scatter instead of stacking trees on each other. A surveyed tree overrides the canopy rule,
 * because the survey records a real tree standing at that spot.
 */
#include "MAirCorridorEditorModule.h"

#include "AssetToolsModule.h"
#include "AssetImportTask.h"
#include "Factories/FbxImportUI.h"
#include "Factories/FbxStaticMeshImportData.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AutomatedAssetImportData.h"
#include "Materials/MaterialInterface.h"
#include "Engine/StaticMesh.h"
#include "Misc/ScopeExit.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "DesktopPlatformModule.h"
#include "Dom/JsonObject.h"
#include "Editor.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Framework/Application/SlateApplication.h"
#include "IDesktopPlatform.h"
#include "Interfaces/IPluginManager.h"
#include "Landscape.h"
#include "LandscapeProxy.h"
#include "LandscapeHeightfieldCollisionComponent.h"
#include "LandscapeComponent.h"
#include "LandscapeDataAccess.h"
#include "LandscapeInfo.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/MessageDialog.h"
#include "Misc/Paths.h"
#include "Misc/ScopedSlowTask.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

#define LOCTEXT_NAMESPACE "MAirCorridorEditor"

namespace
{
    /* THE THREE INPUTS, FIXED. They have been the same files for months, so the tool opens them
     * rather than asking for them three times a run. A dialog appears only for one that is NOT
     * there, and each can be overridden with an environment variable without touching this file:
     *
     *     MAIRCORRIDOR_SCENE   MAIRCORRIDOR_TREES   MAIRCORRIDOR_ROCKS
     *
     * They are in MAirCorridor_Assets beside the project, or wherever MAIRCORRIDOR_ASSETS says.
     */
    FString AssetsDir()
    {
        FString Assets = FPlatformMisc::GetEnvironmentVariable(TEXT("MAIRCORRIDOR_ASSETS"));
        if (Assets.IsEmpty())
        {
            Assets = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("../MAirCorridor_Assets"));
        }
        return Assets;
    }
    FString DefaultSceneJson() { return AssetsDir() / TEXT("corridor_scene.json"); }
    FString DefaultTreeDir()   { return AssetsDir() / TEXT("corridor_trees"); }
    FString DefaultRockDir()   { return AssetsDir() / TEXT("corridor_rocks"); }

    /** An environment override, the fixed path, or empty when neither is on disk. */
    FString FixedInput(const TCHAR* EnvVar, const FString& Fallback, bool bDirectory)
    {
        FString Path = FPlatformMisc::GetEnvironmentVariable(EnvVar);
        if (Path.IsEmpty())
        {
            Path = Fallback;
        }
        FPaths::NormalizeFilename(Path);
        const bool bThere = bDirectory ? FPaths::DirectoryExists(Path) : FPaths::FileExists(Path);
        return bThere ? Path : FString();
    }

    // Not "Tell": MAirCorridorEditorModule.cpp has its own, and a unity build puts both files in
    // one translation unit, where two anonymous-namespace functions of one name collide.
    void TellFoliage(const FString& Message, bool bError)
    {
        // UE_LOG pastes its second argument onto ELogVerbosity::, so the verbosity has to be a
        // literal token here - a ternary does not compile.
        if (bError)
        {
            UE_LOG(LogTemp, Error, TEXT("[MAirCorridor] %s"), *Message);
        }
        else
        {
            UE_LOG(LogTemp, Display, TEXT("[MAirCorridor] %s"), *Message);
        }
        FMessageDialog::Open(EAppMsgType::Ok, FText::FromString(Message));
    }

    /** Stems per hectare, per layer.
     *
     *  THESE ARE FALLBACKS, NOT THE ANSWER. The real numbers belong in a foliage_density.json -
     *  beside the scene file, or in this plugin's Content/Vegetation - so changing how densely the
     *  corridor is planted needs no C++ rebuild, and so the decision can be diffed and argued with
     *  instead of being buried in a compiled constant. These exist only for when that file is
     *  missing, and the tool reports which of the two it used rather than leaving it to be guessed.
     *
     *  The values are real forestry numbers rather than round ones: a closed Michigan woodlot runs
     *  200-400 stems per hectare, scrub is sparser, and farmland is near-zero because a scattered
     *  wood over cropland is the clearest sign vegetation was placed by density rather than by
     *  land use.
     */
    struct FLayerDensity
    {
        FString Layer;
        double TreesPerHa = 0.0;
        double RocksPerHa = 0.0;
    };

    TArray<FLayerDensity> DefaultDensities()
    {
        TArray<FLayerDensity> D;
        D.Add({ TEXT("wood"),     240.0,  4.0 });
        D.Add({ TEXT("scrub"),     40.0, 14.0 });
        D.Add({ TEXT("park"),      35.0,  1.0 });
        D.Add({ TEXT("grass"),      6.0,  2.0 });
        D.Add({ TEXT("farmland"),   1.5,  0.5 });
        return D;
    }

    /** Settings a run can change without recompiling anything. */
    struct FFoliageSettings
    {
        TArray<FLayerDensity> Layers;
        double Scale = 1.0;
        double TreeScaleMin = 0.80, TreeScaleMax = 1.25;
        double RockScaleMin = 0.35, RockScaleMax = 1.60;
        double RockTilt = 12.0;
        FString From;
    };

    /** foliage_density.json: beside the scene file first, then this plugin's own Content.
     *  NO REPOSITORY PATH. The original looked three levels above the project for the tool tree
     *  it was written next to; that tree need not exist beside a plugin, and a candidate that
     *  cannot resolve is just a slower way to reach the built-in defaults below. */
    bool LoadFoliageSettings(const FString& SceneJson, FFoliageSettings& Out)
    {
        TArray<FString> Candidates;
        Candidates.Add(FPaths::GetPath(SceneJson) / TEXT("foliage_density.json"));
        if (const TSharedPtr<IPlugin> Self = IPluginManager::Get().FindPlugin(TEXT("MAirCorridor")))
        {
            Candidates.Add(Self->GetContentDir() / TEXT("Vegetation") /
                           TEXT("foliage_density.json"));
        }

        for (const FString& C : Candidates)
        {
            FString Text;
            if (!FFileHelper::LoadFileToString(Text, *C))
            {
                continue;
            }
            TSharedPtr<FJsonObject> Root;
            if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) ||
                !Root.IsValid())
            {
                continue;
            }
            const TSharedPtr<FJsonObject>* Layers = nullptr;
            if (!Root->TryGetObjectField(TEXT("layers"), Layers) || !Layers)
            {
                continue;
            }
            Out.Layers.Reset();
            for (const auto& Pair : (*Layers)->Values)
            {
                const TSharedPtr<FJsonObject> L = Pair.Value->AsObject();
                if (!L.IsValid())
                {
                    continue;
                }
                FLayerDensity D;
                D.Layer = Pair.Key;
                L->TryGetNumberField(TEXT("trees_per_ha"), D.TreesPerHa);
                L->TryGetNumberField(TEXT("rocks_per_ha"), D.RocksPerHa);
                Out.Layers.Add(D);
            }
            if (Out.Layers.Num() == 0)
            {
                continue;
            }
            Root->TryGetNumberField(TEXT("scale"), Out.Scale);
            const TSharedPtr<FJsonObject>* Var = nullptr;
            if (Root->TryGetObjectField(TEXT("instance_variation"), Var) && Var)
            {
                (*Var)->TryGetNumberField(TEXT("tree_scale_min"), Out.TreeScaleMin);
                (*Var)->TryGetNumberField(TEXT("tree_scale_max"), Out.TreeScaleMax);
                (*Var)->TryGetNumberField(TEXT("rock_scale_min"), Out.RockScaleMin);
                (*Var)->TryGetNumberField(TEXT("rock_scale_max"), Out.RockScaleMax);
                (*Var)->TryGetNumberField(TEXT("rock_tilt_degrees"), Out.RockTilt);
            }
            Out.From = C;
            return true;
        }
        return false;
    }

    /** Even-odd crossing test. The survey's polygons are simple rings, so this is sufficient and
     *  its failure mode - a point on the boundary - moves one tree by centimetres. */
    bool PointInRing(const TArray<FVector2D>& Ring, const FVector2D& P)
    {
        bool bIn = false;
        for (int32 i = 0, j = Ring.Num() - 1; i < Ring.Num(); j = i++)
        {
            if (((Ring[i].Y > P.Y) != (Ring[j].Y > P.Y)) &&
                (P.X < (Ring[j].X - Ring[i].X) * (P.Y - Ring[i].Y) /
                       (Ring[j].Y - Ring[i].Y + KINDA_SMALL_NUMBER) + Ring[i].X))
            {
                bIn = !bIn;
            }
        }
        return bIn;
    }

    double RingAreaM2(const TArray<FVector2D>& Ring)
    {
        double A = 0.0;
        for (int32 i = 0, j = Ring.Num() - 1; i < Ring.Num(); j = i++)
        {
            A += (Ring[j].X * Ring[i].Y) - (Ring[i].X * Ring[j].Y);
        }
        return FMath::Abs(A) * 0.5 / (100.0 * 100.0);   // cm^2 -> m^2
    }
}

namespace
{
    /** Reads the mesh's vertex colours and nothing else, which is exactly what these libraries
     *  carry. ENGINE content - always present, and none of ours. That is what keeps this plugin
     *  standalone: a material of our own here would be one more asset to carry and to keep. */
    UMaterialInterface* VertexColourMaterial()
    {
        return LoadObject<UMaterialInterface>(
            nullptr, TEXT("/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial"));
    }
}

void FMAirCorridorEditorModule::PlaceCorridorFoliage()
{
    IDesktopPlatform* Desktop = FDesktopPlatformModule::Get();
    if (!Desktop)
    {
        return;
    }
    const void* Parent = FSlateApplication::Get().FindBestParentWindowHandleForDialogs(nullptr);

    // The fixed inputs. A picker opens only for one that is not on disk.
    FString SceneJson = FixedInput(TEXT("MAIRCORRIDOR_SCENE"), DefaultSceneJson(), false);
    FString TreeDir = FixedInput(TEXT("MAIRCORRIDOR_TREES"), DefaultTreeDir(), true);
    FString RockDir = FixedInput(TEXT("MAIRCORRIDOR_ROCKS"), DefaultRockDir(), true);

    if (SceneJson.IsEmpty())
    {
        TArray<FString> Picked;
        if (!Desktop->OpenFileDialog(Parent, TEXT("Choose corridor_scene.json"), FPaths::ProjectDir(),
                                     TEXT(""), TEXT("Corridor scene (*.json)|*.json"),
                                     EFileDialogFlags::None, Picked) || Picked.Num() == 0)
        {
            return;
        }
        SceneJson = Picked[0];
    }
    if (TreeDir.IsEmpty())
    {
        TArray<FString> LibDirs;
        if (!Desktop->OpenDirectoryDialog(Parent,
                TEXT("Choose the folder holding the generated trees (corridor_trees)"),
                FPaths::GetPath(SceneJson), LibDirs.Emplace_GetRef()))
        {
            return;
        }
        TreeDir = LibDirs[0];
    }
    if (RockDir.IsEmpty() && !FPaths::DirectoryExists(DefaultRockDir()))
    {
        Desktop->OpenDirectoryDialog(Parent,
            TEXT("Choose the folder holding the generated rocks (corridor_rocks) - cancel to skip"),
            FPaths::GetPath(TreeDir), RockDir);
    }

    UE_LOG(LogTemp, Display, TEXT("[MAirCorridor] scene %s"), *SceneJson);
    UE_LOG(LogTemp, Display, TEXT("[MAirCorridor] trees %s"), *TreeDir);
    UE_LOG(LogTemp, Display, TEXT("[MAirCorridor] rocks %s"),
           RockDir.IsEmpty() ? TEXT("(none)") : *RockDir);

    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!World)
    {
        TellFoliage(TEXT("no editor world to place into"), true);
        return;
    }
    ALandscape* Landscape = nullptr;
    for (TActorIterator<ALandscape> It(World); It; ++It) { Landscape = *It; break; }
    if (!Landscape)
    {
        TellFoliage(TEXT("There is no Landscape in this level, so there is nothing to place onto."), true);
        return;
    }

    /* HOW THE GROUND IS FOUND.
     *
     * Reading the landscape's own heightmap is the primary way, and tracing is the fallback, which
     * is the opposite of the obvious design. The reason is that a scene query needs cooked collision
     * geometry that may simply not be present for an editor landscape, and when it is absent every
     * trace silently finds nothing and the tool plants nothing anywhere.
     *
     * FLandscapeComponentDataInterface is what the landscape tools themselves use: it reads the
     * component's heightmap texture and GetWorldVertex returns the world position of a vertex. It
     * needs no physics and no streaming, only the component, which the level has by definition.
     *
     * Tracing is still used for what it is genuinely good at: finding what STANDS on the ground, so
     * that nothing is planted through a roof or inside a crown. Buildings are ordinary static meshes
     * whose collision works normally. */
    ULandscapeInfo* const Info = Landscape->GetLandscapeInfo();
    const FTransform LandscapeToWorld = Landscape->LandscapeActorToWorld();
    const int32 ComponentQuads = FMath::Max(1, Landscape->ComponentSizeQuads);

    UE_LOG(LogTemp, Display,
           TEXT("[MAirCorridor] landscape '%s' (%s): info %s, %d component(s) mapped, %d collision "
                "component(s) mapped, %d quads per component, actor at %s, landscape-to-world %s"),
           *Landscape->GetActorNameOrLabel(), *Landscape->GetName(), Info ? TEXT("yes") : TEXT("NO"),
           Info ? Info->XYtoComponentMap.Num() : -1, Info ? Info->XYtoCollisionComponentMap.Num() : -1,
           ComponentQuads, *Landscape->GetActorLocation().ToString(),
           *LandscapeToWorld.ToString());

    int32 FromHeightmap = 0, FromQuery = 0, FromTrace = 0;

    auto GroundHeight = [&](double X, double Y, double& OutZ) -> bool
    {
        // 1. The heightmap the landscape is made of. No physics, no streaming.
        if (Info)
        {
            const FVector Local = LandscapeToWorld.InverseTransformPosition(FVector(X, Y, 0.0));
            const FIntPoint Key(FMath::FloorToInt32(Local.X / ComponentQuads),
                                FMath::FloorToInt32(Local.Y / ComponentQuads));
            if (ULandscapeComponent* Comp = Info->XYtoComponentMap.FindRef(Key))
            {
                const FIntPoint Base2 = Comp->GetSectionBase();
                const int32 LocalX = FMath::Clamp(FMath::RoundToInt(Local.X) - Base2.X, 0, ComponentQuads);
                const int32 LocalY = FMath::Clamp(FMath::RoundToInt(Local.Y) - Base2.Y, 0, ComponentQuads);
                FLandscapeComponentDataInterface CDI(Comp, 0, /*bWorkOnEditingLayer=*/false);
                OutZ = CDI.GetWorldVertex(LocalX, LocalY).Z;
                ++FromHeightmap;
                return true;
            }
        }

        // 2. The engine's heightfield query, when there is collision geometry to ask.
        static const EHeightfieldSource Sources[] = { EHeightfieldSource::Complex,
                                                      EHeightfieldSource::Simple,
                                                      EHeightfieldSource::Editor };
        for (EHeightfieldSource Source : Sources)
        {
            const TOptional<float> H = Landscape->GetHeightAtLocation(FVector(X, Y, 0.0), Source);
            if (H.IsSet())
            {
                OutZ = H.GetValue();
                ++FromQuery;
                return true;
            }
        }

        // 3. A trace, which is how this used to work and still serves where the rest cannot.
        const double Top = Landscape->GetActorLocation().Z + 100000.0;
        FHitResult Hit;
        if (World->LineTraceSingleByChannel(Hit, FVector(X, Y, Top), FVector(X, Y, Top - 10000000.0),
                                            ECC_WorldStatic,
                                            FCollisionQueryParams(SCENE_QUERY_STAT(MAirFoliageGround), true))
            && Cast<ALandscapeProxy>(Hit.GetActor()))
        {
            OutZ = Hit.ImpactPoint.Z;
            ++FromTrace;
            return true;
        }
        return false;
    };

    // ---- the library, imported into the project ------------------------------------------
    FAssetToolsModule& AssetTools =
        FModuleManager::LoadModuleChecked<FAssetToolsModule>("AssetTools");
    auto ImportLibrary = [&](const FString& Dir, const FString& Dest,
                             TArray<UStaticMesh*>& Out) -> int32
    {
        if (Dir.IsEmpty()) { return 0; }
        TArray<FString> Files;
        IFileManager::Get().FindFiles(Files, *(Dir / TEXT("*.fbx")), true, false);
        if (Files.Num() == 0) { return 0; }

        // ONE FILE MUST BECOME ONE MESH, and that has to be forced rather than assumed.
        // Each tree FBX holds FOUR objects - Trunk, Branches1, Branches2, Leaves - and without
        // bCombineMeshes the importer makes four separate assets from every file. This routine
        // then collected all of them and the placer instanced them INDIVIDUALLY, so most of what
        // reached the corridor was a bare Leaves object standing on its own with no tree under
        // it. The FBX files were right the whole time; they were being taken apart on arrival.
        UFbxImportUI* Options = NewObject<UFbxImportUI>();
        Options->bImportAsSkeletal = false;
        /* DO NOT IMPORT MATERIALS, AND THIS IS THE CRASH FIX.
         *
         * It used to say bImportMaterials=true with bImportTextures=false, and that pairing is not
         * a preference - it is invalid, and it took the editor down every time the corridor was
         * rendered after a place:
         *
         *     LogUObjectArray: Warning: Other object in slot
         *     Ensure condition failed  [MaterialUniformExpressions.cpp:1321]
         *     Texture not valid! UE-23902! Parameter (DiffuseColorMap)
         *     Access violation reading location 0xFFFFFFFFFFFFFFFF
         *
         * WHY. gen_rocks.py builds one Blender material - a Principled BSDF whose Base Color is
         * driven by a Vertex Color node - and gen_trees.py builds none at all. Dumping the exported
         * FBX shows what Blender actually wrote: a Phong material carrying a DiffuseColor PROPERTY,
         * and ZERO texture objects (no `Texture` node, no `RelativeFilename`). Unreal's FBX importer
         * still creates a texture SAMPLER for that property, named after it - DiffuseColorMap - and
         * bImportTextures=false then forbids it from creating the texture the sampler needs. So the
         * material ships with a null texture, and the first frame that draws 16,534 rock instances
         * dereferences it.
         *
         * The placement was never at fault - it succeeded, and the crash came three minutes later on
         * the first frame after the modal dialog closed, which is why it looked like a placement bug.
         *
         * bImportTextures=true would
         * also stop the ensure, but it would be luck: there is nothing in these files to import, so
         * the sampler's texture would still depend on whatever the importer invents for an empty
         * slot. Not importing materials at all is the honest answer, because the FBX has no material
         * worth having - the colour is in the vertex colours, exactly as both generators intended. */
        Options->bImportMaterials = false;
        Options->bImportTextures = false;
        Options->MeshTypeToImport = FBXIT_StaticMesh;
        Options->StaticMeshImportData->bCombineMeshes = true;
        Options->StaticMeshImportData->bAutoGenerateCollision = true;
        // VERTEX COLOUR IS THE WHOLE MATERIAL HERE. Replace, not Ignore - the default discards
        // it, and a library that carries no textures would arrive with nothing to shade it.
        Options->StaticMeshImportData->VertexColorImportOption = EVertexColorImportOption::Replace;

        /* KEEP THEM REACHABLE. A TArray of raw UObject pointers on the stack is not a GC root, and
         * neither the tasks nor the options object above are referenced from anywhere else - the
         * options' only owner is UAssetImportTask::Options, and the tasks' only owner is this array.
         * ImportAssetTasks ticks the engine, so a collection inside it would free objects that are
         * still in use. "LogUObjectArray: Warning: Other object in slot" in the crash log is what
         * that looks like when it happens. Rooting them costs nothing and removes the question. */
        Options->AddToRoot();
        ON_SCOPE_EXIT { Options->RemoveFromRoot(); };

        TArray<UAssetImportTask*> Tasks;
        for (const FString& F : Files)
        {
            UAssetImportTask* T = NewObject<UAssetImportTask>();
            T->Filename = Dir / F;
            T->DestinationPath = Dest;
            T->bAutomated = true;
            T->bReplaceExisting = true;
            /* BAKED MEANS ON DISK. bSave false left every imported mesh alive only in memory, so
             * the library vanished with the session and the level kept a reference to nothing. That
             * is half of why a scan of this scene found zero vegetation in it. */
            T->bSave = true;
            T->Options = Options;
            T->AddToRoot();
            Tasks.Add(T);
        }
        ON_SCOPE_EXIT { for (UAssetImportTask* T : Tasks) { T->RemoveFromRoot(); } };
        AssetTools.Get().ImportAssetTasks(Tasks);

        for (UAssetImportTask* T : Tasks)
        {
            for (UObject* O : T->GetObjects())
            {
                if (UStaticMesh* M = Cast<UStaticMesh>(O))
                {
                    /* WITH NO IMPORTED MATERIAL, EVERY SECTION DEFAULTS TO WorldGridMaterial - the
                     * grey checkerboard. Not importing materials fixes the crash and would leave a
                     * corridor of checkered trees, which is a different way to be wrong. These
                     * meshes carry their colour in a vertex colour channel (gen_trees.py writes a
                     * "Col" BYTE_COLOR attribute, gen_rocks.py the same), so a material that reads
                     * vertex colour is the whole of what they need, and the one used is
                     * ENGINE content rather than ours, so this plugin stays standalone. */
                    if (UMaterialInterface* VC = VertexColourMaterial())
                    {
                        for (int32 Slot = 0; Slot < M->GetStaticMaterials().Num(); ++Slot)
                        {
                            M->SetMaterial(Slot, VC);
                        }
                        if (M->GetStaticMaterials().Num() == 0)
                        {
                            M->GetStaticMaterials().Add(FStaticMaterial(VC, FName(TEXT("Foliage"))));
                        }
                        M->MarkPackageDirty();
                    }
                    Out.Add(M);
                }
            }
        }
        // A file that produced more than one mesh means the combine did not take, and instancing
        // the pieces separately is exactly the failure this exists to prevent. Say so.
        if (Out.Num() > Files.Num())
        {
            UE_LOG(LogTemp, Warning,
                   TEXT("[MAirCorridor] %d file(s) produced %d mesh(es) - bCombineMeshes did not hold, "
                        "so tree parts would be placed as if each were a whole tree"),
                   Files.Num(), Out.Num());
        }
        return Out.Num();
    };

    TArray<UStaticMesh*> Trees, Rocks;
    const int32 NTree = ImportLibrary(TreeDir, TEXT("/MAirCorridor/Vegetation/Trees"), Trees);
    const int32 NRock = ImportLibrary(RockDir, TEXT("/MAirCorridor/Vegetation/Rocks"), Rocks);

    // ---- CORRECT THE IMPORT SCALE BY MEASURING IT ------------------------------------------
    // The first run put 200-metre trees on the corridor. The FBX files were not at fault - a
    // round trip through Blender returns them at exactly their stated height - so the error was
    // introduced by the import, and its size depends on unit conventions this code does not
    // control and should not have to.
    //
    // So the mesh is MEASURED against the height the generator recorded for it, and the
    // difference becomes the base scale. That is correct whatever the importer did: if the units
    // ever change again, the ratio changes with them and the trees stay the size they are meant
    // to be. Guessing 0.01 would have worked today and broken silently the next time.
    auto MeasuredScales = [&](const FString& Dir, const TArray<UStaticMesh*>& Meshes,
                              const TCHAR* IndexFile, const TCHAR* Field) -> TArray<double>
    {
        TArray<double> Scales;
        Scales.Init(1.0, Meshes.Num());
        FString Text;
        TSharedPtr<FJsonObject> Idx;
        if (Dir.IsEmpty() ||
            !FFileHelper::LoadFileToString(Text, *(Dir / IndexFile)) ||
            !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Idx) || !Idx.IsValid())
        {
            return Scales;
        }
        const TArray<TSharedPtr<FJsonValue>>* Rows = nullptr;
        if (!Idx->TryGetArrayField(Field, Rows) || !Rows)
        {
            return Scales;
        }
        TMap<FString, double> WantM;
        for (const TSharedPtr<FJsonValue>& V : *Rows)
        {
            const TSharedPtr<FJsonObject> O = V->AsObject();
            FString N;
            double H = 0.0;
            if (O.IsValid() && O->TryGetStringField(TEXT("name"), N) &&
                O->TryGetNumberField(TEXT("height_m"), H) && H > 0.0)
            {
                WantM.Add(N, H);
            }
        }
        for (int32 i = 0; i < Meshes.Num(); ++i)
        {
            const double* Want = WantM.Find(Meshes[i]->GetName());
            if (!Want)
            {
                continue;
            }
            const FBoxSphereBounds B = Meshes[i]->GetBounds();
            const double GotCm = B.BoxExtent.Z * 2.0;
            if (GotCm > KINDA_SMALL_NUMBER)
            {
                Scales[i] = (*Want * 100.0) / GotCm;
            }
        }
        return Scales;
    };
    const TArray<double> TreeFix = MeasuredScales(TreeDir, Trees, TEXT("trees.json"),
                                                  TEXT("trees"));
    const TArray<double> RockFix = MeasuredScales(RockDir, Rocks, TEXT("rocks.json"),
                                                  TEXT("rocks"));
    {
        double MinS = BIG_NUMBER, MaxS = 0.0;
        for (double S : TreeFix) { MinS = FMath::Min(MinS, S); MaxS = FMath::Max(MaxS, S); }
        UE_LOG(LogTemp, Display,
               TEXT("[MAirCorridor] import scale correction for trees: %.4f .. %.4f "
                    "(1.0 would mean the importer already agreed with the generator)"),
               MinS, MaxS);
    }
    if (NTree == 0)
    {
        /* WHY IT IMPORTED NOTHING IS THREE DIFFERENT PROBLEMS, and saying "generate the library
         * first" when the library is sitting right there sends someone to re-run a tool that already
         * worked. The first time this fired, 42 tree FBX were on disk and correct; what was missing
         * was the MAirCorridor plugin, so the destination was not a mounted content root and the
         * import had nowhere to put anything. Name the actual cause. */
        FString Probe;
        if (!FPackageName::TryConvertLongPackageNameToFilename(
                FString(TEXT("/MAirCorridor/Vegetation/Trees/probe")), Probe))
        {
            TellFoliage(TEXT("/MAirCorridor is not a mounted content root, so the trees had nowhere to "
                      "import to.\n\nThis tool ships INSIDE that plugin, so the plugin is "
                      "loaded by definition - which means its Content directory is missing or "
                      "unreadable. Check that Plugins/MAirCorridor/Content exists."), true);
            return;
        }
        TArray<FString> Found;
        IFileManager::Get().FindFiles(Found, *(TreeDir / TEXT("*.fbx")), true, false);
        if (Found.Num() == 0)
        {
            TellFoliage(FString::Printf(TEXT("%s holds no .fbx at all - generate the library first with "
                                      "gen_trees.py"), *TreeDir), true);
        }
        else
        {
            TellFoliage(FString::Printf(
                     TEXT("%d .fbx are present in %s and /MAirCorridor is mounted, but none "
                          "imported.\n\nThat is an FBX import failure, not a missing library - the "
                          "Output Log will say why."), Found.Num(), *TreeDir), true);
        }
        return;
    }

    // ---- the survey --------------------------------------------------------------------------
    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *SceneJson))
    {
        TellFoliage(FString::Printf(TEXT("cannot read %s"), *SceneJson), true);
        return;
    }
    TSharedPtr<FJsonObject> Root;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
    {
        TellFoliage(TEXT("that scene file is not valid JSON"), true);
        return;
    }

    AActor* Holder = World->SpawnActor<AActor>(AActor::StaticClass());
    Holder->SetActorLabel(TEXT("CorridorFoliage"));
    /* MARK IT DIRTY OR IT IS NOT SAVED. A spawned actor in a World Partition world needs its package
     * flagged before Save All will write it as an external actor; without this the instances live
     * until the editor closes and then are simply gone - which is what happened, and why the level
     * contains one HISM instead of the corridor's vegetation. */
    Holder->MarkPackageDirty();
    USceneComponent* RootComp = NewObject<USceneComponent>(Holder);
    RootComp->RegisterComponent();
    Holder->SetRootComponent(RootComp);

    TArray<UHierarchicalInstancedStaticMeshComponent*> TreeIsm, RockIsm;
    auto MakeIsm = [&](UStaticMesh* M) -> UHierarchicalInstancedStaticMeshComponent*
    {
        UHierarchicalInstancedStaticMeshComponent* C =
            NewObject<UHierarchicalInstancedStaticMeshComponent>(Holder);
        C->SetStaticMesh(M);
        C->SetMobility(EComponentMobility::Static);
        C->SetupAttachment(RootComp);
        C->RegisterComponent();
        Holder->AddInstanceComponent(C);
        return C;
    };
    for (UStaticMesh* M : Trees) { TreeIsm.Add(MakeIsm(M)); }
    for (UStaticMesh* M : Rocks) { RockIsm.Add(MakeIsm(M)); }

    // ---- how densely to plant: from git, not from a compiled constant ------------------------
    FFoliageSettings Cfg;
    if (!LoadFoliageSettings(SceneJson, Cfg))
    {
        Cfg.Layers = DefaultDensities();
        Cfg.From = TEXT("built-in defaults - foliage_density.json was not found");
    }
    UE_LOG(LogTemp, Display, TEXT("[MAirCorridor] foliage density from %s, scale %.3f"),
           *Cfg.From, Cfg.Scale);
    ON_SCOPE_EXIT
    {
        UE_LOG(LogTemp, Display,
               TEXT("[MAirCorridor] ground heights: %d from the heightmap, %d from the heightfield "
                    "query, %d from a trace"), FromHeightmap, FromQuery, FromTrace);
    };

    const FVector Base = Landscape->GetActorLocation();
    FRandomStream Rng(1057);   // fixed: the same survey must produce the same forest every run
    int32 PlacedTrees = 0, PlacedRocks = 0, Missed = 0, Blocked = 0, Thinned = 0;
    FCollisionQueryParams Q(SCENE_QUERY_STAT(MAirFoliageTrace), true);

    auto DropAt = [&](double XCm, double YCm, bool bTree, bool bSurveyed = false) -> bool
    {
        const double WorldX = Base.X + XCm;
        const double WorldY = Base.Y + YCm;

        // 1. THE GROUND, from the landscape's own heightfield.
        double GroundZ = 0.0;
        if (!GroundHeight(WorldX, WorldY, GroundZ))
        {
            // Outside the Landscape, or over a part of it with no heightfield.
            if (Missed < 10)
            {
                UE_LOG(LogTemp, Warning,
                       TEXT("[MAirCorridor] no ground at x=%.0f y=%.0f (world %.0f %.0f)"),
                       XCm, YCm, WorldX, WorldY);
            }
            ++Missed;
            return false;
        }
        const FVector Where(WorldX, WorldY, GroundZ);

        /* 2. WHAT IS STANDING ON IT, by tracing the air above the ground and nothing below it.
         *
         *   a BUILDING or other structure -> plant NOTHING. That is a roof, not ground, and a tree
         *                                   through a roof is worse than a gap in the trees.
         *   an existing CANOPY            -> plant no TREE, which THINS the scatter. Under a crown
         *                                   that already stands is where another tree should not go.
         *                                   A ROCK still goes down: a rock under a tree is what the
         *                                   floor of a wood looks like.
         *
         * A SURVEYED tree ignores the canopy rule, because the data records a real tree at that
         * spot, but is still refused over a building, which is a data or georeference error.
         *
         * The trace stops 10 cm above the ground so the landscape itself can never be the blocker. */
        TArray<FHitResult> Hits;
        World->LineTraceMultiByChannel(Hits, FVector(WorldX, WorldY, GroundZ + 100000.0),
                                       FVector(WorldX, WorldY, GroundZ + 10.0), ECC_WorldStatic, Q);
        const AActor* Blocker = nullptr;
        for (const FHitResult& H : Hits)
        {
            if (!Cast<ALandscapeProxy>(H.GetActor()))
            {
                Blocker = H.GetActor();
                break;
            }
        }
        if (Blocker)
        {
            if (Blocker != Holder)
            {
                ++Blocked;
                return false;
            }
            if (bTree && !bSurveyed)
            {
                ++Thinned;
                return false;
            }
        }
        // Yaw is free variety and costs nothing; a scatter where every instance faces the same
        // way reads as a texture, not a wood.
        const FRotator Rot(0.0f, Rng.FRandRange(0.0f, 360.0f), 0.0f);
        if (bTree && TreeIsm.Num())
        {
            const int32 i = Rng.RandRange(0, TreeIsm.Num() - 1);
            const float S = Rng.FRandRange((float)Cfg.TreeScaleMin, (float)Cfg.TreeScaleMax)
                          * (float)(TreeFix.IsValidIndex(i) ? TreeFix[i] : 1.0);
            TreeIsm[i]->AddInstance(FTransform(Rot, Where, FVector(S)), true);
            ++PlacedTrees;
        }
        else if (!bTree && RockIsm.Num())
        {
            const int32 i = Rng.RandRange(0, RockIsm.Num() - 1);
            // rocks vary far more in size than trees do, and tilt - a boulder is not level
            const float S = Rng.FRandRange((float)Cfg.RockScaleMin, (float)Cfg.RockScaleMax)
                          * (float)(RockFix.IsValidIndex(i) ? RockFix[i] : 1.0);
            const float T = (float)Cfg.RockTilt;
            const FRotator Tilt(Rng.FRandRange(-T, T), Rot.Yaw, Rng.FRandRange(-T, T));
            RockIsm[i]->AddInstance(FTransform(Tilt, Where, FVector(S)), true);
            ++PlacedRocks;
        }
        return true;
    };

    // ---- 1. the surveyed trees, placed exactly ------------------------------------------------
    const TSharedPtr<FJsonObject>* Points = nullptr;
    int32 Surveyed = 0;
    if (Root->TryGetObjectField(TEXT("points"), Points) && Points)
    {
        const TArray<TSharedPtr<FJsonValue>>* TreePts = nullptr;
        if ((*Points)->TryGetArrayField(TEXT("tree"), TreePts) && TreePts)
        {
            FScopedSlowTask T(static_cast<float>(TreePts->Num()),
                              LOCTEXT("SurveyTrees", "Placing surveyed trees..."));
            T.MakeDialog(true);
            for (const TSharedPtr<FJsonValue>& V : *TreePts)
            {
                if (T.ShouldCancel()) { break; }
                T.EnterProgressFrame(1.0f);
                const TSharedPtr<FJsonObject> O = V->AsObject();
                double X = 0.0, Y = 0.0;
                if (O.IsValid() && O->TryGetNumberField(TEXT("x"), X) &&
                    O->TryGetNumberField(TEXT("y"), Y))
                {
                    if (DropAt(X, Y, true, /*bSurveyed=*/true)) { ++Surveyed; }
                }
            }
        }
    }

    // ---- 2. scatter inside the area polygons -------------------------------------------------
    const TSharedPtr<FJsonObject>* Areas = nullptr;
    if (Root->TryGetObjectField(TEXT("areas"), Areas) && Areas)
    {
        for (const FLayerDensity& L : Cfg.Layers)
        {
            const TArray<TSharedPtr<FJsonValue>>* Polys = nullptr;
            if (!(*Areas)->TryGetArrayField(L.Layer, Polys) || !Polys) { continue; }

            FScopedSlowTask T(static_cast<float>(Polys->Num()),
                              FText::Format(LOCTEXT("ScatterLayer", "Scattering {0}..."),
                                            FText::FromString(L.Layer)));
            T.MakeDialog(true);
            for (const TSharedPtr<FJsonValue>& PV : *Polys)
            {
                if (T.ShouldCancel()) { break; }
                T.EnterProgressFrame(1.0f);
                const TSharedPtr<FJsonObject> PO = PV->AsObject();
                const TArray<TSharedPtr<FJsonValue>>* Pts = nullptr;
                if (!PO.IsValid() || !PO->TryGetArrayField(TEXT("pts"), Pts) || !Pts ||
                    Pts->Num() < 3)
                {
                    continue;
                }
                TArray<FVector2D> Ring;
                Ring.Reserve(Pts->Num());
                FVector2D Min(BIG_NUMBER, BIG_NUMBER), Max(-BIG_NUMBER, -BIG_NUMBER);
                for (const TSharedPtr<FJsonValue>& CV : *Pts)
                {
                    const TArray<TSharedPtr<FJsonValue>>* XY = nullptr;
                    if (!CV->TryGetArray(XY) || !XY || XY->Num() < 2) { continue; }
                    const FVector2D P((*XY)[0]->AsNumber(), (*XY)[1]->AsNumber());
                    Ring.Add(P);
                    Min = FVector2D(FMath::Min(Min.X, P.X), FMath::Min(Min.Y, P.Y));
                    Max = FVector2D(FMath::Max(Max.X, P.X), FMath::Max(Max.Y, P.Y));
                }
                if (Ring.Num() < 3) { continue; }

                const double AreaHa = RingAreaM2(Ring) / 10000.0;
                const int32 WantTrees = FMath::RoundToInt(AreaHa * L.TreesPerHa * Cfg.Scale);
                const int32 WantRocks = FMath::RoundToInt(AreaHa * L.RocksPerHa * Cfg.Scale);

                // REJECTION SAMPLING against the polygon's own bounding box. Attempts are capped
                // at a multiple of what is wanted so a long thin sliver - a hedgerow, a verge -
                // cannot spin forever failing the inside test.
                auto Sprinkle = [&](int32 Want, bool bTree)
                {
                    int32 Made = 0, Tries = 0;
                    const int32 MaxTries = FMath::Max(64, Want * 24);
                    while (Made < Want && Tries < MaxTries)
                    {
                        ++Tries;
                        const FVector2D P(Rng.FRandRange(Min.X, Max.X),
                                          Rng.FRandRange(Min.Y, Max.Y));
                        if (!PointInRing(Ring, P)) { continue; }
                        if (DropAt(P.X, P.Y, bTree)) { ++Made; }
                    }
                };
                Sprinkle(WantTrees, true);
                Sprinkle(WantRocks, false);
            }
        }
    }

    for (UHierarchicalInstancedStaticMeshComponent* C : TreeIsm) { C->BuildTreeIfOutdated(true, false); }
    for (UHierarchicalInstancedStaticMeshComponent* C : RockIsm) { C->BuildTreeIfOutdated(true, false); }

    TellFoliage(FString::Printf(
             TEXT("Corridor foliage placed.\n\n")
             TEXT("%d tree(s) - of which %d are SURVEYED positions from the OSM data, the rest "
                  "scattered inside wood, scrub, park and grass polygons.\n")
             TEXT("%d rock(s).\n")
             TEXT("%d thinned out: a crown already stood there.\n")
             TEXT("%d refused: a building or other structure stood there, not ground.\n")
             TEXT("%d had no ground under them (outside the Landscape).\n\n")
             TEXT("Library: %d tree mesh(es), %d rock mesh(es), imported to "
                  "/MAirCorridor/Vegetation.\n\n")
             TEXT("Every instance was dropped onto the Landscape and placed where it landed - no "
                  "height came from the survey, which describes different terrain."),
             PlacedTrees, Surveyed, PlacedRocks, Thinned, Blocked, Missed, NTree, NRock), false);
}

#undef LOCTEXT_NAMESPACE
