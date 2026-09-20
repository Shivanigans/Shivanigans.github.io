# Walk plates — decisions and measurements

A gallery of under 10 Strava walks, each drawn as one designed plate with a
hand-written caption. Plates are finished in Figma; the script produces
layered SVG.

## Design reference

| element | value |
|---|---|
| ground | `#f9e278` flat yellow |
| blocks | `#f3b568` pale orange, abstract, behind the path |
| path | `#e13a3d` red, heavy weight |
| endpoints | solid dots at start and end |
| caption | `#555555` mono grey, beneath the plate |

## Decisions

**Frame** — derived per walk, not fixed. The script multiplies the walk's
footprint by the shared scale and adds margins plus the caption band.
Orientation falls out of the footprint rather than being chosen. The earlier
1350x1080 frame is dropped.

**Scale** — one shared metres-per-pixel across every plate, so plate size
itself encodes distance. Short walks print small and that is the intent.

**No minimum plate size.** A 400 m walk prints at roughly 352 x 459 px beside
naddi's 1528 x 1347. The size difference is part of what the gallery says.

**Blocks** — real building footprints from OpenStreetMap where map data is
supplied, otherwise abstract shapes following the route. Either way they are
ground, not data: nothing about their size means anything. Roads come through
as their own layer so they can be switched off.

**Wilderness** — scattered conifers on wooded ground, in their own layer
beneath the buildings. Not an outline: the forest here is a single 290 km2
regional polygon, far larger than any one walk, so its shape says nothing.
What is useful is where its edge crosses the frame, and scattering trees
inside it shows exactly that — the wood stops where the town starts.

They were originally one-per-pause sized by duration, but that could not be
read: a random size jitter reversed the ordering within a plate (a 2.3 minute
pause drew larger than a 3.4 minute one), and per-plate scaling broke it
across plates (naddi's 15 minute pause drew larger than mcleodganj's 39
minute one). Pauses are carried by the circles, which are on a shared scale
and have a legend.

Each walk's blocks are seeded from its name, so a walk always draws the same
ground rather than reshuffling on every run.

**Pause rule** — displacement-based: stayed within 10 m for at least 2
minutes. Chosen over a speed rule because on a 21 min/km uphill walk, slow
climbing and standing still are indistinguishable by speed.

**Reversals** — all kept, none filtered. Switchbacks are part of what a steep
walk is.

**Recording gaps** — Strava switching off to save battery. Where recording
stopped but the walking continued, the two ends are simply joined and the
path runs on as one line, because a straight join is all the data supports.
Only a ridden stretch breaks the route, drawn as a long dash.

So the path is continuous as the GPX recorded it, and the single dashed line
is the only place the journey was not on foot. A ridden stretch is still
excluded from the distance walked.

A speed rule sorts them as a first guess — under 100 m means standing still,
under 3 km/h means walking unrecorded, faster means a vehicle — but it is only
a guess, and it got naddi wrong. A cab crawling through a hill town looks like
walking, and slow walking across a long gap looks like a cab. `VEHICLE_GAPS`
in the script overrides it by walk name and gap number, which the script
prints on every run.

**Elevation** — drawn as a climb profile in the caption band, not written.
Across is distance walked, up is height. Distance walked is labelled beneath.

**Typeface** — JetBrains Mono, with a monospace fallback. It must be
installed locally for Figma to render it.

**Pause scale** — shared across every plate, set by the longest pause
anywhere, so circles are comparable between plates. Radius grows with the
square root of duration, so area tracks time. No legend: the reading it
offered felt more precise than the underlying pause detection warrants.

**Captions** — written by hand, never generated.

## Measured walks

Projection is local equirectangular; GPS spikes above 6 m/s dropped.

| | Walk to mcleodganj | Walk to naddi |
|---|---|---|
| Strava type | walking | hiking |
| points | 5,380 (3 spikes) | 15,389 (23 spikes) |
| distance walked | 4.20 km | 10.74 km |
| duration | 130 min | 427 min |
| footprint | 844 x 1537 m | 2331 x 1011 m |
| orientation | portrait (0.55) | landscape (2.31) |
| elevation range | 1617-1768 m | 1767-1968 m |
| elevation gain | 177 m | 416 m |
| moving pace | 21.4 min/km | 23.4 min/km |
| pauses | 6 | 18 |
| reversals | 23 | 74 |
| plate size | 613 x 1300 px | 1530 x 1158 px |
| recording gaps | 1 | 6, of which 1 ridden |
| stretches drawn | 1 | 2 |
| map data | 264 buildings, 174 roads | 762 buildings, 345 roads |
| conifers drawn | 33 | 123 |

