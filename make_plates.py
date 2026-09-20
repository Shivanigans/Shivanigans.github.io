#!/usr/bin/env python3
"""
make_plates.py - turn Strava GPX walks into layered SVG plates.

Run it with every walk you want in the gallery, all at once:

    python3 make_plates.py walks/*.gpx

Passing them together matters. The plates share one scale for distance and
one scale for pause size, and the script can only work those out if it can
see every walk.

Output is one .svg per walk in plates/, with named layers you can switch on
and off in Figma, plus gallery.json for the web gallery.
"""

import xml.etree.ElementTree as ET
import datetime
import json
import math
import os
import random
import sys
from urllib.parse import quote

# ---------------------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------------------

GROUND  = "#f9e278"   # flat yellow background
BLOCKS  = "#f3b568"   # pale orange abstract blocks
PATH    = "#e13a3d"   # red walk path
CAPTION = "#686136"   # olive, for the caption inside the card
RULE    = "#655920"   # the thin line above the caption

FONT = "JetBrains Mono, ui-monospace, monospace"

# The longest walk's longest side becomes this many pixels. Every other
# walk is drawn at that same scale, so plate size means distance.
TARGET_LONG_SIDE = 1350

SPIKE_SPEED = 6.0       # m/s; faster than this is a GPS error, not walking
SPIKE_RUN_LIMIT = 8     # rejections in a row before we trust the new position
SMOOTH_WINDOW = 5
DRAW_EVERY_PX = 1.5     # thin the line to roughly this many pixels between points

# A pause: stayed inside PAUSE_RADIUS metres for at least PAUSE_SECONDS.
PAUSE_RADIUS = 10.0
PAUSE_SECONDS = 120

# Reversals. Every one found is drawn; nothing is filtered out.
RESAMPLE_M = 12.0
TURN_DEG = 85.0

# Recording gaps - Strava switching itself off to save battery.
# A gap is sorted by how far you got whilst it was off:
#   moved almost nowhere      -> you were standing still, so it is a pause
#   moved slowly              -> you walked it, just unrecorded
#   moved faster than walking -> a vehicle, so not your walk at all
GAP_SECONDS = 45
GAP_STILL_M = 100.0
GAP_WALK_KMH = 3.0

# Which gaps were actually a vehicle. The speed rule above is a guess and
# gets it wrong - a cab crawling through a hill town looks like walking,
# and slow walking over a long gap looks like a cab. You were there, so
# name them here by walk and gap number, as the script prints them.
#   {"Walk to naddi": [6]}
VEHICLE_GAPS = {
    "Walk to naddi": [5],
}

MARGIN_SHARE, MARGIN_MIN, MARGIN_MAX = 0.07, 28, 90

# Wilderness is drawn as scattered conifers rather than a filled shape.
# Roughly one tree per this many pixels of plate, jittered so the spacing
# does not read as a grid.
TREE_EVERY_PX = 74

CAPTIONS_FILE = "captions.json"
OUT_DIR = "plates"

NS = {"g": "http://www.topografix.com/GPX/1/1"}
EARTH_R = 6371000.0

# Points are (x, y, time, elevation).


# ---------------------------------------------------------------------------
# Reading and cleaning
# ---------------------------------------------------------------------------

def read_gpx(path):
    root = ET.parse(path).getroot()
    name_el = root.find(".//g:trk/g:name", NS)
    name = name_el.text if name_el is not None else os.path.basename(path)

    points = []
    for trkpt in root.iterfind(".//g:trkpt", NS):
        time_el = trkpt.find("g:time", NS)
        if time_el is None:
            continue
        ele_el = trkpt.find("g:ele", NS)
        points.append((
            float(trkpt.get("lat")),
            float(trkpt.get("lon")),
            datetime.datetime.fromisoformat(time_el.text.replace("Z", "+00:00")),
            float(ele_el.text) if ele_el is not None else 0.0,
        ))

    if len(points) < 2:
        raise ValueError(f"{path}: not enough points with timestamps")
    return name, points


def reference_latitude(points):
    """The latitude everything on this plate is projected against.

    The walk and its map data must use the same one, or the buildings will
    not sit where the walk actually passed them.
    """
    return sum(p[0] for p in points) / len(points)


def project_point(lat, lon, mean_lat):
    squash = math.cos(math.radians(mean_lat))
    return (math.radians(lon) * EARTH_R * squash, math.radians(lat) * EARTH_R)


def to_metres(points, mean_lat=None):
    """Latitude/longitude to flat x/y metres. x east, y north."""
    if mean_lat is None:
        mean_lat = reference_latitude(points)
    return [project_point(lat, lon, mean_lat) + (stamp, ele)
            for lat, lon, stamp, ele in points]


