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

**Blocks** — derived from the walk's own pauses, one per pause, sized by
duration. No two backgrounds repeat.

**Pause rule** — displacement-based: stayed within 10 m for at least 2
minutes. Chosen over a speed rule because on a 21 min/km uphill walk, slow
climbing and standing still are indistinguishable by speed.

**Reversals** — all kept, none filtered. Switchbacks are part of what a steep
walk is.

**Captions** — written by hand, never generated.

## Measured walks

Projection is local equirectangular; GPS spikes above 6 m/s dropped.

| | Walk to mcleodganj | Walk to naddi |
|---|---|---|
| Strava type | walking | hiking |
| points | 5,380 (3 spikes) | 15,389 (23 spikes) |
| distance | 4.17 km | 12.10 km |
| duration | 130 min | 427 min |
| footprint | 844 x 1537 m | 2331 x 1011 m |
| orientation | portrait (0.55) | landscape (2.31) |
| elevation gain | 177 m | 1,494 m |
| moving pace | 21.4 min/km | 23.4 min/km |
| pauses (10 m / 2 min) | 5 | 16 |
| reversals | 23 | 74 |
| plate size | 613 x 1112 px | 1530 x 914 px |

Naddi sets the ceiling for the shared scale, at 1.727 m per pixel.

An earlier note here gave naddi's footprint as 3140 x 2370 m. That was
measured before the GPS spike filter ran. Four bad fixes at 09:23 fly up to
2.7 km from the walk, inflating the box; the true footprint is 2331 x 1011 m,
which a percentile check agrees with independently.

## The script

`make_plates.py` was written fresh; the original `make_fit.py` could not be
located. Run it with every walk at once, because the shared scale can only be
worked out if the script can see them all:

    python3 make_plates.py walks/*.gpx

Captions go in `captions.json`, keyed by Strava track name. Layers are
`background`, `blocks`, `path`, `pace`, `pauses`, `reversals`, `endpoints`
and `caption`; `pace` and `reversals` are hidden by default.

Margins and the caption band are worked out as a share of the plate (7% and
11%) held between a floor and a ceiling, rather than fixed, because plates now
range from a few hundred pixels to over 1500. Setting each pair's floor and
ceiling to the same number restores fixed behaviour.

## Open

- Naddi has six recording gaps over 30 seconds, one of 78 minutes and one
  covering 1444 m. The path currently bridges these with straight lines,
  which read as walked route but were not.
- Whether pause circles should sit on the path or be offset; they currently
  overlap it and can read as artefacts.
