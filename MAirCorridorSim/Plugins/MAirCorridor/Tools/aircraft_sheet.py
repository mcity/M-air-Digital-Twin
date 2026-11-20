"""aircraft_sheet.py - every built aircraft on one picture, to look over a build.

    py -3.10 aircraft_sheet.py [--view three_quarter|side|top|front] [--out FILE]

Reads the renders Tools/blender/aircraft_builder.py left in Tools/work/aircraft/<name>/views and puts
one view of every aircraft in Tools/aircraft/fleet.json on a grid, labelled, in
Tools/work/aircraft/contact_sheet_<view>.png.
"""
import argparse
import io
import json
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "work", "aircraft")


def main():
    ap = argparse.ArgumentParser(description="Every built aircraft on one picture.")
    ap.add_argument("--view", default="three_quarter", choices=("three_quarter", "side", "top", "front"))
    ap.add_argument("--out")
    args = ap.parse_args()
    with io.open(os.path.join(HERE, "aircraft", "fleet.json"), encoding="utf-8") as f:
        names = [e["name"] for e in json.load(f)["aircraft"]]
    cell, cols = 300, 5
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cell * cols, cell * rows), (140, 143, 150))
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(names):
        x, y = (i % cols) * cell, (i // cols) * cell
        path = os.path.join(WORK, name, "views", args.view + ".png")
        if os.path.isfile(path):
            sheet.paste(Image.open(path).convert("RGB").resize((cell, cell)), (x, y))
        else:
            draw.text((x + 6, y + 20), "not built", fill=(120, 0, 0))
        draw.text((x + 6, y + 6), name, fill=(0, 0, 0))
    out = args.out or os.path.join(WORK, "contact_sheet_%s.png" % args.view)
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main()
