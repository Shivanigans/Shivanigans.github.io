#!/usr/bin/env python3
"""
make_plates.py - turn Strava GPX walks into layered SVG plates.

Run it like this, passing every walk you want in the gallery at once:

    python3 make_plates.py walks/*.gpx

Passing them all together matters: the plates share one scale, and the
script can only work that scale out if it can see every walk.

Output is one .svg per walk in the plates/ folder, with named layers you
can switch on and off in Figma.
"""

import xml.etree.ElementTree as ET
import datetime
import math
import os
import random
import sys
import json

# ---------------------------------------------------------------------------
# SETTINGS - these are the numbers you are most likely to want to change.
# ---------------------------------------------------------------------------

# Colours, straight from your design reference.
GROUND    = "#f9e278"   # flat yellow background
BLOCKS    = "#f3b568"   # pale orange abstract blocks
PATH      = "#e13a3d"   # red walk path
CAPTION   = "#555555"   # mono grey caption text

# The longest walk's longest side becomes this many pixels. Every other
# walk is then drawn at that same scale, so plate size means distance.
TARGET_LONG_SIDE = 1350

# A GPS fix implying you moved faster than this is treated as an error
# and dropped. 6 m/s is about 21 km/h - not walking.
SPIKE_SPEED = 6.0

# If this many fixes in a row look wrong, assume the GPS has genuinely
# moved rather than that the rest of the walk is an error.
SPIKE_RUN_LIMIT = 8

# Smoothing. Each point is averaged with its neighbours to take the
# jitter out of the trace. Bigger number, smoother and shorter line.
SMOOTH_WINDOW = 5

# Before drawing, thin the line out to roughly this many pixels between
# points. Anything finer is smaller than a pixel, so it cannot be seen -
# it only makes the SVG enormous and slow to open in Figma.
DRAW_EVERY_PX = 1.5

# A pause is: you stayed inside PAUSE_RADIUS metres for at least
# PAUSE_SECONDS seconds. Distance-based, not speed-based, because on a
# steep slow walk "trudging" and "standing still" look the same by speed.
PAUSE_RADIUS = 10.0
PAUSE_SECONDS = 120

# Reversals. The path is resampled every RESAMPLE_M metres, and a change
# of direction sharper than TURN_DEG degrees counts as a reversal.
# Every one found is drawn - nothing is filtered out.
RESAMPLE_M = 12.0
TURN_DEG = 85.0

# A break in recording longer than this many seconds is treated as a gap.
# The path stops and restarts rather than bridging it with a straight line,
# because a bridged gap looks like route you walked and was not.
GAP_SECONDS = 45

# Margins and the caption band. Your plates now range from a few hundred
# pixels to well over a thousand, so these are worked out as a share of
# the plate rather than fixed, then held between a floor and a ceiling.
# To go back to fixed values, set both numbers in a pair to the same thing.
MARGIN_SHARE, MARGIN_MIN, MARGIN_MAX = 0.07, 28, 90
BAND_SHARE,   BAND_MIN,   BAND_MAX   = 0.15, 82, 190

# Captions. Put your own text in captions.json next to this script, like:
#   {"Walk to mcleodganj": "two hours uphill, mostly standing still"}
# Any walk not listed falls back to its Strava name.
CAPTIONS_FILE = "captions.json"

OUT_DIR = "plates"

NS = {"g": "http://www.topografix.com/GPX/1/1"}
EARTH_R = 6371000.0


# ---------------------------------------------------------------------------
# Reading and cleaning the GPX
# ---------------------------------------------------------------------------

def read_gpx(path):
    """Pull the track name and every point out of a Strava GPX file."""
    root = ET.parse(path).getroot()
    name_el = root.find(".//g:trk/g:name", NS)
    name = name_el.text if name_el is not None else os.path.basename(path)

    points = []
    for trkpt in root.iterfind(".//g:trkpt", NS):
        lat = float(trkpt.get("lat"))
        lon = float(trkpt.get("lon"))
        time_el = trkpt.find("g:time", NS)
        if time_el is None:
            continue
        stamp = datetime.datetime.fromisoformat(time_el.text.replace("Z", "+00:00"))
        points.append((lat, lon, stamp))

    if len(points) < 2:
        raise ValueError(f"{path}: not enough points with timestamps")
    return name, points