def drop_spikes(track):
    """Remove fixes implying impossible speed.

    Each point is checked against the last one we trusted. If several in a
    row look wrong the GPS has probably jumped and come back somewhere new,
    so we trust the latest rather than discarding the rest of the walk.
    """
    kept = [track[0]]
    dropped = 0
    in_a_row = 0
    for point in track[1:]:
        gap = (point[2] - kept[-1][2]).total_seconds()
        step = math.dist(kept[-1][:2], point[:2])
        if (gap <= 0 or step / gap > SPIKE_SPEED) and in_a_row < SPIKE_RUN_LIMIT:
            dropped += 1
            in_a_row += 1
            continue
        in_a_row = 0
        kept.append(point)
    return kept, dropped


def smooth(track, window=SMOOTH_WINDOW):
    if window < 2 or len(track) < window:
        return track
    half = window // 2
    out = []
    for i in range(len(track)):
        chunk = track[max(0, i - half):min(len(track), i + half + 1)]
        out.append((sum(p[0] for p in chunk) / len(chunk),
                    sum(p[1] for p in chunk) / len(chunk),
                    track[i][2], track[i][3]))
    return out


def resample(track, every):
    """Take a point every `every` metres, so turns are measured evenly and
    the drawn line is not finer than a pixel."""
    out = [track[0]]
    run = 0.0
    for i in range(1, len(track)):
        run += math.dist(track[i - 1][:2], track[i][:2])
        if run >= every:
            out.append(track[i])
            run = 0.0
    if out[-1] is not track[-1]:
        out.append(track[-1])
    return out


# ---------------------------------------------------------------------------
# Recording gaps
# ---------------------------------------------------------------------------

def classify_gap(before, after):
    """Work out what happened whilst Strava was switched off."""
    seconds = (after[2] - before[2]).total_seconds()
    metres = math.dist(before[:2], after[:2])
    if metres < GAP_STILL_M:
        return "still", seconds, metres
    kmh = metres / seconds * 3.6 if seconds > 0 else 999
    return ("walked" if kmh < GAP_WALK_KMH else "vehicle"), seconds, metres


def split_on_gaps(track, name=None):
    """Cut the walk at every break in recording, and say what each break was."""
    runs = [[track[0]]]
    gaps = []
    for i in range(1, len(track)):
        if (track[i][2] - track[i - 1][2]).total_seconds() > GAP_SECONDS:
            kind, seconds, metres = classify_gap(track[i - 1], track[i])
            gaps.append({"kind": kind, "seconds": seconds, "metres": metres,
                         "from": track[i - 1], "to": track[i],
                         "number": len(gaps) + 1})
            runs.append([])
        runs[-1].append(track[i])

    # Your word beats the speed rule.
    for number in VEHICLE_GAPS.get(name, []):
        if 1 <= number <= len(gaps):
            gaps[number - 1]["kind"] = "vehicle"

    return [r for r in runs if len(r) >= 2], gaps


# ---------------------------------------------------------------------------
# What happened on the walk
# ---------------------------------------------------------------------------

def find_pauses(track):
    """Places you stopped: a run of points all within PAUSE_RADIUS of where
    the run started, lasting at least PAUSE_SECONDS."""
    pauses = []
    i = 0
    while i < len(track):
        j = i
        while j + 1 < len(track) and math.dist(track[i][:2], track[j + 1][:2]) <= PAUSE_RADIUS:
            j += 1
        seconds = (track[j][2] - track[i][2]).total_seconds()
        if seconds >= PAUSE_SECONDS:
            block = track[i:j + 1]
            pauses.append({"x": sum(p[0] for p in block) / len(block),
                           "y": sum(p[1] for p in block) / len(block),
                           "seconds": seconds})
            i = j + 1
        else:
            i += 1
    return pauses


def all_pauses(runs, gaps):
    """Recorded pauses, plus gaps where you barely moved - those were rests
    too, Strava just wasn't watching."""
    found = [p for run in runs for p in find_pauses(run)]
    for gap in gaps:
        if gap["kind"] == "still":
            found.append({"x": (gap["from"][0] + gap["to"][0]) / 2,
                          "y": (gap["from"][1] + gap["to"][1]) / 2,
                          "seconds": gap["seconds"]})
    return found


def find_reversals(runs):
    """Every sharp change of direction. Nothing is filtered out."""
    found = []
    for run in runs:
        marks = resample(run, RESAMPLE_M)
        for i in range(2, len(marks)):
            before = math.atan2(marks[i - 1][1] - marks[i - 2][1],
                                marks[i - 1][0] - marks[i - 2][0])
            after = math.atan2(marks[i][1] - marks[i - 1][1],
                               marks[i][0] - marks[i - 1][0])
            turn = abs(math.degrees(after - before)) % 360
            if turn > 180:
                turn = 360 - turn
            if turn > TURN_DEG:
                found.append({"x": marks[i - 1][0], "y": marks[i - 1][1]})
    return found


# A dead end: you walk out, turn round, and come back over roughly the
# same ground. These are the reroutes - the wrong turnings that a plain
# line loses, because the way out and the way back sit on top of each
# other.
SPUR_CORRIDOR = 28.0      # how close the return has to pass the outbound
SPUR_MIN_OUT = 45.0       # how far out before it counts as a dead end


