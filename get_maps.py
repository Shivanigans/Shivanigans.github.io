"""
get_maps.py - fetch the OpenStreetMap data that each walk needs.

    python get_maps.py walks

For every walk that does not already have map data of its own, this asks
OpenStreetMap for the buildings and roads around it, and saves the answer
next to the .gpx as <walk name>.geojson. Then run the postcards again and
those walks will have geography behind them.

It asks one walk at a time with a pause in between, because Overpass is a
free service run on donations and hammering it is rude. A whole set takes
a couple of minutes.

Walks that already have their own file are skipped, so it is safe to run
this again whenever you add a walk. Nothing is ever overwritten.
"""

import os, sys, glob, time, json
import urllib.request, urllib.error

from make_postcards import load_gpx, safe_name, overpass_link

PAUSE   = 4      # seconds between requests, to be polite
TRIES   = 3      # attempts per walk before giving up
TIMEOUT = 300    # seconds to wait for one answer

# Overpass asks that tools identify themselves, so it can tell a person
# from a runaway script.
AGENT = "walk-postcards/1.0 (personal art project; one-off download)"


def bounding_box(pts):
    """The patch of the world a walk covers, as south, west, north, east."""
    return (min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts))


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:
        return answer.read()


def looks_right(raw):
    """Did we get map data back, or an error page dressed up as a reply?"""
    try:
        data = json.loads(raw)
    except ValueError:
        return False, "the reply was not readable as data"
    if "elements" not in data:
        return False, "the reply had no map data in it"
    count = len(data["elements"])
    if count == 0:
        return False, "OpenStreetMap has nothing mapped here"
    return True, f"{count} things"


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else 'walks'
    files = sorted(glob.glob(os.path.join(target, '*.gpx')))
    if not files:
        print(f"No .gpx files found in {target}")
        return

    folder = target if os.path.isdir(target) else os.path.dirname(target)
    jobs = []
    for path in files:
        name, pts = load_gpx(path)
        want = os.path.join(folder, safe_name(name) + ".geojson")
        if os.path.exists(want):
            print(f"already have  {os.path.basename(want)}")
            continue
        jobs.append((name, want, bounding_box(pts)))

    if not jobs:
        print("\nEvery walk already has its own map data. Nothing to do.")
        return

    print(f"\nFetching map data for {len(jobs)} walks, "
          f"about {len(jobs) * (PAUSE + 8) // 60 + 1} minutes.\n")

    done, failed = 0, []
    for number, (name, want, box) in enumerate(jobs, 1):
        print(f"[{number}/{len(jobs)}] {name[:48]}")
        url = overpass_link(box)

        for attempt in range(1, TRIES + 1):
            try:
                raw = fetch(url)
            except urllib.error.HTTPError as err:
                # 429 means slow down, 504 means the server is busy.
                wait = 20 * attempt
                print(f"    busy ({err.code}), waiting {wait}s "
                      f"and trying again")
                time.sleep(wait)
                continue
            except Exception as err:
                print(f"    could not reach OpenStreetMap: {err}")
                time.sleep(10 * attempt)
                continue

            ok, note = looks_right(raw)
            if not ok:
                print(f"    {note}")
                break

            with open(want, 'wb') as handle:
                handle.write(raw)
            size = os.path.getsize(want) / 1024
            print(f"    saved {os.path.basename(want)}  "
                  f"({note}, {size:.0f} KB)")
            done += 1
            break
        else:
            print(f"    gave up after {TRIES} attempts")
            failed.append(name)

        if number < len(jobs):
            time.sleep(PAUSE)

    print(f"\nDone. {done} of {len(jobs)} downloaded.")
    if failed:
        print("These did not come through, try running this again later:")
        for name in failed:
            print(f"  {name}")
    if done:
        print("\nNow run run.bat again to redraw the cards with geography.")


if __name__ == '__main__':
    main()
