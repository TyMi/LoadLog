"""Fehlerfälle aus dem unabhängigen Review: kaputte Eingaben dürfen die Anwendung nie dauerhaft beschädigen."""

import io
import sqlite3
import zipfile
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from loadlog import importer, report, stats, synth
from loadlog.api import create_app
from loadlog.db import Database, NotFound
from loadlog.grt import GrtError, parse_grtload
from loadlog.models import Series, Shot, TrackPoint


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "t.sqlite3"))


def grt_with(shots_xml: str) -> bytes:
    return (
        '<?xml version="1.0"?><GordonsReloadingTool><InnerBallistikInput><projectile>'
        '<input name="mp" value="10" unit="g" type="decimal"/></projectile><appendix><Measurement>'
        f'<charge name="Series 1" value="0.0026" menu="V0">{shots_xml}</charge></Measurement></appendix>'
        "</InnerBallistikInput></GordonsReloadingTool>"
    ).encode()


GOOD = '<shot V0="300" note="01-01-2030 10:00:00"/>'


@pytest.mark.parametrize("bad_v0", ["inf", "-inf", "nan", "0", "-5", "99999", "abc"])
def test_grt_drops_shots_with_implausible_v0(bad_v0):
    res = parse_grtload(grt_with(GOOD + f'<shot V0="{bad_v0}" note="01-01-2030 10:01:00"/>'))
    assert len(res.series[0].shots) == 1
    assert any("übersprungen" in w or "verworfen" in w for w in res.warnings)


def test_grt_garbage_track_is_ignored_with_warning():
    res = parse_grtload(grt_with('<shot V0="300" note="01-01-2030 10:00:00"><track time="a" velo="1" dist="2"/></shot>'))
    assert res.series[0].shots[0].track == [] and any("Track" in w for w in res.warnings)
    res = parse_grtload(grt_with('<shot V0="300" note="01-01-2030 10:00:00"><track time="1" velo="inf" dist="2"/></shot>'))
    assert res.series[0].shots[0].track == []


def test_non_finite_values_never_break_the_api(client):
    j = client.post("/api/import", files={"file": ("x.grtload", grt_with(GOOD + '<shot V0="inf" note="01-01-2030 10:01:00"/>'))}).json()
    assert len(j["imported"]) == 1
    sid = j["imported"][0]["id"]
    for path in ("/api/series", f"/api/series/{sid}", "/api/loads", f"/api/charts/series/{sid}.svg"):
        assert client.get(path).status_code == 200, path
    only_bad = grt_with('<shot V0="nan" note="01-01-2030 10:00:00"/>')
    assert client.post("/api/import", files={"file": ("y.grtload", only_bad)}).status_code == 400


def test_sanity_check_on_shots():
    base = dict(number=1, taken_at=datetime(2030, 1, 1), weight_g=10.0, distances_m=[5.0], velocities_ms=[300.0], energy0_j=1.0,
                energies_j=[1.0], power_factor=None, signal_strength=None)
    assert Shot(v0_ms=300.0, **base).is_sane()
    assert not Shot(v0_ms=float("nan"), **base).is_sane()
    assert not Shot(v0_ms=300.0, **{**base, "velocities_ms": [float("inf")]}).is_sane()
    assert not Shot(v0_ms=300.0, track=[TrackPoint(0.0, float("nan"), 0.0, None)], **base).is_sane()
    assert not Shot(v0_ms=0.0, **base).is_sane()


def test_one_oversized_file_only_skips_that_file(client):
    buf = io.BytesIO(synth.make_zip(seed=5))
    with zipfile.ZipFile(buf, "a") as zf:
        zf.writestr("LBR/SR0009/SR0009 Report.csv", b"x" * (importer.MAX_FILE_BYTES + 1))
    j = client.post("/api/import", files={"file": ("sd.zip", buf.getvalue())}).json()
    assert len(j["imported"]) == 3 and any(w["code"] == "file_too_large" and "zu groß" in w["message"] for w in j["warnings"])


def test_oversized_file_in_folder_import_warns_too(tmp_path, monkeypatch):
    synth.write_sd_card(tmp_path, seed=3)
    monkeypatch.setattr(importer, "MAX_FILE_BYTES", 10)
    with pytest.raises(importer.ImportFailure):  # alle Dateien zu groß: nichts importierbar
        importer.import_dir(tmp_path)
    monkeypatch.setattr(importer, "MAX_FILE_BYTES", 5 * 1024 * 1024)
    assert importer.import_dir(tmp_path).warnings == []