def to_metres(points):
    """Turn latitude/longitude into flat x/y metres.

    Good enough over a few kilometres, which is all a walk covers.
    x runs east, y runs north.
    """
    mean_lat = sum(p[0] for p in points) / len(points)
    squash = math.cos(math.radians(mean_lat))
    return [
        (math.radians(lon) * EARTH_R * squash,
         math.radians(lat) * EARTH_R,
         stamp)
        for lat, lon, stamp in points
    ]


def drop_spikes(track):
    """Remove fixes that imply impossible speed - GPS errors, not walking.

    Each point is checked against the last point we trusted. If several
    in a row look wrong, the GPS has probably jumped and come back
    somewhere new, so we trust the latest one again rather than throwing
    away the rest of the walk.
    """
    kept = [track[0]]
    dropped = 0
    in_a_row = 0
    for point in track[1:]:
        gap = (point[2] - kept[-1][2]).total_seconds()
        step = math.dist(kept[-1][:2], point[:2])
        bad = gap <= 0 or step / gap > SPIKE_SPEED
        if bad and in_a_row < SPIKE_RUN_LIMIT:
            dropped += 1
            in_a_row += 1
            continue
        in_a_row = 0
        kept.append(point)
    return kept, dropped


def split_on_gaps(track):
    """Cut the walk wherever recording stopped for a while.

    Strava pauses on its own, and signal drops in hills. Joining the two
    ends of such a break draws a straight line across the plate that
    looks like walking but is not, so each stretch is kept separate.
    """
    runs = [[track[0]]]
    for i in range(1, len(track)):
        if (track[i][2] - track[i - 1][2]).total_seconds() > GAP_SECONDS:
            runs.append([])
        runs[-1].append(track[i])
    return [run for run in runs if len(run) >= 2]


def smooth(track, window=SMOOTH_WINDOW):
    """Average each point with its neighbours to settle the line down."""
    if window < 2 or len(track) < window:
        return track
    half = window // 2
    out = []
    for i in range(len(track)):
        lo = max(0, i - half)
        hi = min(len(track), i + half + 1)
        chunk = track[lo:hi]
        out.append((
            sum(p[0] for p in chunk) / len(chunk),
            sum(p[1] for p in chunk) / len(chunk),
            track[i][2],          # keep the original timestamp
        ))
    return out


# ---------------------------------------------------------------------------
# Working out what happened on the walk
# ---------------------------------------------------------------------------

def find_pauses(track):
    """Find the places you stopped.

    Walks forward looking for a run of points that all stay inside
    PAUSE_RADIUS of where the run started. If that run lasted at least
    PAUSE_SECONDS, it counts as a pause.
    """
    pauses = []
    i = 0
    while i < len(track):
        j = i
        while j + 1 < len(track) and math.dist(track[i][:2], track[j + 1][:2]) <= PAUSE_RADIUS:
            j += 1
        seconds = (track[j][2] - track[i][2]).total_seconds()
        if seconds >= PAUSE_SECONDS:
            xs = [p[0] for p in track[i:j + 1]]
            ys = [p[1] for p in track[i:j + 1]]
            pauses.append({
                "x": sum(xs) / len(xs),
                "y": sum(ys) / len(ys),
                "seconds": seconds,
            })
            i = j + 1
        else:
            i += 1
    return pauses


def resample(track, every=RESAMPLE_M):
    """Take a point every `every` metres, so turns are measured evenly.

    Without this, a slow uphill section has far more GPS points than a
    fast flat one and would appear to contain far more turns.
    """
    out = [track[0]]
    run = 0.0
    for i in range(1, len(track)):
        run += math.dist(track[i - 1][:2], track[i][:2])
        if run >= every:
            out.append(track[i])
            run = 0.0
    return out


def find_reversals(track):
    """Find every sharp change of direction. Nothing is filtered out."""
    marks = resample(track)
    found = []
    for i in range(2, len(marks)):
        before = math.atan2(marks[i - 1][1] - marks[i - 2][1],
                            marks[i - 1][0] - marks[i - 2][0])
        after = math.atan2(marks[i][1] - marks[i - 1][1],
                           marks[i][0] - marks[i - 1][0])
        turn = abs(math.degrees(after - before)) % 360
        if turn > 180:
            turn = 360 - turn
        if turn > TURN_DEG:
            found.append({"x": marks[i - 1][0], "y": marks[i - 1][1], "turn": turn})
    return found


