"""geoid.py - between the heights GPS reports and the heights this landscape is built in.

    py -3.10 geoid.py --fetch            download the geoid model (16.7 MB, once)
    py -3.10 geoid.py --at -83.70 42.30  the separation at a point

WHY THIS EXISTS. Three height references meet in this project and they do not agree:

  * The landscape is USGS 3DEP elevation, which is ORTHOMETRIC height in NAVD88: height above
    the geoid, roughly above mean sea level. Mission heights marked "msl" are this.
  * GPS, ADS-B geometric altitude, and the ASTM F3548 exchange format use height above the WGS84
    ELLIPSOID, a smooth mathematical surface.
  * The two differ by the geoid separation N, with h (ellipsoid) = H (orthometric) + N. Around
    Ann Arbor N is about -34 m: the geoid is 34 m BELOW the ellipsoid, so orthometric heights are
    the LARGER numbers.

Thirty four metres is the difference between flying over the trees and through them, and it was
hard coded until this existed. This reads N from NOAA's GEOID18, the model that defines NAVD88
against the ellipsoid, wherever it is asked for.

THE SILENT ZERO IS THE TRAP. PROJ will happily transform between these datums without the grid
installed, return the height unchanged, and report success. That was measured here: rasterio's
bundled PROJ turned 236.0 m ellipsoidal into 236.00 m NAVD88. So this never returns a separation
it did not read from a grid: outside the grid, on a missing value, or with no grid at all, it
raises, and the caller has to decide what to do instead of being handed a confident zero.

ONE APPROXIMATION, STATED. GEOID18 relates NAD83(2011) ellipsoidal heights to NAVD88, while GPS
and ADS-B report WGS84. The two ellipsoidal frames differ by about a metre in this part of
Michigan. That is not corrected: it is an order of magnitude smaller than the vertical error of an
ADS-B report, and correcting it properly needs a time dependent frame transformation this project
has no other use for.

THE GRID LIVES OUTSIDE THE REPOSITORY, in MAIRCORRIDOR_GEOID_DIR or a cache folder in your home
directory. It is NOAA's, public domain, and fetched from the PROJ project's CDN.
"""
import argparse
import io
import math
import os
import sys

GRIDS = {
    # name: (file on cdn.proj.org, what it relates, where it is valid)
    "GEOID18": ("us_noaa_g2018u0.tif", "NAD83(2011) ellipsoid to NAVD88", "conterminous US"),
    "EGM96": ("us_nga_egm96_15.tif", "WGS84 ellipsoid to EGM96 mean sea level", "worldwide"),
}
DEFAULT_MODEL = "GEOID18"
CDN = "https://cdn.proj.org/"


class GeoidUnavailable(Exception):
    """No honest separation can be given for this point. Never answered with a zero."""


def grid_dir():
    from_env = os.environ.get("MAIRCORRIDOR_GEOID_DIR")
    if from_env:
        return from_env
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "MAirCorridor", "geoid")


def grid_path(model=DEFAULT_MODEL):
    return os.path.join(grid_dir(), GRIDS[model][0])


def fetch(model=DEFAULT_MODEL, quiet=False):
    """Download a grid once. Resumes nothing and verifies the size against the server."""
    import requests
    name = GRIDS[model][0]
    path = grid_path(model)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    url = CDN + name
    head = requests.head(url, timeout=60)
    head.raise_for_status()
    expected = int(head.headers.get("Content-Length", "0") or 0)
    if os.path.isfile(path) and expected and os.path.getsize(path) == expected:
        if not quiet:
            print("%s is already here: %s" % (model, path))
        return path
    if not quiet:
        print("fetching %s (%.1f MB) from %s" % (model, expected / 1048576.0, url))
    tmp = path + ".part"
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with io.open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    if expected and os.path.getsize(tmp) != expected:
        os.remove(tmp)
        raise GeoidUnavailable("the download of %s was %d bytes, the server said %d"
                               % (name, os.path.getsize(tmp), expected))
    os.replace(tmp, path)
    if not quiet:
        print("saved %s" % path)
    return path


