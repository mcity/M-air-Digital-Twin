#!/usr/bin/env python3
"""Pack an installed MAirCorridor plugin's Content into the Hugging Face dataset layout.

    python3 maintainer/package_assets.py --plugin <project>/Plugins/MAirCorridor \
        --terrain <MAirCorridor_Assets>/ue_rect_3m --out <dataset folder>

Maintainers only: users never run this. It writes the archives, the loose files and manifest.json
(sizes and SHA-256 of everything install.py downloads). Needs GNU tar; uses pigz when present.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time

# name -> (file in the dataset, compress?, Content sub-folders/files it holds, what it is)
ARCHIVES = [
    ("corridor_core", "unreal_content/corridor_core.tar.gz", True,
     ["Scene", "Materials", "Aircraft", "Buildings", "Vegetation", "__ExternalObjects__", "AnchorBaked"],
     "The level, terrain materials, building materials, trees and aircraft"),
    ("corridor_level_actors", "unreal_content/corridor_level_actors.tar.gz", True, ["__ExternalActors__"],
     "Every actor placed in the World Partition level (one file each)"),
    ("corridor_buildings", "unreal_content/corridor_buildings.tar.gz", True, ["BuildingsSplit"],
     "One static mesh per building"),
    ("mcity_scan_mesh", "unreal_content/mcity_scan_mesh.tar", False, ["Scan"],
     "The M-City photogrammetric scan as a Nanite mesh (what the level shows)"),
    ("mcity_scan_tiles", "unreal_content/mcity_scan_tiles.tar", False, ["Scans"],
     "The same scan as streamed tiles, read by the MAirCorridorScan module"),
]
# Too big to be worth wrapping in an archive: shipped as they are.
BIG_FILES = [("terrain_imagery", "AnchorBaked/mcity_066m_naip.uasset",
              "unreal_content/terrain_imagery/mcity_066m_naip.uasset",
              "NAIP aerial imagery draped on the terrain (UDIM virtual texture)")]
# Never shipped: unused by the level, or not ours to pack.
EXCLUDE = ["Content/AnchorBaked/mcity_066m_naip.uasset", "Content/AnchorBaked/mcity_rect_07m_naip.uasset",
           "Content/AnchorBaked/mcity05_east.uasset", "Content/AnchorBaked/mcity05_west.uasset"]
TERRAIN_FILES = ["mcity_rect_3m.json", "mcity_rect_3m.r16", "mcity_rect_3m.provenance"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def entry(out, rel, **more):
    path = os.path.join(out, rel)
    return dict(path=rel, bytes=os.path.getsize(path), sha256=sha256(path), **more)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plugin", required=True, help="an installed Plugins/MAirCorridor with its Content")
    ap.add_argument("--terrain", required=True, help="the ue_rect_3m folder (landscape heightmap and plan)")
    ap.add_argument("--out", required=True, help="the dataset folder to write into")
    ap.add_argument("--version", default=time.strftime("%Y.%m.%d"))
    args = ap.parse_args()
    content = os.path.join(args.plugin, "Content")
    if not os.path.isdir(content):
        sys.exit("no Content folder in %s" % args.plugin)
    pigz = shutil.which("pigz")
    items = []
    for name, rel, compress, parts, what in ARCHIVES:
        dest = os.path.join(args.out, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        cmd = ["tar", "--sort=name", "--owner=0", "--group=0", "--numeric-owner", "-C", args.plugin]
        cmd += ["--exclude=" + e for e in EXCLUDE]
        if compress:
            cmd += ["--use-compress-program", (pigz + " -6") if pigz else "gzip -6"]
        cmd += ["-cf", dest] + ["Content/" + p for p in parts]
        print("packing", rel, flush=True)
        subprocess.check_call(cmd)
        raw = int(subprocess.check_output(["du", "-sbc"] + [os.path.join(content, p) for p in parts]).split()[-2])
        items.append(entry(args.out, rel, name=name, kind="archive", extract_to="plugin",
                           installed_bytes=raw, description=what))
    for name, src, rel, what in BIG_FILES:
        dest = os.path.join(args.out, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        print("copying", rel, flush=True)
        shutil.copy2(os.path.join(content, src), dest)
        items.append(entry(args.out, rel, name=name, kind="file", install_to="plugin:Content/" + src,
                           description=what))
    for f in TERRAIN_FILES:
        rel = "terrain_heightmap/ue_rect_3m/" + f
        dest = os.path.join(args.out, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        print("copying", rel, flush=True)
        shutil.copy2(os.path.join(args.terrain, f), dest)
        items.append(entry(args.out, rel, name="terrain_heightmap", kind="file",
                           install_to="assets:ue_rect_3m/" + f,
                           description="Landscape heights the mission tools resolve waypoints against"))
    manifest = {"format": 1, "dataset": "MAirCorridor assets", "version": args.version,
                "unreal_engine": "5.7", "project_airsim": "1.0.1",
                "plugin_mount": "/MAirCorridor", "level": "/MAirCorridor/Scene/CorridorTerrain",
                "WHERE_THINGS_GO": "plugin = <project>/Plugins/MAirCorridor ; assets = MAirCorridor_Assets beside the project",
                "items": items}
    with open(os.path.join(args.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print("wrote manifest.json: %d items, %.1f GB" % (len(items), sum(i["bytes"] for i in items) / 1e9))


if __name__ == "__main__":
    main()