def test_import_is_all_or_nothing(tmp_path):
    db = Database(tmp_path / "a.sqlite3")
    good = importer.import_zip(synth.make_zip(seed=7)).series[0]
    dup_numbers = importer.import_zip(synth.make_zip(seed=8)).series[1]
    dup_numbers.shots.append(dup_numbers.shots[0])  # gleiche Schussnummer zweimal -> UNIQUE-Fehler mitten im Import
    with pytest.raises(sqlite3.IntegrityError):
        db.import_batch([good, dup_numbers], load_data={"name": "Neu"})
    assert db.list_series_ids() == [] and db.list_loads() == []  # weder Serie noch Laborierung übrig
    db.import_batch([good], load_data={"name": "Neu"})
    assert len(db.list_series_ids()) == 1 and len(db.list_loads()) == 1


def test_import_batch_does_not_create_empty_load_for_known_series(tmp_path):
    db = Database(tmp_path / "b.sqlite3")
    s = importer.import_zip(synth.make_zip(seed=7)).series
    db.import_batch(s, load_data={"name": "L"})
    load_id, saved = db.import_batch(s, load_data={"name": "L2"})
    assert load_id is None and not any(new for _, new in saved) and len(db.list_loads()) == 1


@pytest.mark.parametrize("path,body", [
    ("/api/loads/1", {"name": None}), ("/api/loads/1", {"trial_type": None}), ("/api/weapons/1", {"name": None}),
])
def test_put_null_for_required_fields_is_422(client, path, body):
    client.post("/api/loads", json={"name": "L"})
    client.post("/api/weapons", json={"name": "W"})
    assert client.put(path, json=body).status_code == 422
    assert client.post("/api/loads", json={"name": "X", "trial_type": None}).status_code == 422


def test_huge_ids_give_404_or_422_not_500(client):
    big = 99999999999999999999
    assert client.get(f"/api/series/{big}").status_code == 404
    assert client.get(f"/api/loads/{big}").status_code == 404
    assert client.get(f"/api/compare?ids={big}").status_code == 422
    assert client.get("/api/charts/compare.svg?ids=0").status_code == 422
    assert client.delete(f"/api/series/{big}").status_code == 404


def test_weight_override_has_a_realistic_minimum(client):
    sid = client.post("/api/import", files={"file": ("s.zip", synth.make_zip(seed=5))}).json()["imported"][0]["id"]
    assert client.patch(f"/api/series/{sid}", json={"weight_override_g": 1e-300}).status_code == 422
    assert client.patch(f"/api/series/{sid}", json={"weight_override_g": 0.5}).status_code == 200


def test_power_factor_follows_weight_override(tmp_path):
    db = Database(tmp_path / "c.sqlite3")
    sid = db.save_series(importer.import_zip(synth.make_zip(seed=5)).series[0])[0]
    base = db.get_series(sid).shots[0]
    db.update_series(sid, {"weight_override_g": base.weight_g * 2})
    over = db.get_series(sid).shots[0]
    assert over.power_factor == pytest.approx(base.power_factor * 2)
    assert over.mip == pytest.approx(base.mip * 2) and over.energy0_j == pytest.approx(base.energy0_j * 2)


def test_report_shows_bc_when_only_g7_is_available(monkeypatch):
    db = Database(":memory:")
    sid = db.save_series(importer.import_zip(synth.make_zip(seed=5)).series[0])[0]
    only_g7 = {"g1": {"n": 0, "avg": None, "sd": None}, "g7": {"n": 3, "avg": 0.25, "sd": None}}
    monkeypatch.setattr(report, "series_bc", lambda shots: only_g7)
    html = report.series_report(db.get_series(sid, with_track=True), lang="en")
    assert "G7: 0.250" in html


def test_migration_from_schema_2_adds_weight_override(tmp_path, legacy_schema):
    path = tmp_path / "v2.sqlite3"
    con = sqlite3.connect(path)
    con.executescript(legacy_schema().replace("weight_override_g REAL, ", ""))
    con.execute("PRAGMA user_version = 2")
    con.execute("INSERT INTO series (number, name, device_id, source_key, imported_at) VALUES (1,'A','X','k','2030-01-01')")
    con.commit()
    con.close()
    db = Database(path)
    assert db.get_series(1).weight_override_g is None and db.get_series(1).name == "A"
    db.update_series(1, {"weight_override_g": 11.5})
    assert Database(path).get_series(1).weight_override_g == 11.5


