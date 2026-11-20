"""drone_configs.py - a Project AirSim robot config for each built drone, so it flies as itself.

    py -3.10 drone_configs.py                    every drone in aircraft/fleet.json with a "flight"
    py -3.10 drone_configs.py --only drone_quad_industrial

For each, writes AirSim/sim_config/robot_<name>.jsonc. A mission flies it by naming that file as its
"robot_config" (fly_mission.py stages the scene with it), or a scene can name it as its robot-config.

WHAT GOES IN, AND FROM WHERE.
  the flight model    Project AirSim's own tested config for that airframe, named by "template" in the
                      drone's "flight" (robot_quadrotor_fastphysics, robot_hexarotor_fastphysics): its
                      links, joints, controller, actuator order and turning directions, unchanged. A
                      layout that flies is kept, not invented.
  where the rotors are  the built model's (model.json from Tools/blender/aircraft_builder.py, with the
                      propellers marked "spin"): each of the template's rotors is moved to the built
                      rotor at the nearest angle around the frame, so the order and directions the
                      controller expects stay with the same corner of the aircraft.
  how big and heavy   the drone's: "mass_kg" on the frame, its inertia from "inertia_box_m", and each
                      rotor's real diameter. Max rpm is then set so the rotors together lift
                      "thrust_to_weight" times the weight. Left at the template's 6397 rpm, 0.53 m
                      propellers would lift the 6.3 kg quad seven times over, where the template
                      lifts its own 1.2 kg 1.4 times over, and its controller is tuned for that.
  what it looks like  the built body (<name>_body) on the frame and the built rotor (<name>_rotor) on
                      each rotor link, which Project AirSim turns as the rotor spins. Imported by
                      Tools/unreal/import_aircraft.py into /MAirCorridor/Aircraft/<name>/.
  what it carries     the sensors of our own robot_mcity_sensors.jsonc, so a flight records the same
                      data whichever drone flies it; "sensor_origins" moves any of them (metres, x
                      forward, y right, z down, Project AirSim's body frame), as a camera inside a
                      bigger body sees nothing.

Project AirSim's body frame is x forward, y right, z down; the model's is x forward, y left, z up.
"""
import argparse
import io
import json
import math
import os
import sys

try:
    import commentjson
except ImportError:
    raise SystemExit("drone_configs needs commentjson: py -3.10 -m pip install commentjson")

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
FLEET = os.path.join(HERE, "aircraft", "fleet.json")
WORK = os.path.join(HERE, "work", "aircraft")
OURS = os.path.join(PLUGIN, "AirSim", "sim_config")
DEFAULT_CLONE = os.environ.get("PROJECTAIRSIM_ROOT", r"E:\projects\ProjectAirSim")
AIR_DENSITY = 1.225                   # kg/m3, sea level; what Project AirSim's rotor model uses
G = 9.80665


def xyz(text):
    return [float(v) for v in str(text).split()]


def fmt(v):
    return " ".join("%.4f" % c for c in v)


