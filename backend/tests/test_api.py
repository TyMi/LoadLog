import pytest
from fastapi.testclient import TestClient

from loadlog import report, synth
from loadlog.api import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "t.sqlite3"))


def upload(client, data=None, name="card.zip"):
    return client.post("/api/import", files={"file": (name, data or synth.make_zip(seed=5), "application/zip")})


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.headers["x-content-type-options"] == "nosniff" and "frame-ancestors" in r.headers["content-security-policy"]


def test_import_and_dedup(client):
    r = upload(client).json()
    assert len(r["imported"]) == 3 and r["skipped"] == 0
    again = upload(client).json()
    assert again["imported"] == [] and again["skipped"] == 3
    assert len(client.get("/api/series?unassigned=true").json()) == 3


def test_import_rejects_bad_input(client):
    assert upload(client, b"junk").status_code == 400
    big = b"x" * (50 * 1024 * 1024 + 10)
    assert upload(client, big).status_code == 413
    assert client.post("/api/import").status_code == 422


def test_load_workflow_and_exclusion(client):
    upload(client)
    w = client.post("/api/weapons", json={"name": "Testwaffe", "caliber": ".308", "barrel_length_mm": 650}).json()
    lid = client.post("/api/loads", json={"name": "Leiter 1", "trial_type": "ladder", "weapon_id": w["id"],
                                          "powder_name": "P", "charge_gr": 42}).json()["id"]
    ids = [s["id"] for s in client.get("/api/series").json()]
    for i, sid in enumerate(ids):
        r = client.patch(f"/api/series/{sid}", json={"load_id": lid, "charge_gr": 42 + 0.5 * i, "trigger_mode": "doppler"})
        assert r.status_code == 200
    detail = client.get(f"/api/loads/{lid}").json()
    assert detail["series_count"] == 3 and detail["weapon"]["name"] == "Testwaffe" and len(detail["series"]) == 3
    before = client.get(f"/api/series/{ids[0]}").json()
    r = client.put(f"/api/series/{ids[0]}/shots/1/excluded", json={"excluded": True}).json()
    assert r["stats"]["n"] == before["stats"]["n"] - 1 and r["shots"][0]["excluded"] is True
    lad = client.get(f"/api/loads/{lid}/ladder?by=charge").json()
    assert [p["x"] for p in lad] == [42.0, 42.5, 43.0]
    assert client.get(f"/api/loads/{lid}/ladder?by=seating").json() == []
    comp = client.get(f"/api/compare?ids={','.join(map(str, ids))}").json()
    assert len(comp["series"]) == 3 and comp["trend_ms_per_series"] is not None


def test_validation_and_not_found(client):
    assert client.post("/api/loads", json={"name": ""}).status_code == 422
    assert client.post("/api/loads", json={"name": "x", "trial_type": "bogus"}).status_code == 422
    assert client.post("/api/loads", json={"name": "x", "charge_gr": -1}).status_code == 422
    assert client.post("/api/loads", json={"name": "x", "weapon_id": 99}).status_code == 404
    assert client.get("/api/series/99").status_code == 404
    assert client.get("/api/loads/99").status_code == 404
    assert client.get("/api/compare?ids=a,b").status_code == 422
    assert client.get("/api/compare?ids=" + ",".join(["1"] * 61)).status_code == 422
    assert client.patch("/api/series/1", json={"trigger_mode": "x"}).status_code == 422


def test_charts_endpoints(client):
    upload(client)
    ids = [s["id"] for s in client.get("/api/series").json()]
    r = client.get(f"/api/charts/series/{ids[0]}.svg?sel=2&lang=en&units=imp&theme=light")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml") and "fps" in r.text
    assert client.get(f"/api/charts/series/{ids[0]}.svg?lang=fr").status_code == 422
    assert client.get(f"/api/charts/series/{ids[0]}.svg?units=x").status_code == 422
    assert client.get(f"/api/charts/series/{ids[0]}.svg?theme=pink").status_code == 422
    assert 'data-shot="1"' in r.text and "data-vals=" in r.text
    assert "Trend" in client.get(f"/api/charts/compare.svg?ids={ids[0]},{ids[1]}").text
    lid = client.post("/api/loads", json={"name": "L"}).json()["id"]
    assert client.get(f"/api/charts/ladder/{lid}.svg").status_code == 200