def find_dead_ends(runs):
    """Places the walk went out and came straight back."""
    points = [p for run in runs for p in resample(smooth(run), 18.0)]
    if len(points) < 8:
        return []

    along = [0.0]
    for i in range(1, len(points)):
        along.append(along[-1] + math.dist(points[i - 1][:2], points[i][:2]))

    found = []
    spent = set()
    for i in range(len(points)):
        if i in spent:
            continue
        best = None
        for j in range(i + 4, min(i + 160, len(points))):
            walked = along[j] - along[i]
            if walked < SPUR_MIN_OUT * 2:
                continue
            if math.dist(points[i][:2], points[j][:2]) <= SPUR_CORRIDOR:
                best = (j, walked)
        if not best:
            continue
        j, walked = best
        reach = max(math.dist(points[i][:2], points[k][:2])
                    for k in range(i, j + 1))
        found.append({
            "reach": reach, "walked": walked,
            "seconds": (points[j][2] - points[i][2]).total_seconds(),
            "at": points[i][2],
        })
        spent.update(range(i, j + 1))
    return found


def pace_segments(track):
    out = []
    for i in range(1, len(track)):
        gap = (track[i][2] - track[i - 1][2]).total_seconds()
        if gap > 0:
            out.append((track[i - 1][:2], track[i][:2],
                        math.dist(track[i - 1][:2], track[i][:2]) / gap))
    return out


def run_distance(run):
    return sum(math.dist(run[i - 1][:2], run[i][:2]) for i in range(1, len(run)))


def walked_distance(runs, gaps):
    """Distance you actually walked. Unrecorded walking counts; a vehicle
    does not."""
    total = sum(run_distance(r) for r in runs)
    total += sum(g["metres"] for g in gaps if g["kind"] == "walked")
    return total


def elevation_profile(runs, gaps):
    """Height against distance walked, for drawing the climb.

    A gap you walked is bridged with a straight line, because you did climb
    it. A gap you rode is skipped entirely - it is not your walk.
    """
    series = []
    covered = 0.0
    for index, run in enumerate(runs):
        if index > 0:
            gap = gaps[index - 1] if index - 1 < len(gaps) else None
            if gap and gap["kind"] == "walked":
                covered += gap["metres"]
                series.append((covered, run[0][3]))
        for i, point in enumerate(run):
            if i > 0:
                covered += math.dist(run[i - 1][:2], point[:2])
            series.append((covered, point[3]))
    return series


def climb(series):
    return sum(max(0.0, series[i][1] - series[i - 1][1])
               for i in range(1, len(series)))


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def clamp(value, low, high):
    return max(low, min(high, value))


def pause_radius(seconds, longest, stroke):
    """Area grows with time, because that is how the eye reads size. The
    scale is shared across every plate, so circles are comparable."""
    share = min(1.0, seconds / longest) if longest else 0.0
    return stroke * (0.8 + 2.2 * math.sqrt(share))


def say_distance(metres):
    return f"{metres:.0f} m" if metres < 1000 else f"{metres/1000:.2f} km"


def make_blocks(runs, span, seed):
    """Abstract ground behind the walk.

    These are decoration, not data. They follow the route loosely so the
    plate has some geography behind it, and they fade back so the red line
    stays the thing you read. Nothing about their size means anything -
    pauses are carried by the circles, which are on a shared scale.

    The seed is the walk's name, so a given walk always draws the same
    ground rather than reshuffling every time the script runs.
    """
    points = [p for run in runs for p in run]
    if not points:
        return []

    dice = random.Random(seed)
    route = sum(run_distance(run) for run in runs)
    count = int(clamp(round(math.sqrt(route) / 6), 6, 22))

    out = []
    for i in range(count):
        # Spread the anchors evenly along the walk, then push each one off
        # the line so the blocks sit behind the route rather than on it.
        anchor = points[min(len(points) - 1,
                            int((i + dice.uniform(0.2, 0.8)) / count * len(points)))]
        size = span * dice.uniform(0.07, 0.19)
        out.append({"x": anchor[0] + dice.uniform(-0.6, 0.6) * size,
                    "y": anchor[1] + dice.uniform(-0.6, 0.6) * size,
                    "w": size * dice.uniform(0.75, 1.45),
                    "h": size * dice.uniform(0.75, 1.45),
                    "angle": dice.uniform(-20, 20),
                    "fade": dice.uniform(0.32, 0.72)})
    return out


def map_file_for(gpx_path):
    """Where the map data for a walk lives: same folder, same name.

    Either extension works, and either format - overpass-turbo's GeoJSON
    export, or the raw JSON the Overpass API returns in a browser.
    """
    stem = os.path.splitext(gpx_path)[0]
    for extension in (".geojson", ".json"):
        if os.path.exists(stem + extension):
            return stem + extension

    # One download usually covers a whole area, and several walks with it.
    # A file called area.geojson beside the walks serves any of them.
    folder = os.path.dirname(gpx_path) or "."
    for shared in ("area.geojson", "area.json"):
        if os.path.exists(os.path.join(folder, shared)):
            return os.path.join(folder, shared)

    return stem + ".geojson"


