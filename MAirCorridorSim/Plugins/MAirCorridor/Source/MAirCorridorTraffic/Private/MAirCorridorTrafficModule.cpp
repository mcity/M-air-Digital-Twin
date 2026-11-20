// MAirCorridorTrafficModule.cpp - a runtime module with nothing in it but the traffic actor.
//
// Separate from MAirCorridorScan because that module streams the photogrammetric scan and this one
// flies real aircraft: they share no code, and a module named for one should not quietly contain
// the other.
#include "Modules/ModuleManager.h"

IMPLEMENT_MODULE(FDefaultModuleImpl, MAirCorridorTraffic);