def test_reports_html_and_pdf(client):
    upload(client)
    ids = [s["id"] for s in client.get("/api/series").json()]
    lid = client.post("/api/loads", json={"name": "Bericht", "charge_gr": 40}).json()["id"]
    client.patch(f"/api/series/{ids[0]}", json={"load_id": lid})
    h = client.get(f"/api/reports/series/{ids[0]}?format=html&lang=en")
    assert h.status_code == 200 and "Series report" in h.text and "Bericht" in h.text
    assert client.get(f"/api/reports/load/{lid}?format=html").status_code == 200
    assert client.get(f"/api/reports/compare?ids={ids[0]},{ids[1]}&format=html").status_code == 200
    if report.pdf_available():
        p = client.get(f"/api/reports/series/{ids[0]}")
        assert p.status_code == 200 and p.content.startswith(b"%PDF")
        assert 'filename="loadlog-serie-1.pdf"' in p.headers["content-disposition"]


def test_static_mounts(tmp_path):
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "index.html").write_text("<h1>ui</h1>")
    (tmp_path / "man").mkdir()
    (tmp_path / "man" / "index.html").write_text("<h1>manual</h1>")
    c = TestClient(create_app(db_path=tmp_path / "t.sqlite3", static_dir=tmp_path / "ui", manual_dir=tmp_path / "man"))
    assert "ui" in c.get("/").text and "manual" in c.get("/manual/").text
    assert c.get("/api/health").status_code == 200


def test_series_detail_contains_bc(client):
    upload(client)
    sid = client.get("/api/series").json()[0]["id"]
    bc = client.get(f"/api/series/{sid}").json()["bc"]
    assert set(bc) == {"g1", "g7"}
    assert bc["g1"]["n"] > 0 and 0.05 < bc["g7"]["avg"] < bc["g1"]["avg"] < 2.0
    assert "bc" not in client.get("/api/series").json()[0]  # Liste bleibt schlank


def test_series_report_shows_date(client):
    upload(client)
    sid = client.get("/api/series").json()[0]["id"]
    taken = client.get(f"/api/series/{sid}").json()["shots"][0]["taken_at"][:10]
    y, m, d = taken.split("-")
    assert f"{d}.{m}.{y}" in client.get(f"/api/reports/series/{sid}?format=html&lang=de").text
    assert f"{d}/{m}/{y}" in client.get(f"/api/reports/series/{sid}?format=html&lang=en").text


def test_series_report_shows_bc(client):
    upload(client)
    sid = client.get("/api/series").json()[0]["id"]
    de = client.get(f"/api/reports/series/{sid}?format=html&lang=de").text
    en = client.get(f"/api/reports/series/{sid}?format=html&lang=en").text
    assert "Ø BC" in de and "G1:" in de and "G7:" in de
    assert "Avg. BC" in en
    assert "Ø Impuls (MIP)" in de and "<th class=\"n\">MIP</th>" in de and "Avg. impulse (MIP)" in en


def test_api_exposes_mip(client):
    upload(client)
    sid = client.get("/api/series").json()[0]["id"]
    d = client.get(f"/api/series/{sid}").json()
    sh = d["shots"][0]
    assert sh["mip"] == pytest.approx(0.1 * sh["weight_g"] * sh["v0_ms"])
    assert d["stats"]["mip_min"] <= d["stats"]["mip_avg"]


def test_import_grt_creates_load(client):
    r = client.post("/api/import", files={"file": ("x.grtload", synth.make_grtload())})
    assert r.status_code == 200, r.text
    j = r.json()
    assert len(j["imported"]) == 5 and j["skipped"] == 0 and j["load_id"]
    load = client.get(f"/api/loads/{j['load_id']}").json()
    assert load["bullet_maker"] == "Testhersteller" and load["series_count"] == 5 and load["trial_type"] == "ladder"
    lad = client.get(f"/api/loads/{j['load_id']}/ladder?by=charge").json()
    assert [p["x"] for p in lad] == [40.0, 40.5, 41.0, 41.5, 42.0]
    again = client.post("/api/import", files={"file": ("x.grtload", synth.make_grtload())}).json()
    assert again["imported"] == [] and again["skipped"] == 5 and again["load_id"] is None  # keine zweite Laborierung
    sid = j["imported"][0]["id"]
    assert client.get(f"/api/series/{sid}").json()["shots"][0]["mip"] > 0
    assert client.get(f"/api/charts/series/{sid}.svg").text.count("<polyline") == 5


def test_import_into_existing_load(client):
    lid = client.post("/api/loads", json={"name": "Meine", "powder_name": "Eigenes"}).json()["id"]
    j = client.post(f"/api/import?load_id={lid}", files={"file": ("x.grtload", synth.make_grtload())}).json()
    assert j["load_id"] == lid and len(j["imported"]) == 5
    load = client.get(f"/api/loads/{lid}").json()
    assert load["series_count"] == 5 and load["name"] == "Meine"
    assert load["powder_name"] == "Eigenes" and load["bullet_maker"] == "Testhersteller"  # ergänzt, nicht überschrieben
    assert len(client.get("/api/loads").json()) == 1


