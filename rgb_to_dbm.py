#!/usr/bin/env python3
"""Convert an RGB GeoTiff (from Signal Server) to a single-band dBm GeoTiff.

Matches pixel RGB values against the rainbow.dcf color profile to recover
the original dBm signal level.

Usage: python3 rgb_to_dbm.py input.tiff output_dbm.tiff
"""
import sys
import numpy as np

try:
    from osgeo import gdal, osr
    gdal.UseExceptions()
except ImportError:
    print("Error: python3-gdal (GDAL Python bindings) required")
    print("Install: apt install python3-gdal")
    sys.exit(1)

# rainbow.dcf color table: level -> (R, G, B)
DCF_TABLE = [
    (0,   (255, 0, 0)),
    (-10, (255, 128, 0)),
    (-20, (255, 165, 0)),
    (-30, (255, 206, 0)),
    (-40, (255, 255, 0)),
    (-50, (184, 255, 0)),
    (-60, (0, 255, 0)),
    (-70, (0, 208, 0)),
    (-80, (0, 196, 196)),
    (-90, (0, 148, 255)),
    (-100, (80, 80, 255)),
    (-110, (0, 38, 255)),
    (-120, (142, 63, 255)),
    (-130, (196, 54, 255)),
    (-140, (255, 0, 255)),
    (-150, (255, 194, 204)),
]


def build_lookup():
    """Build RGB -> dBm lookup dict with tolerance for compression artifacts."""
    lookup = {}
    for level, (r, g, b) in DCF_TABLE:
        lookup[(r, g, b)] = level
    return lookup


def closest_level(r, g, b, lookup):
    """Find closest DCF color using Euclidean distance."""
    min_dist = float('inf')
    best_level = 0
    for (lr, lg, lb), level in lookup.items():
        dist = (int(r) - lr) ** 2 + (int(g) - lg) ** 2 + (int(b) - lb) ** 2
        if dist < min_dist:
            min_dist = dist
            best_level = level
    return best_level


def convert(input_path, output_path):
    ds = gdal.Open(input_path)
    if ds is None:
        print(f"Error: cannot open {input_path}")
        sys.exit(1)

    bands = ds.RasterCount
    width = ds.RasterXSize
    height = ds.RasterYSize
    gt = ds.GetGeoTransform()
    proj = ds.GetProjection()

    if bands < 3:
        print(f"Error: input has {bands} bands, need RGB (3+)")
        sys.exit(1)

    r_band = ds.GetRasterBand(1).ReadAsArray()
    g_band = ds.GetRasterBand(2).ReadAsArray()
    b_band = ds.GetRasterBand(3).ReadAsArray()

    lookup = build_lookup()

    # Vectorized: build array of unique colors, map each
    # Stack into (H, W, 3) for unique color extraction
    rgb = np.stack([r_band, g_band, b_band], axis=-1)
    flat = rgb.reshape(-1, 3)

    # Find unique colors
    unique_colors = np.unique(flat, axis=0)
    print(f"Processing {len(unique_colors)} unique colors from {width}x{height} image...")

    # Map each unique color to dBm
    color_to_dbm = {}
    for color in unique_colors:
        r, g, b = int(color[0]), int(color[1]), int(color[2])
        if r == 0 and g == 0 and b == 0:
            color_to_dbm[(r, g, b)] = 0  # transparent/no-data
        elif (r, g, b) in lookup:
            color_to_dbm[(r, g, b)] = lookup[(r, g, b)]
        else:
            color_to_dbm[(r, g, b)] = closest_level(r, g, b, lookup)

    # Apply mapping
    dbm_array = np.zeros((height, width), dtype=np.float32)
    for (r, g, b), level in color_to_dbm.items():
        mask = (r_band == r) & (g_band == g) & (b_band == b)
        dbm_array[mask] = level

    # Write output
    driver = gdal.GetDriverByName('GTiff')
    out_ds = driver.Create(output_path, width, height, 1, gdal.GDT_Float32)
    out_ds.SetGeoTransform(gt)
    out_ds.SetProjection(proj)
    out_band = out_ds.GetRasterBand(1)
    out_band.SetNoDataValue(0)
    out_band.WriteArray(dbm_array)
    out_ds.FlushCache()
    out_ds = None

    # Stats
    valid = dbm_array[dbm_array != 0]
    if len(valid):
        print(f"Output: {output_path}")
        print(f"  dBm range: {valid.min():.0f} to {valid.max():.0f}")
        print(f"  Valid pixels: {len(valid)} / {width * height}")
    else:
        print("Warning: no valid signal pixels found")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} input_rgb.tiff output_dbm.tiff")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