def pace_segments(track):
    """Speed for each step of the walk, in metres per second."""
    segments = []
    for i in range(1, len(track)):
        gap = (track[i][2] - track[i - 1][2]).total_seconds()
        if gap <= 0:
            continue
        step = math.dist(track[i - 1][:2], track[i][:2])
        segments.append((track[i - 1][:2], track[i][:2], step / gap))
    return segments


def total_distance(track):
    return sum(math.dist(track[i - 1][:2], track[i][:2]) for i in range(1, len(track)))


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def clamp(value, low, high):
    return max(low, min(high, value))


def make_blocks(pauses, bounds, seed):
    """Build the abstract background blocks from the walk's own pauses.

    One block per pause, bigger the longer you stood there, placed near
    where it happened but nudged and rotated so it reads as abstract
    rather than as a map marker.
    """
    if not pauses:
        return []

    dice = random.Random(seed)
    longest = max(p["seconds"] for p in pauses)
    min_x, min_y, max_x, max_y = bounds
    span = max(max_x - min_x, max_y - min_y)

    blocks = []
    for pause in pauses:
        share = pause["seconds"] / longest          # 0 to 1
        size = span * (0.06 + 0.16 * share)         # metres
        blocks.append({
            "x": pause["x"] + dice.uniform(-0.35, 0.35) * size,
            "y": pause["y"] + dice.uniform(-0.35, 0.35) * size,
            "w": size * dice.uniform(0.7, 1.5),
            "h": size * dice.uniform(0.7, 1.5),
            "angle": dice.uniform(-18, 18),
        })
    return blocks


def pause_radius(seconds, longest_pause, stroke):
    """How big to draw a pause. Area grows with time, which is how the eye
    reads size, and the scale is shared across every plate."""
    share = min(1.0, seconds / longest_pause) if longest_pause else 0.0
    return stroke * (0.8 + 2.2 * math.sqrt(share))


def legend_steps(longest_pause):
    """Pick up to three round durations to label in the legend."""
    minutes = longest_pause / 60
    options = [2, 5, 10, 15, 30, 45, 60, 90, 120]
    usable = [m for m in options if m <= minutes]
    if not usable:
        return [round(minutes)]
    return usable[-3:] if len(usable) >= 3 else usable


