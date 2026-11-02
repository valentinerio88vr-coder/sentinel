"""Geofence evaluation.

Simple spherical distance is accurate to ~0.5% at zone sizes we care about (<5 km),
which is far inside GPS noise. No external geo library needed.
"""
from __future__ import annotations

import json
import math

from . import db

EARTH_RADIUS_M = 6_371_000


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def zones_for(device_id: str) -> list[dict]:
    with db.read() as c:
        rows = c.execute("SELECT * FROM zones WHERE device_id = ?", (device_id,)).fetchall()
    return db.rows_to_dicts(rows)


def evaluate_point(device_id: str, lat: float, lon: float, accuracy: float | None = None) -> list[dict]:
    """Update zone membership for one fix and return transition alerts.

    A fix whose accuracy circle is larger than the zone radius is skipped: entering or
    leaving a 100 m geofence on a 400 m-accurate cell fix is noise, not an event.
    """
    transitions: list[dict] = []
    for z in zones_for(device_id):
        if accuracy is not None and accuracy > max(z["radius_m"], 50):
            continue
        dist = haversine_m(lat, lon, z["lat"], z["lon"])
        inside = dist <= z["radius_m"]
        with db.conn() as c:
            state = c.execute("SELECT inside FROM zone_state WHERE zone_id = ?", (z["id"],)).fetchone()
            was = bool(state["inside"]) if state else False
            if state is None:
                # First observation establishes the baseline without firing an alert.
                c.execute(
                    "INSERT INTO zone_state (zone_id, inside, updated_at) VALUES (?,?,?)",
                    (z["id"], int(inside), db.now()),
                )
                continue
            if inside == was:
                continue
            c.execute(
                "UPDATE zone_state SET inside = ?, updated_at = ? WHERE zone_id = ?",
                (int(inside), db.now(), z["id"]),
            )
        notify = z["notify_enter"] if inside else z["notify_exit"]
        if not notify:
            continue
        verb = "arrived at" if inside else "left"
        transitions.append({
            "zone_id": z["id"],
            "zone_name": z["name"],
            "zone_kind": z["kind"],
            "inside": inside,
            "distance_m": round(dist, 1),
            "message": f"{verb.capitalize()} {z['name']}" + (f" ({round(dist)}m from centre)" if not inside else ""),
            # Dedupe per zone+transition direction so a flapping GPS fix can't spam alerts.
            "dedupe_key": f"zone:{z['id']}:{'in' if inside else 'out'}",
        })
    return transitions