def test_default_host_is_loopback(monkeypatch):
    import loadlog.__main__ as m

    seen = {}
    monkeypatch.delenv("LOADLOG_HOST", raising=False)
    monkeypatch.setattr(m.uvicorn, "run", lambda app, **kw: seen.update(kw))
    monkeypatch.setattr(m, "create_app", lambda: None)
    m.main()
    assert seen["host"] == "127.0.0.1"


def test_stats_helper_unused_import_guard():
    assert stats.compute([]).n == 0 and Series(1, []).shots == []


def test_errors_carry_code_params_and_german_fallback(client):
    r = client.get("/api/charts/compare.svg?ids=1,2,3," + ",".join(["9"] * 70))
    d = r.json()["detail"]
    assert r.status_code == 422 and d["code"] == "ids_count" and d["params"] == {"max": 60} and "Serien" in d["message"]
    r = client.get("/api/series/99999")
    assert r.status_code == 404 and r.json()["detail"]["code"] == "not_found"
    r = client.post("/api/import", files={"file": ("x.zip", b"kein zip")})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "zip_invalid"
    r = client.post("/api/import", files={"file": ("x.grtload", b"<!DOCTYPE x><GordonsReloadingTool/>")})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "grt_doctype"
    r = client.get("/api/reports/series/1?lang=xx")
    assert r.json()["detail"]["code"] == "bad_lang" and r.json()["detail"]["params"] == {"lang": "xx"}


def test_nested_warning_reason_is_structured():
    from loadlog.csvio import CsvError
    from loadlog.messages import Note, note_json, reason

    n = Note("series_skipped", label=Note("series_label", no=7), reason=reason(CsvError("csv_no_series")))
    assert str(n) == "Serie 7 übersprungen: Report ohne Serien-Nr."
    d = n.as_dict()
    assert d["params"]["label"]["code"] == "series_label" and d["params"]["reason"]["code"] == "csv_no_series"
    assert note_json("einfach")["code"] == "generic"


# ---- V2: Serie in mehreren Laborierungen, Duplikate zwischen SD-Karte und GRT ----
def _grt_and_sd_copy():
    """Dieselben Serien einmal als GRT (gerundet, ohne Geräte-ID) und als SD-Karten-Kopie (genauer, mit Geräte-ID)."""
    import copy

    from loadlog.grt import parse_grtload

    grt = parse_grtload(synth.make_grtload()).series[:3]
    sd = copy.deepcopy(grt)
    for i, s in enumerate(sd):
        s.device_id = "LBR-0000001"
        s.number = 10 + i
        s.name = None
        for sh in s.shots:
            sh.v0_ms += 0.4  # GRT rundet auf 1 m/s
            sh.signal_strength = 4
    return grt, sd


def test_series_can_live_in_several_loads(db):
    sid, _ = db.save_series(synth_series(1))
    a, b = db.create_load({"name": "Ladeleiter"}), db.create_load({"name": "Haupt"})
    db.update_series(sid, {"load_ids": [a]})
    db.add_series_to_load(sid, b)
    db.add_series_to_load(sid, b)  # doppelt ist harmlos
    assert db.get_series(sid).load_ids == [a, b] and db.get_series(sid).load_id == a
    assert db.list_series_ids(load_id=a) == [sid] == db.list_series_ids(load_id=b)
    assert db.list_series_ids(unassigned=True) == []
    db.remove_series_from_load(sid, a)
    assert db.get_series(sid).load_ids == [b] and db.list_series_ids(load_id=a) == []
    db.delete_load(b)  # Serie bleibt, ist wieder unzugeordnet
    assert db.get_series(sid).load_ids == [] and db.list_series_ids(unassigned=True) == [sid]
    with pytest.raises(NotFound):
        db.remove_series_from_load(sid, a)
    with pytest.raises(NotFound):
        db.add_series_to_load(sid, 999)


def synth_series(seed):
    from loadlog.importer import import_zip

    return import_zip(synth.make_zip(seed=seed)).series[0]


def test_deleting_series_removes_links_only(db):
    sid, _ = db.save_series(synth_series(2))
    lid = db.create_load({"name": "L"})
    db.add_series_to_load(sid, lid)
    db.delete_series(sid)
    assert db.list_series_ids(load_id=lid) == [] and db.get_load(lid)["name"] == "L"