def build_plate(name, gpx_path, metres_per_pixel, longest_pause, caption):
    """Do the whole job for one walk and return the finished SVG text."""
    _, raw = read_gpx(gpx_path)
    track = to_metres(raw)
    track, dropped = drop_spikes(track)

    # Pauses and reversals are read from the cleaned-but-unsmoothed track,
    # because smoothing pulls points towards each other and would invent
    # stillness that never happened.
    pauses = find_pauses(track)
    reversals = find_reversals(track)

    step = max(metres_per_pixel * DRAW_EVERY_PX, 1.0)
    runs = [resample(smooth(run), every=step) for run in split_on_gaps(track)]
    runs = [run for run in runs if len(run) >= 2]
    paces = [seg for run in runs for seg in pace_segments(run)]

    xs = [p[0] for run in runs for p in run]
    ys = [p[1] for run in runs for p in run]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width_m, height_m = max_x - min_x, max_y - min_y

    # Frame comes out of the walk's own footprint at the shared scale.
    art_w = width_m / metres_per_pixel
    art_h = height_m / metres_per_pixel
    long_side = max(art_w, art_h)

    margin = clamp(long_side * MARGIN_SHARE, MARGIN_MIN, MARGIN_MAX)

    # Work out the type sizes first, then make the caption band tall
    # enough to actually hold the caption and the legend. Sizing it as a
    # flat share of the plate clipped the legend off short plates.
    size = clamp(long_side / 42, 13, 30)
    small = size * 0.72
    stroke = clamp(long_side / 115, 3.5, 14)
    steps = legend_steps(longest_pause)
    widest = max(pause_radius(m * 60, longest_pause, stroke) for m in steps)

    needed = size * 1.6 + small * 2.6 + widest * 2 + small * 1.8 + margin * 0.5
    band = max(clamp(long_side * BAND_SHARE, BAND_MIN, BAND_MAX), needed)

    plate_w = art_w + margin * 2
    plate_h = art_h + margin * 2 + band

    def place(x, y):
        """Metres to pixels. SVG counts y downwards, so north is flipped."""
        return (margin + (x - min_x) / metres_per_pixel,
                margin + (max_y - y) / metres_per_pixel)

    dot = stroke * 1.7

    parts = []
    add = parts.append

    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{plate_w:.0f}" '
        f'height="{plate_h:.0f}" viewBox="0 0 {plate_w:.2f} {plate_h:.2f}">')
    add(f'  <!-- {name}: {total_distance(track)/1000:.2f} km, '
        f'{len(pauses)} pauses, {len(reversals)} reversals, '
        f'{dropped} GPS spikes dropped, {metres_per_pixel:.3f} m per pixel -->')

    # background
    add('  <g id="background">')
    add(f'    <rect x="0" y="0" width="{plate_w:.2f}" height="{plate_h:.2f}" fill="{GROUND}"/>')
    add('  </g>')

    # blocks
    add('  <g id="blocks">')
    for block in make_blocks(pauses, (min_x, min_y, max_x, max_y), name):
        bx, by = place(block["x"], block["y"])
        bw = block["w"] / metres_per_pixel
        bh = block["h"] / metres_per_pixel
        add(f'    <rect x="{bx - bw/2:.2f}" y="{by - bh/2:.2f}" '
            f'width="{bw:.2f}" height="{bh:.2f}" fill="{BLOCKS}" '
            f'transform="rotate({block["angle"]:.1f} {bx:.2f} {by:.2f})"/>')
    add('  </g>')

    # pace - hidden by default
    add('  <g id="pace" display="none">')
    if paces:
        fastest = max(p[2] for p in paces) or 1.0
        for start, end, speed in paces:
            sx, sy = place(*start)
            ex, ey = place(*end)
            w = stroke * (0.35 + 1.3 * (speed / fastest))
            add(f'    <line x1="{sx:.2f}" y1="{sy:.2f}" x2="{ex:.2f}" y2="{ey:.2f}" '
                f'stroke="{PATH}" stroke-width="{w:.2f}" stroke-linecap="round"/>')
    add('  </g>')

    # path - one polyline per unbroken stretch of recording
    add('  <g id="path">')
    for run in runs:
        points = " ".join(f"{x:.2f},{y:.2f}"
                          for x, y in (place(p[0], p[1]) for p in run))
        add(f'    <polyline points="{points}" fill="none" stroke="{PATH}" '
            f'stroke-width="{stroke:.2f}" stroke-linecap="round" '
            f'stroke-linejoin="round"/>')
    add('  </g>')

    # pauses - sized against the longest pause across ALL walks, so a
    # circle of a given size means the same thing on every plate and the
    # legend below is true.
    add('  <g id="pauses">')
    for pause in pauses:
        px, py = place(pause["x"], pause["y"])
        r = pause_radius(pause["seconds"], longest_pause, stroke)
        add(f'    <circle cx="{px:.2f}" cy="{py:.2f}" r="{r:.2f}" fill="none" '
            f'stroke="{PATH}" stroke-width="{stroke*0.5:.2f}"/>')
    add('  </g>')

    # reversals - hidden by default
    add('  <g id="reversals" display="none">')
    for turn in reversals:
        tx, ty = place(turn["x"], turn["y"])
        add(f'    <circle cx="{tx:.2f}" cy="{ty:.2f}" r="{dot*0.45:.2f}" fill="{PATH}"/>')
    add('  </g>')

    # endpoints
    start_x, start_y = place(runs[0][0][0], runs[0][0][1])
    end_x, end_y = place(runs[-1][-1][0], runs[-1][-1][1])
    add('  <g id="endpoints">')
    add(f'    <circle cx="{start_x:.2f}" cy="{start_y:.2f}" r="{dot:.2f}" fill="{PATH}"/>')
    add(f'    <circle cx="{end_x:.2f}" cy="{end_y:.2f}" r="{dot:.2f}" fill="{PATH}"/>')
    add('  </g>')

    # caption
    base = plate_h - band + size * 1.6
    add('  <g id="caption">')
    add(f'    <text x="{margin:.2f}" y="{base:.2f}" '
        f'font-family="monospace" font-size="{size:.1f}" fill="{CAPTION}">'
        f'{escape(caption)}</text>')
    add('  </g>')

    # legend - what the pause circles mean. Shared across every plate.
    add('  <g id="legend">')
    x = margin + widest
    row = base + small * 2.5 + widest
    add(f'    <text x="{margin:.2f}" y="{base + small * 1.9:.2f}" '
        f'font-family="monospace" font-size="{small:.1f}" fill="{CAPTION}">'
        f'stood still</text>')
    for mins in steps:
        r = pause_radius(mins * 60, longest_pause, stroke)
        add(f'    <circle cx="{x:.2f}" cy="{row:.2f}" r="{r:.2f}" fill="none" '
            f'stroke="{CAPTION}" stroke-width="{stroke*0.4:.2f}"/>')
        add(f'    <text x="{x:.2f}" y="{row + widest + small * 1.15:.2f}" '
            f'font-family="monospace" font-size="{small:.1f}" fill="{CAPTION}" '
            f'text-anchor="middle">{mins} min</text>')
        x += widest * 2 + small * 3.2
    add('  </g>')

    add('</svg>')

    stats = {
        "runs": len(runs),
        "name": name,
        "km": total_distance(track) / 1000,
        "footprint": (width_m, height_m),
        "plate": (plate_w, plate_h),
        "pauses": len(pauses),
        "reversals": len(reversals),
        "dropped": dropped,
    }
    return "\n".join(parts), stats


def escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ---------------------------------------------------------------------------

def main(paths):
    captions = {}
    if os.path.exists(CAPTIONS_FILE):
        with open(CAPTIONS_FILE) as handle:
            captions = json.load(handle)

    # First pass: measure every walk, so one scale can cover them all.
    biggest = 0.0
    for path in paths:
        _, raw = read_gpx(path)
        track, _ = drop_spikes(to_metres(raw))
        track = smooth(track)
        xs = [p[0] for p in track]
        ys = [p[1] for p in track]
        biggest = max(biggest, max(xs) - min(xs), max(ys) - min(ys))

    # The longest pause anywhere sets the pause scale for every plate.
    longest_pause = 1.0
    for path in paths:
        _, raw = read_gpx(path)
        track, _ = drop_spikes(to_metres(raw))
        for pause in find_pauses(track):
            longest_pause = max(longest_pause, pause["seconds"])

    metres_per_pixel = biggest / TARGET_LONG_SIDE
    print(f"Shared scale: {metres_per_pixel:.3f} metres per pixel "
          f"(set by a footprint of {biggest:.0f} m)")
    print(f"Longest pause anywhere: {longest_pause/60:.0f} min "
          f"- this sets the pause circle scale on every plate\n")

    os.makedirs(OUT_DIR, exist_ok=True)

    # Second pass: draw them.
    for path in paths:
        name, _ = read_gpx(path)
        svg, stats = build_plate(name, path, metres_per_pixel, longest_pause,
                                 captions.get(name, name))
        safe = "".join(c if c.isalnum() or c in " -_" else "" for c in name)
        out = os.path.join(OUT_DIR, safe.strip().replace(" ", "_") + ".svg")
        with open(out, "w") as handle:
            handle.write(svg)

        w, h = stats["plate"]
        shape = "portrait" if h > w else "landscape"
        print(f"{stats['name']}")
        print(f"  {stats['km']:.2f} km, footprint "
              f"{stats['footprint'][0]:.0f} x {stats['footprint'][1]:.0f} m")
        print(f"  plate {w:.0f} x {h:.0f} px ({shape})")
        print(f"  {stats['pauses']} pauses -> {stats['pauses']} blocks, "
              f"{stats['reversals']} reversals, {stats['dropped']} spikes dropped")
        if stats["runs"] > 1:
            print(f"  path broken into {stats['runs']} stretches "
                  f"by {stats['runs'] - 1} recording gaps")
        print(f"  written to {out}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1:])