# Overpass has several public servers. The busiest one refuses work at
# peak times, so offer more than one.
OVERPASS_SERVERS = (
    ("kumi", "https://overpass.kumi.systems/api/interpreter"),
    ("main", "https://overpass-api.de/api/interpreter"),
    ("france", "https://overpass.openstreetmap.fr/api/interpreter"),
)


# What to ask OpenStreetMap for. Wilderness is the land cover a hill walk
# passes through - woods, scrub, grassland, water - which is what fills the
# stretches where nobody has mapped a single building.
WILD_NATURAL = "wood|scrub|heath|grassland|water|wetland|bare_rock|scree"
WILD_LANDUSE = "forest|meadow|grass|orchard|farmland"


def overpass_query(bbox):
    south, west, north, east = bbox
    box = f"{south:.5f},{west:.5f},{north:.5f},{east:.5f}"
    # "nwr" means node, way and relation. Big forests are usually mapped
    # as relations, so asking only for ways misses them entirely.
    return (f"[out:json][timeout:240];\n(\n"
            f'  way["building"]({box});\n'
            f'  way["highway"]({box});\n'
            f'  nwr["natural"~"^({WILD_NATURAL})$"]({box});\n'
            f'  nwr["landuse"~"^({WILD_LANDUSE})$"]({box});\n'
            f'  nwr["leisure"="nature_reserve"]({box});\n'
            f'  nwr["boundary"="protected_area"]({box});\n'
            f");\nout geom;")


def overpass_links(bbox):
    """Ways to fetch this walk's patch of the world.

    The direct links return raw JSON straight into the browser - save that
    and the script reads it. The turbo link is the fallback if you would
    rather see the map before exporting.
    """
    query = overpass_query(bbox)
    direct = [(name, url + "?data=" + quote(query))
              for name, url in OVERPASS_SERVERS]
    return direct, "https://overpass-turbo.eu/?Q=" + quote(query) + "&R"


def is_wild(tags):
    """Is this patch of ground wilderness rather than something built?"""
    return (tags.get("natural") in WILD_NATURAL.split("|")
            or tags.get("landuse") in WILD_LANDUSE.split("|")
            or tags.get("leisure") == "nature_reserve"
            or tags.get("boundary") == "protected_area")


def polygon_area(shape):
    """Area in square metres, by the shoelace formula."""
    total = 0.0
    for i in range(len(shape)):
        x1, y1 = shape[i]
        x2, y2 = shape[(i + 1) % len(shape)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2


def read_map(path, mean_lat):
    """Read buildings and roads out of a GeoJSON file, in metres.

    Accepts what overpass-turbo exports. Anything it does not recognise is
    skipped rather than crashing the plate.
    """
    with open(path) as handle:
        data = json.load(handle)

    buildings, roads, wild = [], [], []

    # Raw Overpass JSON, as the API hands it back with "out geom".
    if "elements" in data:
        for element in data["elements"]:
            shape = [project_point(node["lat"], node["lon"], mean_lat)
                     for node in element.get("geometry") or []]
            if len(shape) < 2:
                continue
            tags = element.get("tags") or {}
            if tags.get("building"):
                buildings.append(shape)
            elif is_wild(tags):
                wild.append(shape)
            elif tags.get("highway"):
                roads.append(shape)
        return ([b for b in buildings if len(b) >= 3],
                [r for r in roads if len(r) >= 2],
                [w for w in wild if len(w) >= 3])

    for feature in data.get("features", []):
        geometry = feature.get("geometry") or {}
        props = feature.get("properties") or {}
        kind = geometry.get("type")
        coords = geometry.get("coordinates")
        if not coords:
            continue

        # GeoJSON is [longitude, latitude], the other way round to a GPX.
        def shape(ring):
            return [project_point(point[1], point[0], mean_lat)
                    for point in ring if len(point) >= 2]

        into = wild if is_wild(props) else buildings

        if kind == "Polygon":
            into.append(shape(coords[0]))
        elif kind == "MultiPolygon":
            for part in coords:
                into.append(shape(part[0]))
        elif kind == "LineString":
            line = shape(coords)
            # A closed way comes through as a line, not a polygon.
            if is_wild(props) and len(line) > 3:
                wild.append(line)
            elif props.get("building") and len(line) > 3:
                buildings.append(line)
            elif props.get("highway"):
                roads.append(line)
        elif kind == "MultiLineString":
            for part in coords:
                roads.append(shape(part))

    return ([b for b in buildings if len(b) >= 3],
            [r for r in roads if len(r) >= 2],
            [w for w in wild if len(w) >= 3])


def touches_frame(shape, bounds, slack):
    """Is any of this shape near enough the plate to be worth drawing?"""
    min_x, min_y, max_x, max_y = bounds
    return any(min_x - slack <= x <= max_x + slack and
               min_y - slack <= y <= max_y + slack for x, y in shape)


def inside_polygon(point, polygon):
    """Ray casting: is this point within the outline?"""
    x, y = point
    hit = False
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % count]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def scatter_trees(wild, bounds, spacing, seed):
    """Place conifers across the wooded ground inside the plate.

    The forest here is one enormous regional polygon, far bigger than any
    one walk, so there is no sense drawing its outline. What is useful is
    where its edge crosses the frame, and scattering trees inside it shows
    exactly that: the wood stops where the town begins.
    """
    if not wild:
        return []

    dice = random.Random(str(seed) + "trees")
    min_x, min_y, max_x, max_y = bounds
    trees = []
    y = min_y
    while y <= max_y:
        x = min_x
        while x <= max_x:
            spot = (x + dice.uniform(-0.38, 0.38) * spacing,
                    y + dice.uniform(-0.38, 0.38) * spacing)
            if any(inside_polygon(spot, area) for area in wild):
                trees.append((spot[0], spot[1], dice.uniform(0.78, 1.25)))
            x += spacing
        y += spacing
    return trees