def test_migration_v3_moves_load_id_into_link_table(tmp_path, legacy_schema):
    path = tmp_path / "v3.sqlite3"
    con = sqlite3.connect(path)
    con.executescript(legacy_schema())
    con.execute("PRAGMA user_version = 3")
    con.execute("INSERT INTO loads (name, trial_type, created_at) VALUES ('L','single','2030-01-01')")
    con.execute("INSERT INTO series (load_id, number, device_id, source_key, imported_at) VALUES (1,1,'X','k1','2030-01-01')")
    con.execute("INSERT INTO series (number, device_id, source_key, imported_at) VALUES (2,'X','k2','2030-01-01')")
    con.commit()
    con.close()
    db = Database(path)
    assert db.get_series(1).load_ids == [1] and db.get_series(2).load_ids == []
    assert db.list_series_ids(load_id=1) == [1] and db.list_series_ids(unassigned=True) == [2]
    db.add_series_to_load(2, 1)
    assert Database(path).list_series_ids(load_id=1) == [1, 2]  # zweites Öffnen migriert nicht erneut


def test_sd_card_after_grt_upgrades_series_and_keeps_user_data(db):
    grt, sd = _grt_and_sd_copy()
    _, saved = db.import_batch(grt, load_data={"name": "Aus GRT"})
    sid = saved[0][0]
    lid = db.get_series(sid).load_id
    db.update_series(sid, {"name": "Meine Notiz", "weight_override_g": 11.0})
    db.set_shot_excluded(sid, 2, True)
    events: list = []
    _, saved2 = db.import_batch(sd, events=events)
    assert [new for _, new in saved2] == [False, False, False] and saved2[0][0] == sid
    assert [e[0] for e in events] == ["upgraded"] * 3
    rec = db.get_series(sid)
    assert rec.device_id == "LBR-0000001" and rec.number == 10  # genauere Messdaten der Karte
    assert rec.name == "Meine Notiz" and rec.weight_override_g == 11.0 and rec.load_ids == [lid]  # Eingaben bleiben
    assert [s.excluded for s in rec.shots][1] is True
    assert rec.shots[0].signal_strength == 4
    assert len(db.list_series_ids()) == 3  # keine doppelten Serien
    events.clear()
    db.import_batch(sd, events=events)  # nochmal: gleicher Quellschlüssel, nichts zu melden
    assert events == [] and len(db.list_series_ids()) == 3


def test_grt_after_sd_card_is_reported_as_duplicate(db):
    grt, sd = _grt_and_sd_copy()
    db.import_batch(sd)
    events: list = []
    load_id, saved = db.import_batch(grt, load_data={"name": "Aus GRT"}, events=events)
    assert load_id is None  # keine neue Laborierung, wenn nichts Neues dabei ist
    assert [e[0] for e in events] == ["duplicate"] * 3 and not any(new for _, new in saved)
    assert db.list_loads() == [] and len(db.list_series_ids()) == 3
    assert db.get_series(saved[0][0]).device_id == "LBR-0000001"  # die genauere SD-Serie bleibt unverändert


def test_different_series_are_not_duplicates(db):
    grt, sd = _grt_and_sd_copy()
    db.import_batch(sd)
    grt[0].shots[0].v0_ms += 30  # andere Messwerte
    grt[1].shots = grt[1].shots[:-1]  # andere Schusszahl
    for sh in grt[2].shots:
        sh.taken_at += timedelta(minutes=5)  # anderer Zeitpunkt
    _, saved = db.import_batch(grt)
    assert all(new for _, new in saved)


def test_api_import_reports_duplicates_and_series_loads(client):

    r1 = client.post("/api/import", files={"file": ("g.grtload", synth.make_grtload())}).json()
    assert len(r1["imported"]) == 5 and r1["load_id"]
    r2 = client.post("/api/import", files={"file": ("g.grtload", synth.make_grtload())}).json()
    assert r2["skipped"] == 5 and r2["imported"] == []  # gleicher Quellschlüssel: still übersprungen
    sid = r1["imported"][0]["id"]
    other = client.post("/api/loads", json={"name": "Haupt"}).json()["id"]
    d = client.put(f"/api/series/{sid}/loads/{other}").json()
    assert d["load_ids"] == [r1["load_id"], other] and d["load_id"] == r1["load_id"]
    detail = client.get(f"/api/series/{sid}").json()
    assert [x["id"] for x in detail["loads"]] == [r1["load_id"], other]
    assert any(s["id"] == sid for s in client.get(f"/api/loads/{other}").json()["series"])
    assert client.patch(f"/api/series/{sid}", json={"load_ids": [other]}).json()["load_ids"] == [other]
    assert client.patch(f"/api/series/{sid}", json={"load_id": None}).json()["load_ids"] == []
    assert client.patch(f"/api/series/{sid}", json={"load_id": other}).json()["load_ids"] == [other]
    assert client.delete(f"/api/series/{sid}/loads/{other}").json()["load_ids"] == []
    assert client.delete(f"/api/series/{sid}/loads/{other}").status_code == 404
    assert client.put(f"/api/series/{sid}/loads/99999").status_code == 404
    assert client.get(f"/api/reports/series/{sid}?format=html&load_id={other}").status_code == 200