def test_import_sd_card_into_load_assigns_only_new(client):
    lid = client.post("/api/loads", json={"name": "SD"}).json()["id"]
    j = client.post(f"/api/import?load_id={lid}", files={"file": ("sd.zip", synth.make_zip())}).json()
    assert len(j["imported"]) == 3 and client.get(f"/api/loads/{lid}").json()["series_count"] == 3
    other = client.post("/api/loads", json={"name": "Zweite"}).json()["id"]
    j2 = client.post(f"/api/import?load_id={other}", files={"file": ("sd.zip", synth.make_zip())}).json()
    assert j2["imported"] == [] and client.get(f"/api/loads/{other}").json()["series_count"] == 0
    assert client.post("/api/import?load_id=999", files={"file": ("sd.zip", synth.make_zip())}).status_code == 404


def test_import_grt_rejects_garbage(client):
    r = client.post("/api/import", files={"file": ("x.grtload", b"<GordonsReloadingTool><InnerBallistikInput/></GordonsReloadingTool>")})
    assert r.status_code == 400


def test_compare_handles_large_loads(client):
    """Eine GRT-Laborierung kann Dutzende Serien enthalten; Vergleich, Diagramm und Bericht müssen das tragen."""
    ids = []
    for seed in range(1, 13):  # 12 SD-Karten à 3 Serien -> 36 Serien (verschiedene Zeitstempel durch Seeds)
        j = client.post("/api/import", files={"file": ("sd.zip", synth.make_zip(seed=seed))}).json()
        ids += [i["id"] for i in j["imported"]]
    assert len(ids) > 20
    q = ",".join(map(str, ids))
    assert client.get(f"/api/charts/compare.svg?ids={q}").status_code == 200
    assert client.get(f"/api/compare?ids={q}").status_code == 200
    assert client.get(f"/api/reports/compare?ids={q}&format=html").status_code == 200
    too_many = ",".join(map(str, range(1, 62)))
    assert client.get(f"/api/charts/compare.svg?ids={too_many}").status_code == 422


def test_series_can_be_named(client):
    upload(client)
    sid = client.get("/api/series").json()[0]["id"]
    assert client.get(f"/api/series/{sid}").json()["name"] is None
    r = client.patch(f"/api/series/{sid}", json={"name": "Vormittag <1>"})
    assert r.status_code == 200 and r.json()["name"] == "Vormittag <1>"
    assert client.patch(f"/api/series/{sid}", json={"name": "x" * 201}).status_code == 422
    html = client.get(f"/api/reports/series/{sid}?format=html").text
    assert "Vormittag &lt;1&gt;" in html and "Vormittag <1>" not in html  # Name wird escaped
    ids = ",".join(str(i["id"]) for i in client.get("/api/series").json()[:2])
    assert "Vormittag" in client.get(f"/api/charts/compare.svg?ids={ids}").text
    client.patch(f"/api/series/{sid}", json={"name": None})
    assert client.get(f"/api/series/{sid}").json()["name"] is None


def test_grt_import_keeps_custom_series_name(client):
    j = client.post("/api/import", files={"file": ("x.grtload", synth.make_grtload())}).json()
    names = [s["name"] for s in client.get(f"/api/loads/{j['load_id']}").json()["series"]]
    assert "Handnotiz" in names and None in names and "Series 1 (2)" in names


def test_bc_uses_track_when_few_distances(client):
    """GRT-Serien haben nur 3 Distanzwerte, aber einen Track: der BC muss trotzdem berechnet werden."""
    j = client.post("/api/import", files={"file": ("x.grtload", synth.make_grtload())}).json()
    first = j["imported"][0]["id"]  # Serie 1: Track mit 30 Punkten
    bc = client.get(f"/api/series/{first}").json()["bc"]
    assert bc["g1"]["n"] == 5 and bc["g7"]["n"] == 5
    last = j["imported"][4]["id"]  # Handnotiz: nur V0 und 3 Distanzen, kein Track
    assert client.get(f"/api/series/{last}").json()["bc"]["g1"]["n"] >= 0


def test_bc_survives_shot_exclusion(client):
    j = client.post("/api/import", files={"file": ("x.grtload", synth.make_grtload())}).json()
    sid = j["imported"][0]["id"]
    r = client.put(f"/api/series/{sid}/shots/1/excluded", json={"excluded": True}).json()
    assert r["bc"]["g1"]["n"] == 4  # die UI übernimmt die Antwort: der BC darf nicht verschwinden


