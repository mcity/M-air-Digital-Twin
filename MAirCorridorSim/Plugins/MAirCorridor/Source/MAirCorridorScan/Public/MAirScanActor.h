// MAirScanActor.h - drop this into a level and the M-City scan streams in around the viewer.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MAirScanActor.generated.h"

class UMAirScanMeshComponent;

UCLASS(ClassGroup = (MAirCorridor), meta = (DisplayName = "M-City Scan"))
class MAIRCORRIDORSCAN_API AMAirScanActor : public AActor
{
    GENERATED_BODY()

public:
    AMAirScanActor();

    /** The scan loader. Its settings (tile set, load radius, levels of detail, materials) are edited here. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Scan")
    TObjectPtr<UMAirScanMeshComponent> Scan;
};
