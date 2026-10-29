#!/usr/bin/env python3
"""Smoketest gegen eine laufende LoadLog-Instanz; legt dabei SYNTHETISCHE Demodaten an.

Aufruf:  uv run --project backend python scripts/smoke_test.py http://127.0.0.1:8080 [--seed-only]
Benötigt nur die Standardbibliothek plus das Paket `loadlog` (für den Generator synthetischer Daten).
"""

import json
import sys
import urllib.error
import urllib.request
import uuid

from loadlog import synth

LADDER = [{"number": n, "shots": 5, "v0": 279.0 + (n - 1) * 7.5, "sd": 3.0 + (n % 3), "weight_gr": 180.0} for n in range(1, 6)]
SEATING = [{"number": n, "shots": 5, "v0": 292.0 + (n - 6) * 1.5, "sd": 4.5 - (n - 6), "weight_gr": 180.0} for n in range(6, 9)]


def call(base: str, method: str, path: str, body=None, raw: bytes | None = None, ctype: str | None = None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    headers = {"Content-Type": ctype or "application/json"} if data is not None else {}
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = r.read()
            return r.status, r.headers.get("content-type", ""), payload
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("content-type", ""), e.read()


def jcall(base, method, path, body=None):
    status, _, payload = call(base, method, path, body)
    assert status < 300, f"{method} {path} -> {status} {payload[:200]!r}"
    return json.loads(payload) if payload else None


def upload(base: str, zip_bytes: bytes):
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"card.zip\"\r\n"
            f"Content-Type: application/zip\r\n\r\n").encode() + zip_bytes + f"\r\n--{boundary}--\r\n".encode()
    status, _, payload = call(base, "POST", "/api/import", raw=body, ctype=f"multipart/form-data; boundary={boundary}")
    assert status == 200, (status, payload[:200])
    return json.loads(payload)


def seed(base: str) -> None:
    if jcall(base, "GET", "/api/loads"):
        print("Demodaten sind schon vorhanden, überspringe das Anlegen")
        return
    weapon = jcall(base, "POST", "/api/weapons", {"name": "Beispielwaffe", "caliber": ".308 Win", "barrel_length_mm": 650, "twist": "1:12"})
    r1 = upload(base, synth.make_zip(seed=21, specs=LADDER))
    r2 = upload(base, synth.make_zip(seed=22, specs=SEATING))
    ids = {i["number"]: i["id"] for i in r1["imported"] + r2["imported"]}
    assert len(ids) == 8, ids
    common = {"weapon_id": weapon["id"], "powder_maker": "Beispiel-Hersteller", "powder_name": "Pulver X", "bullet_maker": "Beispiel-Hersteller",
              "bullet_type": "Vollmantel", "bullet_weight_gr": 180, "coal_mm": 71.2, "primer": "Zünder Typ A", "case_maker": "Beispiel-Hülse",
              "case_firings": 2, "temperature_c": 15}
    ladder = jcall(base, "POST", "/api/loads", {**common, "name": "Beispiel-Ladeleiter", "trial_type": "ladder", "charge_gr": 42.0,
                                                "seating_depth_mm": 2.0, "seating_ref": "Ogive", "notes": "Fiktive Demodaten, keine Ladedaten: nicht nachladen"})
    seat = jcall(base, "POST", "/api/loads", {**common, "name": "Beispiel-Setztiefe", "trial_type": "seating", "charge_gr": 43.0, "notes": "Fiktive Demodaten, keine Ladedaten: nicht nachladen"})
    for n in range(1, 6):
        jcall(base, "PATCH", f"/api/series/{ids[n]}", {"load_id": ladder["id"], "charge_gr": 42.0 + 0.5 * (n - 1), "trigger_mode": "doppler"})
    for n in range(6, 9):
        jcall(base, "PATCH", f"/api/series/{ids[n]}", {"load_id": seat["id"], "seating_depth_mm": 0.5 * (n - 5), "trigger_mode": "internal"})
    jcall(base, "PUT", f"/api/series/{ids[3]}/shots/2/excluded", {"excluded": True})
    print("Demodaten angelegt:", ids)


def check(base: str) -> None:
    health = jcall(base, "GET", "/api/health")
    assert health["status"] == "ok"
    loads = jcall(base, "GET", "/api/loads")
    assert len(loads) >= 2, loads
    ladder = next(x for x in loads if x["name"] == "Beispiel-Ladeleiter")
    detail = jcall(base, "GET", f"/api/loads/{ladder['id']}")
    sid = detail["series"][0]["id"]
    ids = ",".join(str(s["id"]) for s in detail["series"])
    for path in (f"/api/charts/series/{sid}.svg", f"/api/charts/compare.svg?ids={ids}", f"/api/charts/ladder/{ladder['id']}.svg?by=charge"):
        status, ctype, payload = call(base, "GET", path)
        assert status == 200 and ctype.startswith("image/svg+xml") and payload.startswith(b"<svg"), path
    assert b"data-shot=" in call(base, "GET", f"/api/charts/series/{sid}.svg")[2], "Hover-Daten fehlen"
    bc = jcall(base, "GET", f"/api/series/{sid}")["bc"]
    st = jcall(base, "GET", f"/api/series/{sid}")["stats"]
    assert st["mip_avg"] and st["mip_min"] <= st["mip_avg"], st
    assert bc["g1"]["avg"] and 0.05 < bc["g7"]["avg"] < bc["g1"]["avg"], bc
    for path in (f"/api/reports/series/{sid}", f"/api/reports/load/{ladder['id']}", f"/api/reports/compare?ids={ids}"):
        status, ctype, payload = call(base, "GET", path)
        if health["pdf"]:
            assert status == 200 and payload.startswith(b"%PDF") and len(payload) > 5000, (path, status)
        status, _, payload = call(base, "GET", path + ("&" if "?" in path else "?") + "format=html")
        assert status == 200 and b"<svg" in payload, path
    grt = upload(base, synth.make_grtload())  # GRT-Import: beim ersten Lauf neu, danach nur noch "vorhanden"
    assert len(grt["imported"]) + grt["skipped"] == 5, grt
    if grt["imported"]:
        assert grt["load_id"] and jcall(base, "GET", f"/api/loads/{grt['load_id']}")["series_count"] == 5
    status, _, payload = call(base, "GET", "/")
    assert status == 200 and b"LoadLog" in payload, "Oberfläche fehlt"
    mm = ".".join(health["version"].split(".")[:2])
    for lang in ("de", "en"):
        for path in (f"/manual/{mm}/{lang}/", f"/manual/{lang}/"):  # versionierte Adresse und Weiterleitung der alten
            status, _, payload = call(base, "GET", path)
            assert status == 200 and b"LoadLog" in payload, f"Handbuch {lang} fehlt ({path})"
    status, ctype, payload = call(base, "GET", f"/api/export/load/{ladder['id']}.csv")
    assert status == 200 and ctype.startswith("text/csv") and payload.count(b"\n") > 5, "CSV-Export fehlt"
    status, _, payload = call(base, "GET", "/api/system/backup")
    assert status == 200 and payload.startswith(b"SQLite format 3"), "Sicherung fehlt"
    print(f"Smoketest OK (PDF: {health['pdf']}, Version {health['version']})")


if __name__ == "__main__":
    url = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080").rstrip("/")
    seed(url)
    if "--seed-only" not in sys.argv:
        check(url)
