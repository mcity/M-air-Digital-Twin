#!/usr/bin/env python3
"""
change_weather.py - Adjust CARLA-Air weather parameters at runtime.

Connects to a running CARLA-Air simulator and applies the weather parameters
provided on the command line. Any parameter not specified is left at its
current value, so this script can be used to tweak one setting or several
at a time.

Examples:
    # Heavy rain at noon
    python change_weather.py --precipitation 100 --cloudiness 100 --wetness 80

    # Sunset, leave everything else alone
    python change_weather.py --sun-altitude-angle 5 --sun-azimuth-angle 270

    # Apply a built-in preset
    python change_weather.py --preset HardRainNoon

    # Apply a preset then override one value
    python change_weather.py --preset ClearSunset --fog-density 30

    # Print the current weather without changing anything
    python change_weather.py --show
"""

import argparse
import sys

import carla


PARAM_SPECS = [
    ("cloudiness",              0.0, 100.0),
    ("precipitation",           0.0, 100.0),
    ("precipitation_deposits",  0.0, 100.0),
    ("wind_intensity",          0.0, 100.0),
    ("sun_azimuth_angle",       0.0, 360.0),
    ("sun_altitude_angle",    -90.0,  90.0),
    ("fog_density",             0.0, 100.0),
    ("fog_distance",            0.0,  None),
    ("fog_falloff",             0.0,  None),
    ("wetness",                 0.0, 100.0),
]

PRESETS = [
    "ClearNoon", "ClearSunset",
    "CloudyNoon", "CloudySunset",
    "SoftRainNoon", "SoftRainSunset",
    "HardRainNoon", "HardRainSunset",
    "WetNoon", "WetSunset",
    "WetCloudyNoon", "WetCloudySunset",
    "MidRainyNoon", "MidRainSunset",
]


def ranged_float(name, low, high):
    def parse(value):
        try:
            v = float(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{name}: '{value}' is not a number")
        if v < low:
            raise argparse.ArgumentTypeError(f"{name}: {v} is below minimum {low}")
        if high is not None and v > high:
            raise argparse.ArgumentTypeError(f"{name}: {v} is above maximum {high}")
        return v
    return parse


def build_parser():
    p = argparse.ArgumentParser(
        description="Change weather parameters in a running CARLA-Air simulation.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--host", default="localhost", help="CARLA server host")
    p.add_argument("--port", type=int, default=2000, help="CARLA server port")
    p.add_argument("--timeout", type=float, default=10.0, help="Client timeout in seconds")
    p.add_argument("--show", action="store_true",
                   help="Print current weather and exit without applying changes")
    p.add_argument("--preset", choices=PRESETS, metavar="NAME",
                   help="Apply a built-in preset before any individual overrides. "
                        "Choices: " + ", ".join(PRESETS))
    p.add_argument("--list-presets", action="store_true",
                   help="List available presets and exit")

    for name, low, high in PARAM_SPECS:
        flag = "--" + name.replace("_", "-")
        hi_txt = "+" if high is None else str(high)
        p.add_argument(flag, type=ranged_float(name, low, high),
                       metavar=f"[{low}..{hi_txt}]",
                       help=f"Set {name} (range {low} to {hi_txt})")
    return p


def print_weather(weather, header):
    print(header)
    for name, _, _ in PARAM_SPECS:
        print(f"  {name:<24} = {getattr(weather, name):.2f}")


def main():
    args = build_parser().parse_args()

    if args.list_presets:
        print("Available presets:")
        for name in PRESETS:
            print(f"  {name}")
        return 0

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    world = client.get_world()

    weather = world.get_weather()
    print_weather(weather, "Current weather:")

    if args.show:
        return 0

    overrides = {name: getattr(args, name) for name, _, _ in PARAM_SPECS
                 if getattr(args, name) is not None}

    if not args.preset and not overrides:
        print("\nNo changes requested. Use --show, --preset, or one of the --<param> flags.")
        return 0

    if args.preset:
        weather = getattr(carla.WeatherParameters, args.preset)
        print(f"\nApplying preset: {args.preset}")

    for name, value in overrides.items():
        setattr(weather, name, value)

    world.set_weather(weather)

    if overrides:
        print("\nApplied overrides:")
        for name, value in overrides.items():
            print(f"  {name:<24} -> {value:.2f}")

    print_weather(world.get_weather(), "\nNew weather:")
    return 0


if __name__ == "__main__":
    sys.exit(main())