def conifer(x, y, size, colour, fade):
    """A small fir: two stacked tiers over a short trunk."""
    trunk = size * 0.30
    return (f'    <path d="M {x:.2f} {y - size:.2f} '
            f'L {x + size*0.52:.2f} {y - size*0.30:.2f} '
            f'L {x + size*0.30:.2f} {y - size*0.30:.2f} '
            f'L {x + size*0.68:.2f} {y + size*0.26:.2f} '
            f'L {x - size*0.68:.2f} {y + size*0.26:.2f} '
            f'L {x - size*0.30:.2f} {y - size*0.30:.2f} '
            f'L {x - size*0.52:.2f} {y - size*0.30:.2f} Z" '
            f'fill="none" stroke="{colour}" stroke-width="{size*0.13:.2f}" '
            f'stroke-linejoin="round" opacity="{fade:.2f}"/>\n'
            f'    <line x1="{x:.2f}" y1="{y + size*0.16:.2f}" '
            f'x2="{x:.2f}" y2="{y + size*0.16 + trunk:.2f}" '
            f'stroke="{colour}" stroke-width="{size*0.13:.2f}" '
            f'stroke-linecap="round" opacity="{fade:.2f}"/>')


def escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_plate(name, gpx_path, metres_per_pixel, longest_pause, caption):
    _, raw = read_gpx(gpx_path)
    mean_lat = reference_latitude(raw)
    track, dropped = drop_spikes(to_metres(raw, mean_lat))
    runs, gaps = split_on_gaps(track, name)

    # Pauses and reversals read from the cleaned but unsmoothed track;
    # smoothing pulls points together and would invent stillness.
    pauses = all_pauses(runs, gaps)
    reversals = find_reversals(runs)
    dead_ends = find_dead_ends(runs)
    profile = elevation_profile(runs, gaps)
    distance = walked_distance(runs, gaps)
    ascent = climb(profile)

    step = max(metres_per_pixel * DRAW_EVERY_PX, 1.0)
    drawn = [resample(smooth(run), step) for run in runs]

    # Join the recorded stretches back into continuous routes. Where
    # recording stopped but you kept walking, the two ends are simply
    # joined - a straight line, because that is all the data supports.
    # Only a ride breaks the route, and that is drawn separately.
    chains = []
    chain = list(drawn[0])
    for index, gap in enumerate(gaps):
        if index + 1 >= len(drawn):
            break
        if gap["kind"] == "vehicle":
            chains.append(chain)
            chain = list(drawn[index + 1])
        else:
            chain.extend(drawn[index + 1])
    chains.append(chain)
    chains = [c for c in chains if len(c) >= 2]

    paces = [seg for run in drawn for seg in pace_segments(run)]

    xs = [p[0] for run in chains for p in run]
    ys = [p[1] for run in chains for p in run]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    width_m, height_m = max_x - min_x, max_y - min_y

    art_w = width_m / metres_per_pixel
    art_h = height_m / metres_per_pixel
    long_side = max(art_w, art_h)

    margin = clamp(long_side * MARGIN_SHARE, MARGIN_MIN, MARGIN_MAX)
    size = clamp(long_side / 42, 13, 30)
    small = size * 0.72
    stroke = clamp(long_side / 115, 3.5, 14)
    dot = stroke * 1.7

    # The band holds a rule and the caption, centred. Nothing else.
    lines = [line for line in str(caption).split("\n") if line.strip()] or [""]
    band = (margin * 0.75 + size * 1.5 * len(lines)
            + small * 1.9 + margin * 0.75)

    plate_w = art_w + margin * 2
    plate_h = art_h + margin * 2 + band

    def place(x, y):
        """Metres to pixels. SVG counts y downwards, so north is flipped."""
        return (margin + (x - min_x) / metres_per_pixel,
                margin + (max_y - y) / metres_per_pixel)

    parts = []
    add = parts.append

    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{plate_w:.0f}" '
        f'height="{plate_h:.0f}" viewBox="0 0 {plate_w:.2f} {plate_h:.2f}">')
    # Map data runs past the walk in every direction, so hold it inside the
    # picture. Without this, roads carry on down through the caption band.
    add('  <defs>')
    add(f'    <clipPath id="frame"><rect x="0" y="0" width="{plate_w:.2f}" '
        f'height="{art_h + margin * 2:.2f}"/></clipPath>')
    add('  </defs>')
    add(f'  <!-- {name}: {say_distance(distance)} walked, {ascent:.0f} m climbed, '
        f'{len(pauses)} pauses, {len(reversals)} reversals, '
        f'{len(gaps)} recording gaps, {dropped} GPS spikes dropped, '
        f'{metres_per_pixel:.3f} m per pixel -->')

    add('  <g id="background">')
    add(f'    <rect x="0" y="0" width="{plate_w:.2f}" height="{plate_h:.2f}" fill="{GROUND}"/>')
    add('  </g>')

    bounds = (min_x, min_y, max_x, max_y)
    slack = max(width_m, height_m) * 0.25
    buildings, roads, wild = [], [], []
    map_path = map_file_for(gpx_path)
    if os.path.exists(map_path):
        buildings, roads, wild = read_map(map_path, mean_lat)
        buildings = [b for b in buildings if touches_frame(b, bounds, slack)]
        roads = [r for r in roads if touches_frame(r, bounds, slack)]
        wild = [w for w in wild if touches_frame(w, bounds, slack)]

    # Wilderness first, so buildings and roads sit on top of the trees.
    add('  <g id="wilderness" clip-path="url(#frame)">')
    tree_size = stroke * 1.45
    dice = random.Random(str(name) + "fade")
    for tx, ty, wobble in scatter_trees(
            wild, bounds, metres_per_pixel * TREE_EVERY_PX, name):
        px, py = place(tx, ty)
        add(conifer(px, py, tree_size * wobble, BLOCKS, dice.uniform(0.45, 0.8)))
    add('  </g>')

    add('  <g id="blocks" clip-path="url(#frame)">')
    if buildings:
        # Real building footprints from the map data, in their real places.
        dice = random.Random(name)
        for shape in buildings:
            points = " ".join(f"{x:.2f},{y:.2f}"
                              for x, y in (place(px, py) for px, py in shape))
            add(f'    <polygon points="{points}" fill="none" stroke="{BLOCKS}" '
                f'stroke-width="{stroke*0.32:.2f}" stroke-linejoin="round" '
                f'opacity="{dice.uniform(0.55, 0.95):.2f}"/>')
    else:
        # No map data for this walk, so fall back to abstract ground.
        for block in make_blocks(chains, max(width_m, height_m), name):
            bx, by = place(block["x"], block["y"])
            bw, bh = block["w"] / metres_per_pixel, block["h"] / metres_per_pixel
            add(f'    <rect x="{bx - bw/2:.2f}" y="{by - bh/2:.2f}" '
                f'width="{bw:.2f}" height="{bh:.2f}" fill="none" '
                f'stroke="{BLOCKS}" stroke-width="{stroke*0.32:.2f}" '
                f'opacity="{block["fade"] + 0.2:.2f}" '
                f'transform="rotate({block["angle"]:.1f} {bx:.2f} {by:.2f})"/>')
    add('  </g>')

    # Roads as their own layer, faint, so you can switch them off in Figma.
    add('  <g id="roads" clip-path="url(#frame)">')
    for shape in roads:
        points = " ".join(f"{x:.2f},{y:.2f}"
                          for x, y in (place(px, py) for px, py in shape))
        add(f'    <polyline points="{points}" fill="none" stroke="{BLOCKS}" '
            f'stroke-width="{stroke*0.5:.2f}" stroke-linecap="round" '
            f'stroke-linejoin="round" opacity="0.7"/>')
    add('  </g>')

    add('  <g id="pace" display="none">')
    if paces:
        fastest = max(p[2] for p in paces) or 1.0
        for start, end, speed in paces:
            sx, sy = place(*start)
            ex, ey = place(*end)
            add(f'    <line x1="{sx:.2f}" y1="{sy:.2f}" x2="{ex:.2f}" y2="{ey:.2f}" '
                f'stroke="{PATH}" stroke-width="{stroke*(0.35+1.3*(speed/fastest)):.2f}" '
                f'stroke-linecap="round"/>')
    add('  </g>')

    # Only a ride is drawn here. Gaps you walked are part of the path.
    add('  <g id="gaps">')
    for gap in gaps:
        if gap["kind"] != "vehicle":
            continue
        fx, fy = place(gap["from"][0], gap["from"][1])
        tx, ty = place(gap["to"][0], gap["to"][1])
        add(f'    <line x1="{fx:.2f}" y1="{fy:.2f}" x2="{tx:.2f}" y2="{ty:.2f}" '
            f'stroke="{PATH}" stroke-width="{stroke*0.55:.2f}" stroke-linecap="butt" '
            f'stroke-dasharray="{stroke*2.4:.2f} {stroke*1.5:.2f}" opacity="0.65"/>')
    add('  </g>')

    add('  <g id="path">')
    for index, run in enumerate(chains):
        points = " ".join(f"{x:.2f},{y:.2f}"
                          for x, y in (place(p[0], p[1]) for p in run))
        add(f'    <polyline id="stretch-{index+1}" points="{points}" fill="none" '
            f'stroke="{PATH}" stroke-width="{stroke:.2f}" stroke-linecap="round" '
            f'stroke-linejoin="round"/>')
    add('  </g>')

    add('  <g id="pauses">')
    for pause in pauses:
        px, py = place(pause["x"], pause["y"])
        add(f'    <circle cx="{px:.2f}" cy="{py:.2f}" '
            f'r="{pause_radius(pause["seconds"], longest_pause, stroke):.2f}" '
            f'fill="none" stroke="{PATH}" stroke-width="{stroke*0.5:.2f}"/>')
    add('  </g>')

    add('  <g id="reversals" display="none">')
    for turn in reversals:
        tx, ty = place(turn["x"], turn["y"])
        add(f'    <circle cx="{tx:.2f}" cy="{ty:.2f}" r="{dot*0.45:.2f}" fill="{PATH}"/>')
    add('  </g>')

    start_x, start_y = place(chains[0][0][0], chains[0][0][1])
    end_x, end_y = place(chains[-1][-1][0], chains[-1][-1][1])
    # A filled dot where you set off, a cross where you stopped. Two
    # different shapes, because two identical dots leave no way of telling
    # which end of the walk you are looking at. The cross is deliberately
    # not a ring: the pause marks are rings already.
    arm = dot * 1.35
    add('  <g id="endpoints">')
    add(f'    <circle id="start" cx="{start_x:.2f}" cy="{start_y:.2f}" '
        f'r="{dot:.2f}" fill="{PATH}"/>')
    add(f'    <g id="end" stroke="{PATH}" stroke-width="{stroke*0.8:.2f}" '
        f'stroke-linecap="round">')
    add(f'      <line x1="{end_x - arm:.2f}" y1="{end_y - arm:.2f}" '
        f'x2="{end_x + arm:.2f}" y2="{end_y + arm:.2f}"/>')
    add(f'      <line x1="{end_x - arm:.2f}" y1="{end_y + arm:.2f}" '
        f'x2="{end_x + arm:.2f}" y2="{end_y - arm:.2f}"/>')
    add('    </g>')
    add('  </g>')

    # A thin rule across the card, then the caption centred beneath it,
    # and the distance walked in smaller type under that.
    rule_y = plate_h - band
    centre = plate_w / 2
    add('  <g id="caption">')
    add(f'    <line x1="0" y1="{rule_y:.2f}" x2="{plate_w:.2f}" y2="{rule_y:.2f}" '
        f'stroke="{RULE}" stroke-width="{max(1.0, stroke*0.16):.2f}"/>')
    y = rule_y + margin * 0.75 + size
    for line in lines:
        add(f'    <text x="{centre:.2f}" y="{y:.2f}" font-family="{FONT}" '
            f'font-size="{size:.1f}" font-weight="500" fill="{CAPTION}" '
            f'text-anchor="middle">{escape(line)}</text>')
        y += size * 1.5
    add('  </g>')

    add('  <g id="figures">')
    add(f'    <text x="{centre:.2f}" y="{y + small * 0.5:.2f}" '
        f'font-family="{FONT}" font-size="{small:.1f}" fill="{CAPTION}" '
        f'text-anchor="middle" opacity="0.75">{say_distance(distance)} walked</text>')
    add('  </g>')

    add('</svg>')

    # The bounding box to download map data for, padded a little so the
    # geography reaches the frame edges rather than stopping at the route.
    pad = max(width_m, height_m) * 0.12
    south = math.degrees((min_y - pad) / EARTH_R)
    north = math.degrees((max_y + pad) / EARTH_R)
    squash = math.cos(math.radians(mean_lat))
    west = math.degrees((min_x - pad) / (EARTH_R * squash))
    east = math.degrees((max_x + pad) / (EARTH_R * squash))

    return "\n".join(parts), {
        "map": map_path if buildings or roads or wild else None,
        "buildings": len(buildings), "roads": len(roads),
        "wild": len(wild),
        "trees": len(scatter_trees(wild, bounds,
                                   metres_per_pixel * TREE_EVERY_PX, name)),
        "bbox": (south, west, north, east),
        "name": name, "distance": distance, "ascent": ascent,
        "dead_ends": dead_ends,
        "seconds": (track[-1][2] - track[0][2]).total_seconds(),
        "started": track[0][2].strftime("%H:%M"),
        "finished": track[-1][2].strftime("%H:%M"),
        "footprint": (width_m, height_m), "plate": (plate_w, plate_h),
        "pauses": len(pauses), "reversals": len(reversals),
        "stretches": len(chains), "dropped": dropped,
        "gap_list": [{"number": g["number"], "kind": g["kind"],
                      "seconds": g["seconds"], "metres": g["metres"],
                      "at": g["from"][2].strftime("%H:%M")} for g in gaps],
        "caption": caption,
    }