def build(entry, template_dir):
    name, fl = entry["name"], entry["flight"]
    with io.open(os.path.join(WORK, name, "model.json"), encoding="utf-8") as f:
        model = json.load(f)
    rotors = model.get("rotors") or []
    if not rotors:
        raise ValueError("%s has no spinning rotors in model.json: build it with them marked \"spin\"" % name)
    with io.open(os.path.join(template_dir, fl["template"]), encoding="utf-8") as f:
        robot = commentjson.load(f)
    with io.open(os.path.join(OURS, "robot_mcity_sensors.jsonc"), encoding="utf-8") as f:
        ours = commentjson.load(f)

    rotor_acts = [a for a in robot["actuators"] if a["type"] == "rotor"]
    if len(rotor_acts) != len(rotors):
        raise ValueError("%s: the template has %d rotors and the model %d" % (name, len(rotor_acts), len(rotors)))

    # Each template rotor to the built rotor nearest it in angle around the frame (body frame).
    built = [{"frd": [r["position_m"][0], -r["position_m"][1], -r["position_m"][2]], "d": r["diameter_m"]}
             for r in rotors]
    for b in built:
        b["az"] = math.atan2(b["frd"][1], b["frd"][0])
    taken, placed = set(), {}
    for act in rotor_acts:
        o = xyz(act["origin"]["xyz"])
        az = math.atan2(o[1], o[0])
        best = min((i for i in range(len(built)) if i not in taken),
                   key=lambda i: abs(math.atan2(math.sin(built[i]["az"] - az), math.cos(built[i]["az"] - az))))
        taken.add(best)
        placed[act["child-link"]] = built[best]

    # The frame: our mass, our inertia, our body.
    frame = robot["links"][0]
    frame["inertial"]["mass"] = fl["mass_kg"]
    box = {"box": {"size": fmt(fl["inertia_box_m"])}}
    frame["inertial"]["inertia"] = {"type": "geometry", "geometry": box}
    frame["inertial"]["aerodynamics"]["geometry"] = box
    frame["visual"]["geometry"] = {"type": "unreal_mesh", "name": "/MAirCorridor/Aircraft/%s/%s_body" % (name, name)}

    # The rotor links where the built rotors are, with the built rotor on each.
    prop_mass = 0.0
    for link in robot["links"][1:]:
        b = placed.get(link["name"])
        if b is None:
            continue
        for part in ("inertial", "visual"):
            if part in link and "origin" in link[part]:
                link[part]["origin"]["xyz"] = fmt(b["frd"])
        link["inertial"]["aerodynamics"]["geometry"] = {"cylinder": {"radius": b["d"] / 2, "length": 0.01}}
        link["visual"]["geometry"] = {"type": "unreal_mesh", "name": "/MAirCorridor/Aircraft/%s/%s_rotor" % (name, name)}
        prop_mass += link["inertial"].get("mass", 0.0)

    # Each rotor's diameter, and the rpm that lifts thrust_to_weight times the weight between them.
    weight = (fl["mass_kg"] + prop_mass) * G
    per_rotor = fl["thrust_to_weight"] * weight / len(rotor_acts)
    for act in rotor_acts:
        b = placed[act["child-link"]]
        act["origin"]["xyz"] = fmt(b["frd"])
        rs = act["rotor-settings"]
        rs["propeller-diameter"] = b["d"]
        rps = math.sqrt(per_rotor / (rs["coeff-of-thrust"] * AIR_DENSITY * b["d"] ** 4))
        rs["max-rpm"] = round(rps * 60.0, 1)

    # Our sensors, moved where the drone needs them.
    sensors = json.loads(json.dumps(ours["sensors"]))
    for s in sensors:
        o = fl.get("sensor_origins", {}).get(s["id"])
        if o is not None:
            s.setdefault("origin", {})["xyz"] = fmt(o)
    robot["sensors"] = sensors

    header = ("// robot_%s.jsonc - written by Tools/drone_configs.py; edit aircraft/fleet.json and run it again.\n"
              "//\n"
              "// The %s built by Tools/blender/aircraft_builder.py, flying on Project AirSim's %s:\n"
              "// its links, joints, controller, actuator order and turning directions, with each rotor moved\n"
              "// to the built rotor at the nearest angle. Frame %.2f kg, inertia from a %s m box, %d rotors of\n"
              "// %.3f m at %.0f rpm at most, lifting %.1f times the weight. Sensors as robot_mcity_sensors.jsonc.\n"
              % (name, name, fl["template"], fl["mass_kg"], " x ".join("%.2f" % v for v in fl["inertia_box_m"]),
                 len(rotor_acts), rotor_acts[0]["rotor-settings"]["propeller-diameter"],
                 rotor_acts[0]["rotor-settings"]["max-rpm"], fl["thrust_to_weight"]))
    out = os.path.join(OURS, "robot_%s.jsonc" % name)
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(header)
        json.dump(robot, f, indent=2)
        f.write("\n")
    return out, rotor_acts


def main():
    ap = argparse.ArgumentParser(description="A Project AirSim robot config for each built drone.")
    ap.add_argument("--only", nargs="+", metavar="NAME")
    ap.add_argument("--clone", default=DEFAULT_CLONE, help="the ProjectAirSim clone, for its template configs")
    args = ap.parse_args()
    template_dir = os.path.join(args.clone, "client", "python", "example_user_scripts", "sim_config")
    with io.open(FLEET, encoding="utf-8") as f:
        fleet = [e for e in json.load(f)["aircraft"] if "flight" in e]
    if args.only:
        fleet = [e for e in fleet if e["name"] in args.only]
    for e in fleet:
        out, acts = build(e, template_dir)
        print("wrote %s" % out)
        for a in acts:
            print("   %-18s %-20s at %s" % (a["name"], a["rotor-settings"]["turning-direction"], a["origin"]["xyz"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
