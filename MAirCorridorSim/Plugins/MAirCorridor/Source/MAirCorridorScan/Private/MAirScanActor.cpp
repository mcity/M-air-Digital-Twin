#include "MAirScanActor.h"

#include "MAirScanMeshComponent.h"

AMAirScanActor::AMAirScanActor()
{
    PrimaryActorTick.bCanEverTick = false;   // the component ticks itself
    Scan = CreateDefaultSubobject<UMAirScanMeshComponent>(TEXT("Scan"));
    RootComponent = Scan;

    /* NOT SPATIALLY LOADED, AND THAT IS THE WHOLE POINT OF THIS ACTOR.
     *
     * World Partition files an actor into a cell by its bounds. This actor has none worth speaking
     * of: it sits at the origin and the scan hangs off it at a surveyed offset, kilometres away, and
     * only exists once tiles have streamed. So the actor lands in the cell at 0,0, and a player over
     * the scan itself is far outside that cell and never loads it: in Play the actor is simply
     * absent, the scan draws nothing, and the only clue is an outliner that does not list it.
     *
     * It also does not need the cells. The component streams its own tiles around the viewer, which
     * is a better fit for a 1.6 km scan than a grid sized for a 65 km corridor. Being always loaded
     * costs one ticking component holding an index of 148 entries until something is near it.
     */
    // Editor-only data: World Partition files actors into cells when the level is saved, and a
    // packaged game only ever sees the result, so the game build has no such property.
#if WITH_EDITORONLY_DATA
    bIsSpatiallyLoaded = false;
#endif
}