# ---------------------------------------------------------------------------

def main(paths):
    captions = {}
    if os.path.exists(CAPTIONS_FILE):
        with open(CAPTIONS_FILE) as handle:
            captions = json.load(handle)

    # First pass: measure every walk, so one scale can cover them all.
    biggest = 0.0
    longest_pause = 1.0
    for path in paths:
        name, raw = read_gpx(path)
        track, _ = drop_spikes(to_metres(raw))
        runs, gaps = split_on_gaps(track, name)
        points = [p for run in runs for p in smooth(run)]
        biggest = max(biggest,
                      max(p[0] for p in points) - min(p[0] for p in points),
                      max(p[1] for p in points) - min(p[1] for p in points))
        for pause in all_pauses(runs, gaps):
            longest_pause = max(longest_pause, pause["seconds"])

    metres_per_pixel = biggest / TARGET_LONG_SIDE
    print(f"Shared scale: {metres_per_pixel:.3f} metres per pixel "
          f"(set by a footprint of {biggest:.0f} m)")
    print(f"Longest pause anywhere: {longest_pause/60:.0f} min "
          f"- this sets the pause circle scale on every plate\n")

    os.makedirs(OUT_DIR, exist_ok=True)
    gallery = []

    for path in paths:
        name, _ = read_gpx(path)
        svg, stats = build_plate(name, path, metres_per_pixel, longest_pause,
                                 captions.get(name, name))
        safe = "".join(c if c.isalnum() or c in " -_" else "" for c in name)
        filename = safe.strip().replace(" ", "_") + ".svg"
        with open(os.path.join(OUT_DIR, filename), "w") as handle:
            handle.write(svg)

        w, h = stats["plate"]
        print(stats["name"])
        print(f"  {say_distance(stats['distance'])} walked, "
              f"{stats['ascent']:.0f} m climbed")
        print(f"  plate {w:.0f} x {h:.0f} px "
              f"({'portrait' if h > w else 'landscape'})")
        print(f"  {stats['pauses']} pauses -> {stats['pauses']} blocks, "
              f"{stats['reversals']} reversals, {stats['dropped']} spikes dropped")
        if stats["dead_ends"]:
            biggest = max(stats["dead_ends"], key=lambda d: d["reach"])
            print(f"  {len(stats['dead_ends'])} dead ends, the longest "
                  f"{biggest['reach']:.0f} m out at "
                  f"{biggest['at'].strftime('%H:%M')}")
        if stats["map"]:
            print(f"  map data: {stats['buildings']} buildings, "
                  f"{stats['roads']} roads from {os.path.basename(stats['map'])}")
            if stats["wild"]:
                print(f"  wilderness: {stats['wild']} areas -> "
                      f"{stats['trees']} conifers inside the frame")
            else:
                print(f"  wilderness: none in this file - the query may not "
                      f"have asked for it, or OSM has none mapped here")
        else:
            direct, turbo = overpass_links(stats["bbox"])
            want = os.path.basename(map_file_for(path))
            print(f"  no map data - using abstract blocks.")
            print(f"  For real geography, open one of these, save what comes "
                  f"back as {want}, next to the GPX.")
            print(f"  If a server is busy, try the next one:")
            for label, url in direct:
                print(f"    [{label}] {url}")
            print(f"  Or see it on a map first (Export -> GeoJSON): {turbo}")
        if stats["gap_list"]:
            print(f"  {stats['stretches']} stretches, "
                  f"{len(stats['gap_list'])} recording gaps:")
            for gap in stats["gap_list"]:
                kmh = gap["metres"] / gap["seconds"] * 3.6 if gap["seconds"] else 0
                print(f"    {gap['number']}. {gap['at']}  {gap['seconds']/60:4.0f} min, "
                      f"{gap['metres']:6.0f} m ({kmh:4.1f} km/h) -> {gap['kind']}")
        print(f"  written to {OUT_DIR}/{filename}\n")

        gallery.append({
            "name": stats["name"], "file": filename,
            "caption": stats["caption"],
            "distance": round(stats["distance"]),
            "ascent": round(stats["ascent"]),
            "pauses": stats["pauses"],
            "deadEnds": len(stats["dead_ends"]),
            "minutes": round(stats["seconds"] / 60),
            "started": stats["started"], "finished": stats["finished"],
            "width": round(w), "height": round(h)})

    with open(os.path.join(OUT_DIR, "gallery.json"), "w") as handle:
        json.dump(gallery, handle, indent=2)
    print(f"Gallery index written to {OUT_DIR}/gallery.json")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1:])