# ---- Eingabehärtung: Upload-Länge, Parser, Berichte ----

@pytest.mark.parametrize("path", ["/api/import", "/api/system/restore"])
def test_upload_without_content_length_is_rejected(client, path):
    def chunks():
        yield b"x" * 10

    r = client.post(path, content=chunks(), headers={"content-type": "multipart/form-data; boundary=b"})
    assert r.status_code == 411 and r.json()["detail"]["code"] == "length_required"


def test_pdf_report_never_fetches_external_resources(tmp_path):
    pytest.importorskip("weasyprint")
    if not report.pdf_available():
        pytest.skip("WeasyPrint/Pango fehlt")
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"not an image")
    html = f'<html><body><img src="file://{secret}"><img src="http://127.0.0.1:9/x.png"><p>ok</p></body></html>'
    assert report.html_to_pdf(html).startswith(b"%PDF")  # Fehler beim Laden werden zu Warnungen, nicht zu Zugriffen


def test_pdf_fetcher_rejects_non_data_urls(monkeypatch):
    pytest.importorskip("weasyprint")
    import weasyprint

    seen = {}
    real = weasyprint.HTML

    class Spy(real):
        def __init__(self, *a, url_fetcher=None, **kw):
            seen["fetcher"] = url_fetcher
            super().__init__(*a, url_fetcher=url_fetcher, **kw)

    monkeypatch.setattr(weasyprint, "HTML", Spy)
    report.html_to_pdf("<p>x</p>")
    for url in ("file:///etc/passwd", "http://127.0.0.1/x"):
        with pytest.raises(ValueError):
            seen["fetcher"].fetch(url) if hasattr(seen["fetcher"], "fetch") else seen["fetcher"](url)


def _nonfinite_report() -> bytes:
    card = synth.make_sd_card()
    name = next(n for n in card if n.endswith(".csv") and "Report" in n)
    text = card[name].decode("utf-8", "replace")
    return name, text


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf"])
def test_csv_nonfinite_numbers_never_reach_the_database(bad, client):
    name, text = _nonfinite_report()
    rows = text.splitlines()
    head = next(i for i, r in enumerate(rows) if r.startswith("Shot"))
    cols = rows[head].split(";")
    v0 = cols.index("V0")
    cells = rows[head + 1].split(";")
    cells[v0] = bad
    rows[head + 1] = ";".join(cells)
    card = synth.make_sd_card()
    card[name] = "\n".join(rows).encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for n, d in card.items():
            zf.writestr(n, d)
    r = client.post("/api/import", files={"file": ("x.zip", buf.getvalue())})
    assert r.status_code in (200, 400)
    for s in client.get("/api/series").json():
        det = client.get(f"/api/series/{s['id']}").json()
        for sh in det["shots"]:
            assert all(x is None or x == x and abs(x) != float("inf") for x in (sh["v0_ms"], sh["energy0_j"]))


def _mutations(blob: bytes, rng, n: int):
    for _ in range(n):
        b = bytearray(blob)
        for _ in range(rng.randint(1, 8)):
            kind = rng.random()
            pos = rng.randrange(len(b)) if b else 0
            if kind < 0.5 and b:
                b[pos] = rng.randrange(256)
            elif kind < 0.75 and b:
                del b[pos:pos + rng.randint(1, 40)]
            else:
                b[pos:pos] = bytes(rng.randrange(256) for _ in range(rng.randint(1, 20)))
        yield bytes(b)


