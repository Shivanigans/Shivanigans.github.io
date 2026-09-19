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
| footprint | 845 x 1539 m | 3140 x 2370 m |
| orientation | portrait (0.55) | landscape (1.32) |
| elevation gain | 177 m | 1,494 m |
| moving pace | 21.4 min/km | 23.4 min/km |
| pauses (10 m / 2 min) | 5 | 16 |

Naddi sets the ceiling for the shared scale. At 2.33 m/px its long side fills
1350 px and mcleodganj comes out 543 x 991 px.

## Open

- `make_fit.py` is not yet in this repository.
- The script's existing distance (3.8 km) and pause figures (9 pauses,
  13 min) could not be reproduced from the GPX; the smoothing step likely
  explains the distance, the pause gap is unexplained.
- Whether margins and the caption band stay fixed in pixels or scale with
  the plate, now that plates vary widely in size.
