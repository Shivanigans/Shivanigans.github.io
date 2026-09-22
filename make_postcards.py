"""
make_postcards.py - turn Strava GPX walks into postcards, a front and a back.

How to run it, from the folder this file sits in:

    python make_postcards.py walks          <- every .gpx in the walks folder
    python make_postcards.py walks/one.gpx  <- just the one walk

For each walk it writes three things into the cards folder:

    <walk>-front.png    the yellow card with the walk drawn on it
    <walk>-back.png     the info side, with the left half left clear
    gallery.json        a list of what was made, which postcards.html reads

It needs two extra libraries, installed once with:

    pip install pillow numpy
"""

import sys, math, json, os, glob, random, unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------------------------------------------------------------------------
# SETTINGS: the only part you should need to change
# ---------------------------------------------------------------------------

CARD_W, CARD_H = 1350, 1080   # size of every card, in pixels

BORDER  = 46     # width of the cream border round the front
STRIP_H = 104    # height of the caption strip along the bottom of the front
INSET   = 64     # breathing room between the border and anything drawn

# Colours, written as amounts of red, green and blue from 0 to 255.
CREAM  = (244, 238, 218)   # the border, and the whole of the back
BG     = (249, 226, 120)   # the yellow ground on the front
RED    = (225, 58, 61)     # the walk itself
INK    = (85, 85, 85)      # captions and the figures on the back
FAINT  = (154, 147, 128)   # hairlines and the small labels on the back
BLOCKS = (243, 181, 104)   # buildings and roads from OpenStreetMap
GREEN  = (150, 166, 92)    # trees on parks, woods and other green ground

# Green ground is drawn as scattered trees rather than a filled shape.
# A park's outline says almost nothing, and a filled block of colour would
# fight the walk for attention. Scattered trees show where the green
# actually is, and where it stops. Roughly one tree per this many pixels.
TREE_EVERY_PX = 62

PATH_WIDTH = 10
DOT_SIZE   = 16

# "fit"    = every walk fills its own card, so every shape reads clearly
# "shared" = one true scale across every walk, so card size means distance
SCALE_MODE = "fit"

SHOW_PAUSES = True

# A pause means you were moving slower than SLOW_SPEED for at least
# PAUSE_MIN_SECS.
#
# The obvious alternative is to ask whether you stayed within a few metres
# of one spot. That was tried and is worse here, because when you sit still
# the GPS drifts twenty or thirty metres on its own, so the rule decides
# you are walking and misses the rest entirely. Measured that way your
# 84 minute dosa run contained no stops at all.
#
# The known weakness of the speed rule is the opposite one: very slow
# uphill walking is the same speed as standing, so steep climbs read high.
SLOW_SPEED     = 0.3    # metres per second, below this counts as standing
PAUSE_MIN_SECS = 30     # stood still this long before it counts as a pause

# Strava switches itself off to save battery. When it comes back, the two
# ends are far apart and nobody knows what route was taken between them, so
# that stretch is drawn as a dashed line rather than a straight solid one
# pretending to be a path. If you covered it faster than VEHICLE_KMH you
# were not walking, and it is left out of the distance.
GAP_SECONDS = 45      # longer than this between two points means a break
VEHICLE_KMH = 8.0     # faster than this across a break means a vehicle

# Walks to leave out, by the name Strava gave them. The files stay where
# they are, they are simply not drawn.
SKIP = [
    "Vän vihar bicycling änd steling",   # a bicycle ride, not a walk
]

# Draw buildings and roads behind the walk, where map data is available.
# The script looks for a .geojson beside each .gpx with the same name, and
# prints a download link for any walk that has none.
SHOW_MAP = True

# Strava records everything in UTC. Add your local offset here so the back
# of the card shows the time you actually set off. India is 5.5. The UK is
# 0 in winter and 1 in summer.
TZ_OFFSET_HOURS = 5.5

# Paper texture. Left exactly as it was.
PAPER      = True
GRAIN      = 0.07     # fine speckle. 0 = none, 0.15 = heavy
BLOTCH     = 0.045    # soft uneven tone
FIBRES     = 300      # number of faint paper fibres
PAPER_SEED = 7        # same number = identical paper on every card

CAPTIONS_FILE = "captions.json"   # {"Strava track name": "your caption"}
OUT_DIR       = "cards"
SUPERSAMPLE   = 3     # draw big then shrink, so the lines come out smooth
# ---------------------------------------------------------------------------

