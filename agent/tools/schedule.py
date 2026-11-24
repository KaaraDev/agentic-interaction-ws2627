"""Checks a train connection against the appointments of the same day, in code.

The model is unreliable at comparing times and places (it called a train that leaves during a
meeting "no conflict"), so the runtime does it and the model only reports the result.

Rules for one connection origin -> destination, departure..arrival:
- an in-person appointment overlapping the journey is a conflict;
- the last in-person appointment before departure must be at the origin (else you are elsewhere);
- after arrival you are at the destination: the next in-person appointment elsewhere is a conflict
  if it starts sooner than the trip back could take (the journey's own duration), otherwise a
  warning that a trip back is needed;
- online appointments never block travel; overlapping one is a warning.
"""
import re

ONLINE = 'online'
UNKNOWN = 'unknown'
_UNIVERSITY_ROOM = re.compile(r'^\s*o\d{2}\s*/', re.I)  # e.g. O27/3302: Ulm University buildings


def place_of(location) -> str:
    """'ulm', 'muenchen', 'online' or 'unknown' for an appointment's location text."""
    text = str(location or '').strip().lower()
    if not text or ONLINE in text or 'remote' in text or 'video' in text:
        return ONLINE
    if any(name in text for name in ('muenchen', 'münchen', 'munich')):
        return 'muenchen'
    if 'ulm' in text or _UNIVERSITY_ROOM.match(text):
        return 'ulm'
    return UNKNOWN


def _minutes(hhmm) -> int | None:
    match = re.fullmatch(r'\s*(\d{1,2}):(\d{2})\s*', str(hhmm or ''))
    return int(match[1]) * 60 + int(match[2]) if match else None


def _label(event: dict) -> str:
    return f"{event.get('title', 'appointment')} {event.get('start')}-{event.get('end')} ({event.get('location') or ONLINE})"


def appointments(events) -> list[dict]:
    """Timed appointments with minutes and place, sorted by start. All-day entries do not block travel."""
    result = []
    for event in events or []:
        if not isinstance(event, dict) or event.get('all_day'):
            continue
        start, end = _minutes(event.get('start')), _minutes(event.get('end'))
        if start is None or end is None:
            continue
        result.append({**event, '_start': start, '_end': end, '_place': place_of(event.get('location'))})
    return sorted(result, key=lambda e: e['_start'])


def _trip_back(connections, after_min: int, before_min: int):
    """None if there is no data; else the connections leaving after `after_min` and arriving by `before_min`."""
    if connections is None:
        return None
    fitting = []
    for c in connections:
        dep, arr = _minutes(c.get('departure')), _minutes(c.get('arrival'))
        if dep is not None and arr is not None and dep >= after_min and arr <= before_min:
            fitting.append(c)
    return fitting


def check_connection(connection: dict, origin: str, destination: str, events, return_trains=None) -> dict:
    """{'fits': bool, 'conflicts': [...], 'warnings': [...], 'notes': [...]} for one connection.

    return_trains(from_city, to_city) -> list of connections, or None if there is no data: used to
    check whether a later appointment back in another city can still be reached by train."""
    dep, arr = _minutes(connection.get('departure')), _minutes(connection.get('arrival'))
    if dep is None or arr is None:
        return {"fits": None, "conflicts": [], "warnings": ["departure or arrival time unknown"], "notes": []}
    if arr < dep:  # past midnight
        arr += 24 * 60
    conflicts, warnings, notes = [], [], []
    apps = appointments(events)

    for event in apps:
        if event['_start'] < arr and event['_end'] > dep:  # overlaps the journey
            if event['_place'] == ONLINE:
                warnings.append(f"overlaps the online appointment {_label(event)}: join from the train")
            else:
                conflicts.append(f"overlaps {_label(event)}: you are on the train")

    in_person = [e for e in apps if e['_place'] != ONLINE]
    before = [e for e in in_person if e['_end'] <= dep]
    if before and before[-1]['_place'] not in (origin, UNKNOWN):
        conflicts.append(f"you are in {before[-1]['_place']} until {before[-1]['end']} "
                         f"({before[-1].get('title')}), not in {origin}")
    elif before:
        notes.append(f"leaves {dep - before[-1]['_end']} min after {_label(before[-1])} ends")

    after = [e for e in in_person if e['_start'] >= arr]
    for event in after:
        if event['_place'] == destination:
            notes.append(f"arrives {event['_start'] - arr} min before {_label(event)}")
            break
        if event['_place'] == UNKNOWN:
            notes.append(f"next appointment {_label(event)} has an unknown location")
            break
        travel = arr - dep
        if event['_start'] - arr < travel:
            conflicts.append(f"you would be in {destination} and miss {_label(event)} in {event['_place']}")
        elif return_trains is None:
            warnings.append(f"{_label(event)} is in {event['_place']}: you need a trip back to "
                            f"{event['_place']} before {event['start']} (not checked)")
        else:
            back = _trip_back(return_trains(destination, event['_place']), arr, event['_start'])
            if back is None:
                conflicts.append(f"{_label(event)} is in {event['_place']}, and there is no train data for "
                                 f"the trip back {destination}->{event['_place']} that day")
            elif not back:
                conflicts.append(f"{_label(event)} is in {event['_place']}: no train back from {destination} "
                                 f"arrives before {event['start']}")
            else:
                notes.append(f"trip back possible for {_label(event)}: "
                             + ', '.join(f"{c.get('train')} {c.get('departure')}-{c.get('arrival')}" for c in back))
        break

    for event in apps:  # only when it is close: more notes cost tokens with every later step
        if event['_place'] == ONLINE and 0 <= event['_start'] - arr <= 60:
            notes.append(f"arrives {event['_start'] - arr} min before the online appointment {_label(event)}")
            break

    return {"fits": not conflicts, "conflicts": conflicts, "warnings": warnings, "notes": notes}
