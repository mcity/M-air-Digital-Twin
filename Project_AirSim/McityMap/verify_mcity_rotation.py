"""
verify_mcity_rotation.py — Load McityMap_Main FROM DISK in a fresh editor
process and report whether the saved map is in the rotated (+X = true north)
or original CARLA (+X = east) orientation. Read-only; never modifies the map.

Usage (headless):
   "$UE_ROOT/Engine/Binaries/Linux/UnrealEditor-Cmd" \
       /path/to/McityMap.uproject \
       -ExecutePythonScript="/path/to/verify_mcity_rotation.py"
"""

import unreal

LEVEL_TO_LOAD = "/Game/McityMap/McityMap_Main"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if not level_subsystem.load_level(LEVEL_TO_LOAD):
    raise RuntimeError(f"Failed to load level {LEVEL_TO_LOAD}")

xs, ys = [], []
by_level = {}
for a in actor_subsystem.get_all_level_actors():
    loc = a.get_actor_location()
    xs.append(loc.x)
    ys.append(loc.y)
    level_name = a.get_outer().get_outermost().get_name().split("/")[-1]
    by_level.setdefault(level_name, []).append((loc.x, loc.y))

min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
unreal.log(f"[VERIFY] actor extents (cm): X [{min_x:.0f}, {max_x:.0f}], "
           f"Y [{min_y:.0f}, {max_y:.0f}]")

unreal.log("[VERIFY] per-level extents (cm):")
for level_name in sorted(by_level):
    pts = by_level[level_name]
    lx = [p[0] for p in pts]
    ly = [p[1] for p in pts]
    unreal.log(f"[VERIFY]   {level_name:35s} n={len(pts):4d} "
               f"X [{min(lx):8.0f}, {max(lx):8.0f}] "
               f"Y [{min(ly):8.0f}, {max(ly):8.0f}]")

# Fingerprints (from the McityMap content):
#   original: X [ -9552, 28149], Y [-24231, 18830]  -> min Y < -100 m
#   rotated:  X [-18830, 24231], Y [ -9552, 28149]  -> min Y > -100 m, min X < -150 m
if min_y < -10000.0:
    unreal.log("[VERIFY] VERDICT: UNROTATED (original CARLA orientation, +X = east)")
elif min_x < -15000.0:
    unreal.log("[VERIFY] VERDICT: ROTATED +90 (+X = true north) - GPS-correct")
else:
    unreal.log("[VERIFY] VERDICT: UNRECOGNIZED orientation - inspect manually!")