NS = {'g': 'http://www.topografix.com/GPX/1/1'}
FONT_CANDIDATES = ["JetBrainsMono-Regular.ttf", "consola.ttf", "Consolas.ttf",
                   "DejaVuSansMono.ttf", "Menlo.ttc", "cour.ttf"]


def load_font(size):
    for f in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fit_font(d, text, max_width, start_size, min_size=14):
    """The largest font size that still keeps text inside max_width.

    Captions are yours to write and some will be longer than others, so
    rather than letting a long one run off the card, it is stepped down
    until it fits.
    """
    size = int(start_size)
    while size > min_size:
        font = load_font(size)
        if d.textlength(text, font=font) <= max_width:
            return font
        size -= 2
    return load_font(int(min_size))


# ---------------------------------------------------------------------------
# Reading the walk
# ---------------------------------------------------------------------------

def load_gpx(path):
    root = ET.parse(path).getroot()
    name_el = root.find('.//g:trk/g:name', NS)
    name = name_el.text if name_el is not None else os.path.basename(path)
    pts = []
    for p in root.findall('.//g:trkpt', NS):
        t = p.find('g:time', NS)
        pts.append((float(p.get('lat')), float(p.get('lon')),
                    datetime.fromisoformat(t.text.replace('Z', '+00:00'))))
    if len(pts) < 2:
        raise ValueError(f"{path}: not enough points to draw")
    return name, pts


EARTH_R = 6371000.0


def reference_latitude(pts):
    """The latitude everything on this card is measured against.

    The walk and its map data must use the same one, or the buildings will
    not line up with the streets you actually walked along.
    """
    return sum(p[0] for p in pts) / len(pts)


def project(lat, lon, lat0):
    """One latitude and longitude turned into flat x and y metres."""
    k = math.cos(math.radians(lat0))
    return (math.radians(lon) * EARTH_R * k, math.radians(lat) * EARTH_R)


def to_metres(pts, lat0=None):
    if lat0 is None:
        lat0 = reference_latitude(pts)
    return [project(p[0], p[1], lat0) for p in pts]