class Geoid:
    """Geoid separation from a grid, by bilinear interpolation, refusing to guess."""

    _default = None

    def __init__(self, model=DEFAULT_MODEL, path=None):
        import numpy as np
        import rasterio
        self.model = model
        self.path = path or grid_path(model)
        if not os.path.isfile(self.path):
            raise GeoidUnavailable("the %s grid is not at %s. Run: py -3.10 geoid.py --fetch"
                                   % (model, self.path))
        with rasterio.open(self.path) as ds:
            # The whole grid is a few tens of megabytes as float32; holding it costs less than
            # opening the file for every aircraft, every second.
            self.grid = ds.read(1).astype(np.float32)
            self.nodata = ds.nodata
            self.transform = ds.transform
            self.inverse = ~ds.transform
            self.bounds = ds.bounds
            self.width, self.height = ds.width, ds.height
        # Some grids are written in longitudes from 0 to 360.
        self.east_positive = self.bounds.left >= 0.0 and self.bounds.right > 180.0
        self.relates = GRIDS.get(model, ("", "", ""))[1]

    @classmethod
    def default(cls):
        """The installed GEOID18, loaded once. Raises GeoidUnavailable when it is not there."""
        if cls._default is None:
            cls._default = cls(DEFAULT_MODEL)
        return cls._default

    @classmethod
    def available(cls):
        try:
            cls.default()
            return True
        except GeoidUnavailable:
            return False

    def separation(self, lon, lat):
        """N in metres at a point: ellipsoidal height minus orthometric height."""
        x = lon % 360.0 if self.east_positive else lon
        col, row = self.inverse * (x, lat)
        # Pixel centres: the transform maps corners, so shift by half a cell.
        col -= 0.5
        row -= 0.5
        c0, r0 = int(math.floor(col)), int(math.floor(row))
        if c0 < 0 or r0 < 0 or c0 + 1 >= self.width or r0 + 1 >= self.height:
            raise GeoidUnavailable("%.5f, %.5f is outside the %s grid" % (lon, lat, self.model))
        fc, fr = col - c0, row - r0
        cells = self.grid[r0:r0 + 2, c0:c0 + 2]
        values = [float(v) for v in cells.ravel()]
        for v in values:
            if (self.nodata is not None and v == self.nodata) or math.isnan(v) or abs(v) > 200.0:
                raise GeoidUnavailable("the %s grid has no value at %.5f, %.5f"
                                       % (self.model, lon, lat))
        top = values[0] * (1.0 - fc) + values[1] * fc
        bottom = values[2] * (1.0 - fc) + values[3] * fc
        n = top * (1.0 - fr) + bottom * fr
        if n == 0.0:
            # Exactly zero is what a transformation with no grid behind it returns. A real geoid
            # crosses zero only on a line, and never exactly at a bilinear sample.
            raise GeoidUnavailable("a separation of exactly zero at %.5f, %.5f, which is what a "
                                   "missing grid looks like" % (lon, lat))
        return n

    def to_landscape(self, lon, lat, ellipsoidal_m):
        """WGS84 ellipsoid height to this landscape's orthometric height (NAVD88)."""
        return float(ellipsoidal_m) - self.separation(lon, lat)

    def to_ellipsoid(self, lon, lat, orthometric_m):
        """This landscape's orthometric height to WGS84 ellipsoid height."""
        return float(orthometric_m) + self.separation(lon, lat)

    def describe(self, lon=None, lat=None):
        text = "%s (%s)" % (self.model, self.relates)
        if lon is not None and lat is not None:
            try:
                text += ", N = %.2f m here" % self.separation(lon, lat)
            except GeoidUnavailable as e:
                text += ", %s" % e
        return text


def main():
    ap = argparse.ArgumentParser(description="Geoid separation, from a grid, never guessed.")
    ap.add_argument("--fetch", action="store_true", help="download the grid")
    ap.add_argument("--model", choices=sorted(GRIDS), default=DEFAULT_MODEL)
    ap.add_argument("--at", nargs=2, type=float, metavar=("LON", "LAT"),
                    help="print the separation at a point")
    args = ap.parse_args()
    if args.fetch:
        fetch(args.model)
    if args.at:
        try:
            geoid = Geoid(args.model)
        except GeoidUnavailable as e:
            sys.exit(str(e))
        lon, lat = args.at
        n = geoid.separation(lon, lat)
        print("%s at %.5f, %.5f: N = %.3f m" % (geoid.model, lon, lat, n))
        print("so an ellipsoidal height of h is an orthometric height of h %+.3f m" % (-n))
    if not args.fetch and not args.at:
        print("grid folder: %s" % grid_dir())
        for model, (name, relates, where) in sorted(GRIDS.items()):
            path = os.path.join(grid_dir(), name)
            print("  %-8s %-46s %s" % (model, relates,
                                      "installed" if os.path.isfile(path) else "not installed"))


if __name__ == "__main__":
    main()