def test_parsers_survive_random_mutations():
    """Zufällig veränderte Dateien dürfen nur zu Meldungen führen, nie zu unbehandelten Ausnahmen."""
    import random

    from loadlog.csvio import CsvError, parse_report, parse_track
    from loadlog.grt import GrtError
    from loadlog.lbr import LbrError, parse_lbr

    rng = random.Random(20261029)
    card = synth.make_sd_card()
    lbr = next(v for k, v in card.items() if k.endswith(".lbr"))
    rep = next(v for k, v in card.items() if k.endswith(".csv") and "Report" in k)
    trk = next(v for k, v in card.items() if k.endswith(".csv") and "Track" in k)
    for blob, parse, errors in ((lbr, parse_lbr, (LbrError,)), (rep, parse_report, (CsvError,)), (trk, parse_track, (CsvError,)),
                                (synth.make_grtload(), parse_grtload, (GrtError,))):
        for data in _mutations(blob, rng, 300):
            try:
                parse(data)
            except errors:
                pass


def test_zip_import_survives_random_mutations():
    import random

    rng = random.Random(7)
    z = synth.make_zip()
    for data in _mutations(z, rng, 150):
        try:
            importer.import_zip(data)
        except importer.ImportFailure:
            pass


def test_grt_with_utf16_doctype_or_unknown_encoding_is_rejected():
    evil = '<?xml version="1.0" encoding="utf-16"?><!DOCTYPE x [<!ENTITY a "aaaa">]><GordonsReloadingTool/>'
    for blob in (evil.encode("utf-16"), b'<?xml version="1.0" encoding="UfF-8"?><GordonsReloadingTool/>'):
        with pytest.raises(GrtError):
            parse_grtload(blob)


# ---- Review vom 2026-10-31 (BUG-01, 02, 03, 09, 11) ----
def test_excluding_a_shot_returns_the_full_series_with_loads(client):
    sid = client.post("/api/import", files={"file": ("s.zip", synth.make_zip(seed=5))}).json()["imported"][0]["id"]
    lid = client.post("/api/loads", json={"name": "L"}).json()["id"]
    client.put(f"/api/series/{sid}/loads/{lid}")
    out = client.put(f"/api/series/{sid}/shots/1/excluded", json={"excluded": True}).json()
    assert out["shots"][0]["excluded"] is True
    assert [load["id"] for load in out["loads"]] == [lid] and out["load"]["id"] == lid
    assert out.keys() == client.get(f"/api/series/{sid}").json().keys()


def test_duplicate_shot_numbers_are_skipped_with_a_warning():
    series = importer.import_zip(synth.make_zip(seed=5)).series[0]
    series.shots.append(series.shots[0])  # zweimal Schuss 1
    warnings: list = []
    importer.drop_insane(series, "Serie 1", warnings)
    numbers = [s.number for s in series.shots]
    assert numbers == sorted(set(numbers)) and [w.code for w in warnings] == ["shot_duplicate"]


@pytest.mark.parametrize("raw", ['{"name": "X", "charge_gr": NaN}', '{"name": "X", "charge_gr": Infinity}'])
def test_non_finite_numbers_are_422_not_500(client, raw):
    r = client.post("/api/loads", content=raw, headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and r.json()["detail"]["code"] in ("value_invalid", "value_min", "value_max")


def test_validation_errors_are_coded_messages(client):
    d = client.post("/api/loads", json={"name": "x", "temperature_c": 99}).json()["detail"]
    assert d["code"] == "value_max" and d["params"] == {"field": "temperature_c", "limit": 80}
    d = client.post("/api/loads", json={"name": "x", "charge_gr": -1}).json()["detail"]
    assert d["code"] == "value_min" and d["params"]["field"] == "charge_gr"
    assert client.post("/api/loads", json={"name": "x", "case_firings": "abc"}).json()["detail"]["code"] == "value_invalid"


def test_blank_names_are_rejected_and_edge_whitespace_is_removed(client):
    assert client.post("/api/loads", json={"name": "   "}).status_code == 422
    assert client.post("/api/weapons", json={"name": "\t"}).status_code == 422
    assert client.post("/api/loads", json={"name": "  Test  "}).json()["name"] == "Test"
    sid = client.post("/api/import", files={"file": ("s.zip", synth.make_zip(seed=5))}).json()["imported"][0]["id"]
    assert client.patch(f"/api/series/{sid}", json={"name": "Mein Name"}).json()["name"] == "Mein Name"
    assert client.patch(f"/api/series/{sid}", json={"name": "  "}).json()["name"] is None
