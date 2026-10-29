// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/preact";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppCtx } from "../src/app";
import { tr } from "../src/i18n";
import { LoadsView, SeriesView } from "../src/views";

// Nutzertext (Namen, Notizen) muss immer als Text erscheinen, nie als HTML.
const SOURCES = import.meta.glob("../src/*.{ts,tsx}", { query: "?raw", import: "default", eager: true }) as Record<string, string>;
const EVIL = '<img src=x onerror="window.__pwned=1"><script>window.__pwned=1</script>';
const stats = { n: 1, avg: 300, sd: 0, es: 0, vmin: 300, vmax: 300, energy_avg_j: 3000, mip_avg: 350, mip_min: 350 };
const LOAD = { id: 1, name: EVIL, trial_type: "single", weapon_id: 2, weapon_name: EVIL, series_count: 1, shots_total: 1, stats, powder_name: EVIL, charge_gr: 1, bullet_weight_gr: 180 };
const SERIES = {
  id: 7, number: 7, name: EVIL, weight_override_g: null, weight_measured_g: 11.66, device_id: EVIL, load_id: 1, load_ids: [1],
  taken_at: "2030-01-01T10:00:00", charge_gr: 42, seating_depth_mm: null, note: EVIL, trigger_mode: null, shots_total: 1, weight_g: 11.66, stats,
  shots: [{ number: 1, taken_at: "2030-01-01T10:00:01", weight_g: 11.66, v0_ms: 300, energy0_j: 3000, power_factor: 3.5, signal_strength: 4, excluded: false, distances_m: [10], velocities_ms: [298], energies_j: [2900], mip: 350 }],
  bc: { g1: { n: 0, avg: null, sd: null }, g7: { n: 0, avg: null, sd: null } }, load: LOAD, loads: [LOAD],
};

function stubFetch() {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const json = (b: unknown) => new Response(JSON.stringify(b), { headers: { "content-type": "application/json" } });
    if (url.startsWith("/api/charts/")) return new Response("<svg></svg>", { headers: { "content-type": "image/svg+xml" } });
    if (url === "/api/loads") return json([LOAD]);
    if (url === "/api/series/7") return json(SERIES);
    return json([]);
  }));
}

function mount(ui: preact.ComponentChild) {
  return render(
    <AppCtx.Provider value={{ lang: "de", units: "si", pdf: true, version: "0.0.1", manualVersion: "0.0", setLang: () => {}, setUnits: () => {}, t: (k) => tr("de", k) }}>{ui}</AppCtx.Provider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  delete (window as unknown as Record<string, unknown>).__pwned;
});

describe("Nutzertext wird nie als HTML ausgewertet", () => {
  it("Laborierungsübersicht (Karten und Liste)", async () => {
    stubFetch();
    const view = mount(<LoadsView />);
    await screen.findAllByText(EVIL, { exact: false });
    expect(view.container.querySelector("img, script")).toBeNull();
    expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined();
  });

  it("Serienansicht (Name, Notiz, Geräte-ID, Laborierung)", async () => {
    stubFetch();
    const view = mount(<SeriesView id={7} />);
    await screen.findAllByText(EVIL, { exact: false });
    expect(view.container.querySelectorAll("img, script, [onerror]").length).toBe(0);
    expect(view.container.querySelector("textarea")?.value).toBe(EVIL); // Notiz steht als Wert, nicht als Markup
    expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined();
  });
});

describe("Quelltext", () => {
  it("dangerouslySetInnerHTML kommt nur für das serverseitig erzeugte SVG vor", () => {
    const hits: string[] = [];
    for (const [file, text] of Object.entries(SOURCES)) {
      text.split("\n").forEach((line: string, i: number) => line.includes("dangerouslySetInnerHTML") && hits.push(`${file}:${i + 1}`));
    }
    expect(hits).toHaveLength(1);
    expect(hits[0]).toMatch(/views\.tsx:/);
    expect(SOURCES["../src/views.tsx"]).toContain("SVG stammt vom eigenen Server");
  });

  it("kein innerHTML, eval oder document.write im Frontend", () => {
    expect(Object.keys(SOURCES).length).toBeGreaterThan(5);
    for (const [file, text] of Object.entries(SOURCES)) {
      expect(text, file).not.toMatch(/\.innerHTML\s*=|\beval\(|document\.write\(|new Function\(/);
    }
  });
});
