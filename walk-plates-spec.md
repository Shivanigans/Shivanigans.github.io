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

**Blocks** — decoration, not data. They follow the route loosely so the plate
has some geography behind it, and they fade back so the red line stays the
thing you read. Nothing about their size means anything.

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

**Recording gaps** — Strava switching off to save battery. Not bridged, and
sorted by how far the walk got whilst it was off:

| what happened | test | drawn as |
|---|---|---|
| stood still | moved under 100 m | a pause, so it gets a block |
| walked, unrecorded | under 3 km/h | a dotted line |
| vehicle | 3 km/h or more | not drawn, not counted |

Naddi has 2 rests, 3 unrecorded walking stretches and 1 cab ride.

**Elevation** — drawn as a climb profile in the caption band, not written.
Across is distance walked, up is height. Distance walked is labelled beneath.

**Typeface** — JetBrains Mono, with a monospace fallback. It must be
installed locally for Figma to render it.

**Pause scale** — shared across every plate, set by the longest pause
anywhere, so a circle of a given size means the same duration on any plate and
the legend is true. Radius grows with the square root of duration, so area
tracks time.

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
| recording gaps | 1 | 6 |
| stretches drawn | 2 | 7 |

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

## The script

`make_plates.py` was written fresh; the original `make_fit.py` could not be
located. Run it with every walk at once, because the shared scale can only be
worked out if the script can see them all:

    python3 make_plates.py walks/*.gpx

Captions go in `captions.json`, keyed by Strava track name. Layers are
`background`, `blocks`, `path`, `pace`, `pauses`, `reversals`, `endpoints`
and `caption`; `pace` and `reversals` are hidden by default.

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

- On naddi the start dot floats clear of the path, because the first recorded
  stretch is too short to draw. Truthful, but reads as a mistake.
- Pause circles are drawn as outlines and can disappear into the red line.
  They now carry the pause data alone, so legibility matters more than it did.
- Blocks bleed off the plate edge where the route runs close to it.
- Naddi's gap 4 (78 minutes, 124 m) is classed as unrecorded walking because
  it drifted just over the 100 m threshold. It was almost certainly a long
  rest, so that threshold may want raising.