def smooth(xy, w=5):
    out = []
    for i in range(len(xy)):
        a, b = max(0, i - w // 2), min(len(xy), i + w // 2 + 1)
        out.append((sum(p[0] for p in xy[a:b]) / (b - a),
                    sum(p[1] for p in xy[a:b]) / (b - a)))
    return out


def prepare(path):
    name, pts = load_gpx(path)
    lat0 = reference_latitude(pts)
    xy = smooth(to_metres(pts, lat0))
    keep = [0]
    for i in range(1, len(xy)):
        dt = (pts[i][2] - pts[keep[-1]][2]).total_seconds()
        if dt > 0 and math.dist(xy[keep[-1]], xy[i]) / dt > 6:
            continue                      # a GPS error, faster than running
        keep.append(i)
    xy = [xy[i] for i in keep]
    pts = [pts[i] for i in keep]
    if len(xy) < 2:
        raise ValueError(f"{path}: every point looked like a GPS error, so "
                         f"there is nothing left to draw")
    speed = [0.0]
    for i in range(1, len(xy)):
        dt = (pts[i][2] - pts[i - 1][2]).total_seconds()
        speed.append(math.dist(xy[i - 1], xy[i]) / dt if dt > 0 else 0.0)
    xs = [p[0] for p in xy]; ys = [p[1] for p in xy]
    return dict(file=path, name=name, xy=xy, pts=pts, lat0=lat0, speed=speed,
                span=(max(xs) - min(xs), max(ys) - min(ys)),
                centre=((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2),
                box=(min(p[0] for p in pts), min(p[1] for p in pts),
                     max(p[0] for p in pts), max(p[1] for p in pts)))


# ---------------------------------------------------------------------------
# What happened on the walk
# ---------------------------------------------------------------------------

def pause_runs(walk):
    """Where you stopped, as (first point, last point, seconds).

    A run of points all slower than SLOW_SPEED, lasting at least
    PAUSE_MIN_SECS. See the note beside those settings for why this is
    measured by speed rather than by whether you stayed in one place.

    Kept separate from the drawing, so the dots on the front and the
    figures on the back always count exactly the same thing.
    """
    sp, pts, out, i = walk['speed'], walk['pts'], [], 1
    while i < len(sp):
        if sp[i] < SLOW_SPEED:
            j = i
            while j < len(sp) and sp[j] < SLOW_SPEED:
                j += 1
            secs = (pts[j - 1][2] - pts[i][2]).total_seconds()
            if secs >= PAUSE_MIN_SECS:
                out.append((i, j, secs))
            i = j
        else:
            i += 1
    return out


def split_on_gaps(walk):
    """Break the walk wherever Strava stopped recording.

    Gives back the stretches that were actually recorded, and the jumps
    between them. A jump is marked as a vehicle if you covered it faster
    than walking pace, which is the only way to tell from the data that
    you were not on foot.
    """
    xy, pts = walk['xy'], walk['pts']
    runs, jumps, start = [], [], 0
    for i in range(1, len(xy)):
        secs = (pts[i][2] - pts[i - 1][2]).total_seconds()
        if secs > GAP_SECONDS:
            runs.append((start, i - 1))
            metres = math.dist(xy[i - 1], xy[i])
            kmh = metres / secs * 3.6 if secs > 0 else 0.0
            jumps.append({'from': i - 1, 'to': i, 'metres': metres,
                          'seconds': secs, 'vehicle': kmh > VEHICLE_KMH})
            start = i
    runs.append((start, len(xy) - 1))
    return [r for r in runs if r[1] > r[0]], jumps


def local(when):
    """A GPX time turned into your local time."""
    return when + timedelta(hours=TZ_OFFSET_HOURS)


def walk_stats(walk):
    """Every figure the back of the card reports."""
    xy, pts = walk['xy'], walk['pts']
    pauses = pause_runs(walk)
    stood = [secs for _, _, secs in pauses]
    runs, jumps = split_on_gaps(walk)

    # What was recorded, plus the gaps you walked but Strava missed. A
    # stretch you rode is not distance you walked, so it is left out.
    metres = sum(math.dist(xy[i - 1], xy[i])
                 for a, b in runs for i in range(a + 1, b + 1))
    metres += sum(j['metres'] for j in jumps if not j['vehicle'])

    return {
        'metres':   metres,
        'ridden':   sum(j['metres'] for j in jumps if j['vehicle']),
        'seconds':  (pts[-1][2] - pts[0][2]).total_seconds(),
        'pauses':   len(pauses),
        'still':    sum(stood),
        'longest':  max(stood) if stood else 0.0,
        'started':  local(pts[0][2]),
        'finished': local(pts[-1][2]),
    }


def say_distance(metres):
    return f"{metres/1000:.1f} km" if metres >= 1000 else f"{metres:.0f} m"


def say_duration(seconds):
    total = int(round(seconds / 60))
    hours, minutes = divmod(total, 60)
    return f"{hours} h {minutes:02d} min" if hours else f"{minutes} min"


def say_minutes(seconds):
    return f"{int(round(seconds / 60))} min"


# ---------------------------------------------------------------------------
# Laying out the front
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Map data from OpenStreetMap
# ---------------------------------------------------------------------------

def map_file_for(gpx_path, name=None):
    """Where a walk's map data lives.

    Your .gpx files are named by Strava activity number, which is no use
    for recognising a walk, so a file named after the walk itself is
    checked first. Failing that, one named after the .gpx, and failing
    that, a shared area.geojson sitting beside the walks.

    A shared file is convenient but only helps if it happens to cover the
    walk in question, so the script checks afterwards whether anything
    actually landed on the card, and says so plainly when nothing did.
    """
    folder = os.path.dirname(gpx_path) or "."
    tries = []
    if name:
        tries.append(os.path.join(folder, safe_name(name) + ".geojson"))
    tries.append(os.path.splitext(gpx_path)[0] + ".geojson")
    tries.append(os.path.join(folder, "area.geojson"))

    for path in tries:
        if os.path.exists(path):
            return path
    return tries[0]        # nothing there yet, so this is what to save as


# What to ask OpenStreetMap for.
OVERPASS = "https://overpass-api.de/api/interpreter"

# Green ground, in OpenStreetMap's own vocabulary. A park, a wood and a
# patch of scrub are all tagged differently, so all of them have to be
# asked for by name.
WILD_NATURAL = "wood|scrub|heath|grassland|water|wetland|tree_row"
WILD_LANDUSE = ("forest|meadow|grass|orchard|farmland|village_green|"
                "recreation_ground|allotments")
WILD_LEISURE = "park|garden|nature_reserve|common"


def overpass_query(box, pad=0.12):
    """The question to ask OpenStreetMap about one walk's patch of world.

    "nwr" means node, way and relation. Big parks and woods are usually
    mapped as relations rather than simple ways, so asking only for ways
    misses them completely.
    """
    south, west, north, east = box
    gap = max(north - south, east - west) * pad
    area = (f"{south - gap:.5f},{west - gap:.5f},"
            f"{north + gap:.5f},{east + gap:.5f}")
    return (f'[out:json][timeout:240];('
            f'way["building"]({area});'
            f'way["highway"]({area});'
            f'nwr["natural"~"^({WILD_NATURAL})$"]({area});'
            f'nwr["landuse"~"^({WILD_LANDUSE})$"]({area});'
            f'nwr["leisure"~"^({WILD_LEISURE})$"]({area});'
            f'nwr["boundary"="protected_area"]({area});'
            f');out geom;')


def overpass_link(box, pad=0.12):
    """A ready-made link that downloads the map data for one walk.

    Open it in a browser, wait for it to finish, and save what comes back
    next to the .gpx with the same name and a .geojson ending.
    """
    return OVERPASS + "?data=" + quote(overpass_query(box, pad))


def is_green(tags):
    """Is this patch of ground green rather than built?"""
    return (tags.get("natural") in WILD_NATURAL.split("|")
            or tags.get("landuse") in WILD_LANDUSE.split("|")
            or tags.get("leisure") in WILD_LEISURE.split("|")
            or tags.get("boundary") == "protected_area")


def read_map(path, lat0):
    """Pull buildings, roads and green ground out of a geojson file.

    Understands both what overpass-turbo exports and the raw JSON the
    Overpass API hands back. Anything it does not recognise is skipped
    rather than stopping the card being made.
    """
    with open(path, encoding='utf-8') as handle:
        data = json.load(handle)

    buildings, roads, green = [], [], []

    # Raw Overpass JSON, as the API returns it with "out geom".
    if "elements" in data:
        for element in data["elements"]:
            tags = element.get("tags") or {}

            # A way carries its own shape. A relation, which is how larger
            # parks and woods are mapped, carries a list of members that
            # each have one.
            rings = []
            if element.get("geometry"):
                rings.append(element["geometry"])
            for member in element.get("members") or []:
                if member.get("geometry"):
                    rings.append(member["geometry"])

            for ring in rings:
                shape = [project(n["lat"], n["lon"], lat0) for n in ring]
                if tags.get("building") and len(shape) >= 3:
                    buildings.append(shape)
                elif is_green(tags) and len(shape) >= 3:
                    green.append(shape)
                elif tags.get("highway") and len(shape) >= 2:
                    roads.append(shape)
        return buildings, roads, green

    # A geojson export. Note that geojson writes coordinates the other way
    # round to a GPX: longitude first, then latitude.
    for feature in data.get("features", []):
        geometry = feature.get("geometry") or {}
        props = feature.get("properties") or {}
        coords = geometry.get("coordinates")
        kind = geometry.get("type")
        if not coords:
            continue

        def shape(ring):
            return [project(p[1], p[0], lat0) for p in ring if len(p) >= 2]

        into = green if is_green(props) else buildings

        if kind == "Polygon":
            into.append(shape(coords[0]))
        elif kind == "MultiPolygon":
            for part in coords:
                into.append(shape(part[0]))
        elif kind == "LineString":
            line = shape(coords)
            # A closed shape comes through as a line, not a polygon.
            if is_green(props) and len(line) > 3:
                green.append(line)
            elif props.get("building") and len(line) > 3:
                buildings.append(line)
            elif props.get("highway"):
                roads.append(line)
        elif kind == "MultiLineString":
            for part in coords:
                roads.append(shape(part))

    return ([b for b in buildings if len(b) >= 3],
            [r for r in roads if len(r) >= 2],
            [g for g in green if len(g) >= 3])


def inside_shape(point, polygon):
    """Is this point within the outline? Counts how many times a ray cast
    sideways crosses the edge: an odd number means inside."""
    x, y = point
    hit = False
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % count]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def scatter_trees(green, bounds, spacing, seed):
    """Place trees across the green ground that falls on the card.

    Stepped over a grid and nudged off it at random, so the spacing does
    not read as a pattern, and each is kept only if it lands inside one of
    the green shapes. The seed is the walk's name, so a given walk always
    grows the same trees instead of reshuffling them on every run.
    """
    if not green:
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
            if any(inside_shape(spot, area) for area in green):
                trees.append((spot[0], spot[1], dice.uniform(0.78, 1.25)))
            x += spacing
        y += spacing
    return trees


def draw_tree(d, x, y, size, colour, width):
    """A small fir: two stacked tiers over a short trunk."""
    d.line([(x, y - size),
            (x + size * 0.52, y - size * 0.30),
            (x + size * 0.30, y - size * 0.30),
            (x + size * 0.68, y + size * 0.26),
            (x - size * 0.68, y + size * 0.26),
            (x - size * 0.30, y - size * 0.30),
            (x - size * 0.52, y - size * 0.30),
            (x, y - size)],
           fill=colour, width=width, joint='curve')
    d.line([(x, y + size * 0.16), (x, y + size * 0.16 + size * 0.30)],
           fill=colour, width=width)


def near_the_card(shape, centre, reach):
    """Is any of this shape close enough to the card to be worth drawing?

    Map data runs well past the walk in every direction, and drawing all of
    it would be slow for no visible gain.
    """
    cx, cy = centre
    return any(abs(x - cx) <= reach and abs(y - cy) <= reach for x, y in shape)


def plot_box():
    """The area on the front that the walk is drawn into, as a rectangle.

    It is the card, less the cream border, less the caption strip along the
    bottom, less a little breathing room on every side.
    """
    return (BORDER + INSET,
            BORDER + INSET,
            CARD_W - BORDER - INSET,
            CARD_H - BORDER - STRIP_H - INSET)


def metres_per_px(span):
    """How many real metres one pixel stands for.

    A bigger number means the walk is drawn smaller. Whichever way the walk
    is longest decides, so it always fits inside the box.
    """
    x0, y0, x1, y1 = plot_box()
    return max(span[0] / (x1 - x0), span[1] / (y1 - y0), 0.0001)


# ---------------------------------------------------------------------------
# Paper texture, unchanged
# ---------------------------------------------------------------------------

def paper_texture(w, h, seed):
    """A multiplier image: 1.0 = unchanged, below 1 darkens, above lightens."""
    rng = np.random.default_rng(seed)
    tex = np.ones((h, w), dtype=np.float32)

    # fine grain
    tex += rng.normal(0, 1, (h, w)).astype(np.float32) * GRAIN * 0.5

    # soft blotches: tiny noise image stretched up and blurred
    small = Image.fromarray(
        (rng.random((h // 40 + 2, w // 40 + 2)) * 255).astype(np.uint8))
    big = small.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(30))
    b = np.asarray(big, dtype=np.float32) / 255.0
    tex += (b - b.mean()) * BLOTCH * 2

    # fibres: short faint curved strokes
    fib = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(fib)
    for _ in range(FIBRES):
        x, y = rng.random() * w, rng.random() * h
        ang = rng.random() * math.pi
        length = 8 + rng.random() * 30
        line = []
        for s in range(6):
            ang += (rng.random() - 0.5) * 0.6
            line.append((x, y))
            x += math.cos(ang) * length / 6
            y += math.sin(ang) * length / 6
        d.line(line, fill=int(40 + rng.random() * 60), width=1)
    f = np.asarray(fib.filter(ImageFilter.GaussianBlur(0.6)), dtype=np.float32) / 255
    tex -= f * 0.12

    return tex


def lay_paper(img, paper):
    if paper is None:
        return img
    arr = np.asarray(img, dtype=np.float32)
    arr = np.clip(arr * paper[:, :, None], 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


# ---------------------------------------------------------------------------
# Drawing text
# ---------------------------------------------------------------------------

def dashed_line(d, start, end, fill, width, dash, space):
    """A dashed straight line. Pillow only draws solid ones, so the dashes
    are stepped along the line by hand."""
    span = math.dist(start, end)
    if span <= 0:
        return
    dx = (end[0] - start[0]) / span
    dy = (end[1] - start[1]) / span
    along = 0.0
    while along < span:
        stop = min(along + dash, span)
        d.line([(start[0] + dx * along, start[1] + dy * along),
                (start[0] + dx * stop, start[1] + dy * stop)],
               fill=fill, width=width)
        along += dash + space


def draw_spaced(d, xy, text, font, fill, spacing):
    """Draw text with extra air between the letters.

    Pillow has no letter spacing of its own, so each character is placed by
    hand. Used for the small uppercase labels on the back.
    """
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill, anchor='ls')
        x += d.textlength(ch, font=font) + spacing


# ---------------------------------------------------------------------------
# The front of the card
# ---------------------------------------------------------------------------

def draw_front(walk, mpp, caption, stats, paper, geography):
    S = SUPERSAMPLE
    W, H = CARD_W * S, CARD_H * S

    img = Image.new('RGB', (W, H), CREAM)
    d = ImageDraw.Draw(img)

    # The yellow ground, sitting inside the cream border.
    d.rectangle([BORDER * S, BORDER * S,
                 (CARD_W - BORDER) * S, (CARD_H - BORDER) * S], fill=BG)

    # Work out where each point of the walk lands on the card.
    cx, cy = walk['centre']
    x0, y0, x1, y1 = plot_box()
    mid_x, mid_y = (x0 + x1) / 2, (y0 + y1) / 2

    def px(p):
        return (((p[0] - cx) / mpp + mid_x) * S,
                (mid_y - (p[1] - cy) / mpp) * S)

    strip_y = CARD_H - BORDER - STRIP_H

    # Buildings and roads, if this walk has any. They are drawn on a layer
    # of their own and then cropped to the picture area, because map data
    # runs past the walk in every direction and would otherwise spill over
    # the cream border and through the caption.
    if geography:
        buildings, roads, trees = geography
        layer = Image.new('RGBA', (W, H), BG + (255,))
        ld = ImageDraw.Draw(layer, 'RGBA')

        # Trees first, so the town sits on top of the green rather than
        # the other way round.
        dice = random.Random(str(walk['name']) + "fade")
        tree_size = PATH_WIDTH * 1.5 * S
        for tx, ty, wobble in trees:
            fade = int(255 * dice.uniform(0.5, 0.85))
            draw_tree(ld, *px((tx, ty)), tree_size * wobble,
                      GREEN + (fade,), max(1, int(PATH_WIDTH * 0.2 * S)))

        # Then roads, then buildings on top of those.
        for shape in roads:
            ld.line([px(p) for p in shape], fill=BLOCKS + (170,),
                    width=max(1, int(PATH_WIDTH * 0.42 * S)),
                    joint='curve')
        for shape in buildings:
            ring = [px(p) for p in shape]
            ld.line(ring + [ring[0]], fill=BLOCKS + (225,),
                    width=max(1, int(PATH_WIDTH * 0.3 * S)))

        picture = (BORDER * S, BORDER * S, (CARD_W - BORDER) * S, strip_y * S)
        img.paste(layer.convert('RGB').crop(picture),
                  (BORDER * S, BORDER * S))
        d = ImageDraw.Draw(img)

    P = [px(p) for p in walk['xy']]
    lw = PATH_WIDTH * S

    # The walk is drawn in the pieces Strava actually recorded. Where it
    # switched off, a dashed line crosses the gap instead, because the real
    # route between those two points is not known and a solid line there
    # would look like a path you took.
    runs, jumps = split_on_gaps(walk)
    for a, b in runs:
        d.line(P[a:b + 1], fill=RED, width=lw, joint='curve')
    for jump in jumps:
        dashed_line(d, P[jump['from']], P[jump['to']], RED,
                    max(1, int(lw * 0.62)), lw * 2.2, lw * 1.6)

    # Pause dots, drawn see-through so overlapping ones still read.
    if SHOW_PAUSES:
        overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for i, j, secs in pause_runs(walk):
            seg = P[i:j]
            if not seg:
                continue
            x = sum(a for a, b in seg) / len(seg)
            y = sum(b for a, b in seg) / len(seg)
            r = (6 + math.sqrt(secs) * 1.6) * S
            od.ellipse([x - r, y - r, x + r, y + r], fill=RED + (140,))
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
        d = ImageDraw.Draw(img)

    # An empty circle where you set off, a filled one where you finished.
    # Two different marks, because two identical dots leave no way of
    # telling which end of the walk you are looking at.
    r = DOT_SIZE * S
    first, last = P[0], P[-1]
    d.ellipse([first[0] - r, first[1] - r, first[0] + r, first[1] + r],
              fill=BG, outline=RED, width=max(1, int(lw * 0.6)))
    d.ellipse([last[0] - r, last[1] - r, last[0] + r, last[1] + r], fill=RED)

    # The caption strip: a hairline, then the place on the left and the
    # date on the right.
    d.line([(BORDER * S, strip_y * S), ((CARD_W - BORDER) * S, strip_y * S)],
           fill=FAINT, width=max(1, int(1.5 * S)))

    font = load_font(int(38 * S))
    base = (strip_y + STRIP_H * 0.63) * S
    left = (BORDER + INSET * 0.55) * S
    right = (CARD_W - BORDER - INSET * 0.55) * S

    # The date is fixed width, so the caption gets whatever is left over,
    # less a gap so the two never touch.
    date_text = stats['started'].strftime('%d%m%Y')
    room = (right - left) - d.textlength(date_text, font=font) - 30 * S
    d.text((left, base), caption, fill=INK,
           font=fit_font(d, caption, room, 38 * S), anchor='ls')
    d.text((right, base), date_text, fill=INK, font=font, anchor='rs')

    img = img.resize((CARD_W, CARD_H), Image.LANCZOS)
    return lay_paper(img, paper)


# ---------------------------------------------------------------------------
# The back of the card
# ---------------------------------------------------------------------------

def draw_back(caption, stats, paper):
    """Postcard paper, a divider, and the walk's figures on the right.

    The whole left half is left empty on purpose. That is the space for
    photographs later, so nothing is drawn into it.
    """
    S = SUPERSAMPLE
    W, H = CARD_W * S, CARD_H * S

    img = Image.new('RGB', (W, H), CREAM)
    d = ImageDraw.Draw(img)

    hair = max(1, int(1.5 * S))

    # A faint frame, echoing the border on the front.
    d.rectangle([BORDER * S, BORDER * S,
                 (CARD_W - BORDER) * S, (CARD_H - BORDER) * S],
                outline=FAINT, width=hair)

    # The divider straight down the middle, as a postcard has.
    mid = CARD_W // 2
    d.line([(mid * S, (BORDER + INSET * 0.5) * S),
            (mid * S, (CARD_H - BORDER - INSET * 0.5) * S)],
           fill=FAINT, width=hair)

    # Everything below is inside the right half only.
    rx0 = mid + INSET
    rx1 = CARD_W - BORDER - INSET

    label_font = load_font(int(19 * S))
    value_font = load_font(int(32 * S))
    spacing = 3.2 * S

    y = BORDER + INSET + 34
    heading = fit_font(d, caption, (rx1 - rx0) * S, 46 * S)
    d.text((rx0 * S, y * S), caption, fill=INK, font=heading, anchor='ls')

    rows = [
        ("distance",      say_distance(stats['metres'])),
        ("duration",      say_duration(stats['seconds'])),
        ("pauses",        str(stats['pauses'])),
        ("stood still",   say_minutes(stats['still'])),
        ("longest pause", say_minutes(stats['longest'])),
        ("date",          stats['started'].strftime('%d%m%Y')),
        ("time",          stats['started'].strftime('%H:%M') + " to "
                          + stats['finished'].strftime('%H:%M')),
    ]

    # Share the leftover height out evenly, so the rows always fit however
    # many there are.
    rows_top = y + 76
    rows_bottom = CARD_H - BORDER - INSET
    row_h = (rows_bottom - rows_top) / len(rows)

    for i, (label, value) in enumerate(rows):
        line_y = rows_top + row_h * i

        # A hairline above each row, to sit the pair on.
        d.line([(rx0 * S, line_y * S), (rx1 * S, line_y * S)],
               fill=FAINT, width=hair)

        text_y = (line_y + row_h * 0.62) * S
        draw_spaced(d, (rx0 * S, text_y), label.upper(), label_font,
                    FAINT, spacing)
        d.text((rx1 * S, text_y), value, fill=INK, font=value_font, anchor='rs')

    img = img.resize((CARD_W, CARD_H), Image.LANCZOS)
    return lay_paper(img, paper)


# ---------------------------------------------------------------------------

def load_captions():
    if os.path.exists(CAPTIONS_FILE):
        with open(CAPTIONS_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}


def safe_name(name):
    """Turn a walk's name into something safe to use as a filename.

    Accented letters are flattened to plain ones, so a name like "Vaen
    vihar" cannot produce a file that a web address chokes on later.
    """
    flat = unicodedata.normalize('NFKD', name)
    flat = flat.encode('ascii', 'ignore').decode('ascii')
    kept = "".join(c if c.isalnum() or c in " -_" else "" for c in flat)
    return kept.strip().replace(" ", "_") or "walk"


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else 'walks'
    files = (sorted(glob.glob(os.path.join(target, '*.gpx')))
             if os.path.isdir(target) else [target])
    if not files:
        print(f"No .gpx files found in {target}")
        print("Put your Strava exports there and run this again.")
        return

    walks = [prepare(f) for f in files]

    left_out = [w for w in walks if w['name'] in SKIP]
    walks = [w for w in walks if w['name'] not in SKIP]
    for w in left_out:
        print(f"Skipping {w['name']} (listed in SKIP)\n")
    if not walks:
        print("Every walk found was in the SKIP list, so nothing was drawn.")
        return

    captions = load_captions()
    os.makedirs(OUT_DIR, exist_ok=True)
    paper = paper_texture(CARD_W, CARD_H, PAPER_SEED) if PAPER else None
    missing_maps = []

    shared = None
    if SCALE_MODE == 'shared':
        shared = max(metres_per_px(w['span']) for w in walks)
        print(f"Shared scale: 1 pixel = {shared:.2f} m\n")

    gallery = []
    for walk in walks:
        mpp = shared or metres_per_px(walk['span'])
        stats = walk_stats(walk)

        # Captions are yours to write, and always lowercase.
        caption = captions.get(walk['name'], walk['name']).lower()

        stem = safe_name(walk['name'])
        front_file = f"{stem}-front.png"
        back_file = f"{stem}-back.png"

        # Buildings and roads, where this walk has a map file of its own.
        geography = None
        out_of_reach = False
        map_path = map_file_for(walk['file'], walk['name'])
        if SHOW_MAP and os.path.exists(map_path):
            buildings, roads, green = read_map(map_path, walk['lat0'])
            # Only keep what is near enough to land on the card.
            reach = max(walk['span']) * 0.8 + 400
            buildings = [b for b in buildings
                         if near_the_card(b, walk['centre'], reach)]
            roads = [r for r in roads
                     if near_the_card(r, walk['centre'], reach)]
            green = [g for g in green
                     if near_the_card(g, walk['centre'], reach)]

            # Trees are scattered across the part of the card the walk
            # occupies, then kept only where they land on green ground.
            cx, cy = walk['centre']
            half_w = (walk['span'][0] / 2) + mpp * 260
            half_h = (walk['span'][1] / 2) + mpp * 260
            trees = scatter_trees(
                green,
                (cx - half_w, cy - half_h, cx + half_w, cy + half_h),
                mpp * TREE_EVERY_PX, walk['name'])

            if buildings or roads or trees:
                geography = (buildings, roads, trees)
            else:
                # The file exists but covers somewhere else entirely.
                out_of_reach = True
                missing_maps.append(walk)
        elif SHOW_MAP:
            missing_maps.append(walk)

        draw_front(walk, mpp, caption, stats, paper, geography).save(
            os.path.join(OUT_DIR, front_file))
        draw_back(caption, stats, paper).save(
            os.path.join(OUT_DIR, back_file))

        print(f"{walk['name']}")
        print(f"  {say_distance(stats['metres'])} in "
              f"{say_duration(stats['seconds'])}, {stats['pauses']} pauses, "
              f"{say_minutes(stats['still'])} stood still")
        runs, jumps = split_on_gaps(walk)
        if jumps:
            ridden = [j for j in jumps if j['vehicle']]
            note = (f", of which {say_distance(stats['ridden'])} ridden "
                    f"and left out" if ridden else "")
            print(f"  {len(jumps)} recording gaps, drawn dashed{note}")
        print(f"  1 pixel = {mpp:.2f} m")
        if geography:
            print(f"  map: {len(geography[0])} buildings, "
                  f"{len(geography[1])} roads, {len(geography[2])} trees "
                  f"from {os.path.basename(map_path)}")
        elif out_of_reach:
            print(f"  map: {os.path.basename(map_path)} covers somewhere "
                  f"else, nothing reached this walk")
        elif SHOW_MAP:
            print(f"  map: none yet, so the ground is left plain")
        print(f"  {OUT_DIR}/{front_file} and {OUT_DIR}/{back_file}\n")

        gallery.append({
            "name": walk['name'],
            "caption": caption,
            "front": front_file,
            "back": back_file,
            "date": stats['started'].strftime('%d%m%Y'),
            "distance": say_distance(stats['metres']),
            "duration": say_duration(stats['seconds']),
            "pauses": stats['pauses'],
        })

    # Written as .js rather than .json on purpose. A browser refuses to read
    # a .json file when the page has been opened straight from your own
    # computer, so the page would sit there empty until it was on a real web
    # server. A .js file loads either way, so postcards.html works when you
    # double-click it and when it is live.
    listing = os.path.join(OUT_DIR, 'gallery.js')
    with open(listing, 'w', encoding='utf-8') as f:
        f.write("window.WALKS = ")
        json.dump(gallery, f, indent=2)
        f.write(";\n")
    print(f"Wrote {listing}, which postcards.html reads.")

    if missing_maps:
        print(f"\n{'-' * 68}")
        print(f"{len(missing_maps)} walks have no map data, so their ground "
              f"is plain yellow.")
        print("To add buildings and roads, do this once per walk:")
        print("  1. Open the link below in your browser")
        print("  2. Wait. It may take a minute, and it will look like a wall "
              "of text")
        print("  3. Save the page (Ctrl+S) with the exact filename given")
        print("  4. Put it in the walks folder and run this again")
        print(f"{'-' * 68}")
        for walk in missing_maps:
            folder = os.path.dirname(walk['file']) or "."
            want = safe_name(walk['name']) + ".geojson"
            print(f"\n{walk['name']}")
            print(f"  save as: {want}")
            print(f"  {overpass_link(walk['box'])}")


if __name__ == '__main__':
    main()