Naddi sets the ceiling for the shared scale, at 1.727 m per pixel.

Three earlier figures here were measured before the GPS spike filter ran and
were wrong. Naddi's footprint was given as 3140 x 2370 m; four bad fixes at
09:23 lie up to 2.7 km off the route and inflated the box. The true footprint
is 2331 x 1011 m, which a percentile check agrees with.

Naddi's elevation was given as 1767-2921 m with 1494 m of climb. The 2921 m
readings are those same bad fixes. The walk stays between 1767 and 1968 m and
climbs 416 m, so it is rolling ground above McLeod Ganj rather than a major
ascent.

Distance was given as 12.26 km, which counted the cab ride and the rests as
route. 10.74 km is what was walked.

## Map data

Each walk can have real geography behind it. The script looks for a
`.geojson` file beside the GPX with the same name; if it is not there, it
prints a ready-made overpass-turbo link for that walk's bounding box.

Open the link, let the query run, then Export → GeoJSON and save the file
next to the GPX. No coding, and no network needed on later runs. Buildings
are drawn into the `blocks` layer, roads into `roads`.

The walk and its map data are projected against the same reference latitude,
so buildings sit where the walk actually passed them. Both layers are clipped
to the picture area, because map data runs past the walk in every direction
and would otherwise carry on through the caption band.

One download covers a whole area and several walks with it, so a file named
`area.geojson` beside the walks serves any of them. A walk with its own
`<name>.geojson` uses that instead.

Coverage of wilderness is thin. The query asks for woods, scrub, grassland,
water, farmland, nature reserves and protected areas, across ways and
relations. For Dharamshala that returns 3 farmland, 2 water and one enormous
`natural=wood` relation of 290 km2 with 7532 points. Nothing else on those
hillsides is mapped at all.

That one polygon is still useful, because its boundary crosses both frames:
naddi's western corners fall inside it and its eastern ones do not, and 77%
of that walk is within it. So it separates forest from town, which is the
distinction worth drawing.

Coverage is uneven and that is kept, not filled. On mcleodganj, OpenStreetMap
has 459-859 data points per band across the northern third and 11-55 across
the southern two-thirds, because that stretch is forested hillside with
nothing mapped on it. The plate is left empty there: the walk goes from empty
ground into a dense town, and showing that is the point.

## The script

`make_plates.py` was written fresh; the original `make_fit.py` could not be
located. Run it with every walk at once, because the shared scale can only be
worked out if the script can see them all:

    python3 make_plates.py walks/*.gpx

Captions go in `captions.json`, keyed by Strava track name. Layers are
`background`, `blocks`, `pace`, `gaps`, `path`, `pauses`, `reversals`,
`endpoints`, `caption`, `elevation` and `figures`; `pace` and `reversals` are
hidden by default.

Margins are worked out as a share of the plate (7%) held between a floor and a
ceiling, rather than fixed, because plates now range from a few hundred pixels
to over 1500. The caption band is measured from its actual contents so the
legend cannot be clipped off a short plate.

## The gallery

`walks.html` shows every plate and replays a walk from start to end when
clicked, drawing each recorded stretch in turn. Plate widths stay
proportional on screen, so the shared scale still reads. It loads
`plates/gallery.json`, which the script writes.

## Open

- Start and end are drawn as identical solid dots, so there is no way to tell
  which is which. On naddi they also sit close together.
- Pause circles are drawn as outlines and can disappear into the red line.
  They now carry the pause data alone, so legibility matters more than it did.
- Blocks bleed off the plate edge where the route runs close to it.
- Naddi's gap 4 (78 minutes, 124 m) is classed as unrecorded walking because
  it drifted just over the 100 m threshold. It was almost certainly a long
  rest, so that threshold may want raising.