def test_bulk_assign_and_undo_via_patch(client):
    upload(client)
    lid = client.post("/api/loads", json={"name": "Ziel"}).json()["id"]
    ids = [s["id"] for s in client.get("/api/series?unassigned=true").json()]
    assert len(ids) == 3
    for sid in ids[:2]:
        assert client.patch(f"/api/series/{sid}", json={"load_id": lid}).json()["load_id"] == lid
    assert len(client.get("/api/series?unassigned=true").json()) == 1
    for sid in ids[:2]:  # "Rückgängig" der Oberfläche
        assert client.patch(f"/api/series/{sid}", json={"load_id": None}).json()["load_id"] is None
    assert len(client.get("/api/series?unassigned=true").json()) == 3


def test_series_weight_override_via_api(client):
    upload(client)
    sid = client.get("/api/series").json()[0]["id"]
    d = client.get(f"/api/series/{sid}").json()
    measured = d["weight_measured_g"]
    assert d["weight_override_g"] is None and d["shots"][0]["weight_g"] == pytest.approx(measured)
    r = client.patch(f"/api/series/{sid}", json={"weight_override_g": 14.9})
    assert r.status_code == 200 and r.json()["weight_override_g"] == 14.9 and r.json()["weight_g"] == 14.9
    d = client.get(f"/api/series/{sid}").json()
    assert d["shots"][0]["mip"] == pytest.approx(0.1 * 14.9 * d["shots"][0]["v0_ms"])
    assert d["weight_measured_g"] == pytest.approx(measured)  # Messwert bleibt sichtbar
    assert client.patch(f"/api/series/{sid}", json={"weight_override_g": 0}).status_code == 422
    assert client.patch(f"/api/series/{sid}", json={"weight_override_g": None}).json()["weight_override_g"] is None


def test_apply_load_weight_to_all_series_and_clear(client):
    upload(client)
    lid = client.post("/api/loads", json={"name": "Gewicht", "bullet_weight_gr": 185}).json()["id"]
    ids = [s["id"] for s in client.get("/api/series").json()]
    for sid in ids:
        client.patch(f"/api/series/{sid}", json={"load_id": lid})
    r = client.post(f"/api/loads/{lid}/apply-weight").json()
    assert r["series"] == 3 and r["weight_override_g"] == pytest.approx(185 * 0.06479891, abs=1e-3)
    for sid in ids:
        assert client.get(f"/api/series/{sid}").json()["weight_g"] == pytest.approx(11.987, abs=1e-3)
    assert client.post(f"/api/loads/{lid}/apply-weight?clear=true").json()["weight_override_g"] is None
    assert client.get(f"/api/series/{ids[0]}").json()["weight_override_g"] is None
    empty = client.post("/api/loads", json={"name": "Ohne"}).json()["id"]
    assert client.post(f"/api/loads/{empty}/apply-weight").status_code == 400
    assert client.post("/api/loads/999/apply-weight").status_code == 404


def test_delete_unassigned_series_and_reimport(client):
    upload(client)
    ids = [s["id"] for s in client.get("/api/series?unassigned=true").json()]
    assert len(ids) == 3
    for sid in ids[:2]:
        assert client.delete(f"/api/series/{sid}").status_code == 204
    assert len(client.get("/api/series?unassigned=true").json()) == 1
    assert client.get(f"/api/series/{ids[0]}").status_code == 404
    j = upload(client).json()
    assert len(j["imported"]) == 2 and j["skipped"] == 1  # gelöschte lassen sich neu einlesen, die übrige bleibt


def test_grt_without_measurements_imports_the_load_only(client):
    data = (
        b'<?xml version="1.0"?><GordonsReloadingTool><InnerBallistikInput><title>Nur Kopf</title>'
        b'<projectile><input name="mp" value="10" unit="g" type="decimal"/></projectile>'
        b'<propellant><input name="mc" value="2.6" unit="g" type="decimal"/></propellant>'
        b"</InnerBallistikInput></GordonsReloadingTool>"
    )
    r = client.post("/api/import", files={"file": ("k.grtload", data)})
    body = r.json()
    assert r.status_code == 200 and body["imported"] == [] and [w["code"] for w in body["warnings"]] == ["grt_load_only"]
    load = client.get(f"/api/loads/{body['load_id']}").json()
    assert load["name"] == "Nur Kopf" and load["charge_gr"] == 40.12
