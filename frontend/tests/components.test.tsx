// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/preact";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppCtx } from "../src/app";
import { tr } from "../src/i18n";
import { setMessageLang } from "../src/messages";
import type { Lang, Units } from "../src/units";
import { LoadView, LoadsView, SeriesView, SystemView } from "../src/views";

const stats = { n: 5, avg: 300, sd: 2, es: 6, vmin: 297, vmax: 303, energy_avg_j: 3000, mip_avg: 349.6, mip_min: 340.2 };
const load = (id: number, name: string, weapon_id: number | null, weapon_name: string | null) => ({
  id, name, trial_type: "single", weapon_id, weapon_name, series_count: 2, shots_total: 10, stats,
  powder_name: "Pulver X", charge_gr: 42, bullet_weight_gr: 180,
});
const LOADS = [load(1, "Zebra-Last", 2, "Zebra"), load(2, "Ohne", null, null), load(3, "Alpha-Last", 1, "Alpha")];

const shot = (n: number) => ({
  number: n, taken_at: "2030-01-01T10:00:0" + n, weight_g: 11.66, v0_ms: 300 + n, energy0_j: 3000, power_factor: 3.5,
  signal_strength: 4, excluded: false, distances_m: [10], velocities_ms: [298], energies_j: [2900], mip: 349.9 + n,
});
const SERIES = {
  id: 7, number: 7, name: null, weight_override_g: null, weight_measured_g: 11.66, device_id: "X", load_id: 1, load_ids: [1],
  taken_at: "2030-01-01T10:00:00", charge_gr: 42, seating_depth_mm: null, note: null, trigger_mode: null, shots_total: 2,
  weight_g: 11.66, stats, shots: [shot(1), shot(2)], bc: { g1: { n: 0, avg: null, sd: null }, g7: { n: 0, avg: null, sd: null } },
  load: LOADS[0], loads: [LOADS[0]],
};

let calls: { method: string; url: string; headers?: Record<string, string> }[];
let seriesState: typeof SERIES;

function fakeFetch(extra: (url: string, init?: RequestInit) => Response | undefined = () => undefined) {
  calls = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, headers: init?.headers as Record<string, string> | undefined });
    const custom = extra(url, init);
    if (custom) return custom;
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
    if (url.startsWith("/api/charts/")) return new Response("<svg></svg>", { headers: { "content-type": "image/svg+xml" } });
    if (url === "/api/loads") return json(LOADS);
    if (url === "/api/series/7" && method === "GET") return json(seriesState);
    const add = url.match(/^\/api\/series\/7\/loads\/(\d+)$/);
    if (add && method === "PUT") {
      seriesState = { ...seriesState, load_ids: [...seriesState.load_ids, Number(add[1])], loads: [...seriesState.loads, LOADS.find((l) => l.id === Number(add[1]))!] };
      return json(seriesState);
    }
    if (add && method === "DELETE") {
      seriesState = { ...seriesState, load_ids: seriesState.load_ids.filter((i) => i !== Number(add[1])), loads: seriesState.loads.filter((l) => l.id !== Number(add[1])) };
      return json(seriesState);
    }
    return json({ detail: "unerwartet " + method + " " + url }, 404);
  }));
}

function mount(ui: preact.ComponentChild, o: { lang?: Lang; units?: Units; setLang?: (l: Lang) => void; setUnits?: (u: Units) => void } = {}) {
  const lang = o.lang ?? "de";
  setMessageLang(lang); // wie die App: Fehler aus api.ts kommen in der Oberflächensprache
  return render(
    <AppCtx.Provider value={{ lang, units: o.units ?? "si", pdf: true, version: "0.0.1", manualVersion: "0.0", setLang: o.setLang ?? (() => {}), setUnits: o.setUnits ?? (() => {}), t: (k) => tr(lang, k) }}>
      {ui}
    </AppCtx.Provider>,
  );
}

beforeEach(() => {
  seriesState = structuredClone(SERIES);
  localStorage.clear();
  fakeFetch();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Laborierungsübersicht", () => {
  it("zeigt Karten, wechselt auf Liste und merkt sich die Wahl", async () => {
    const view = mount(<LoadsView />);
    await screen.findByText("Zebra-Last");
    expect(view.container.querySelector("table")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Liste" }));
    expect(view.container.querySelector("table")).not.toBeNull();
    expect(localStorage.getItem("loadsView")).toBe("list");
    cleanup();
    const again = mount(<LoadsView />); // zweite Sitzung
    await screen.findByText("Zebra-Last");
    expect(again.container.querySelector("table")).not.toBeNull();
  });

  it("gruppiert nach Waffe: alphabetisch, ohne Waffe zuletzt, Überschrift mit Anzahl", async () => {
    const view = mount(<LoadsView />);
    await screen.findByText("Zebra-Last");
    fireEvent.click(screen.getByRole("button", { name: "Nach Waffe" }));
    const titles = [...view.container.querySelectorAll(".group-title")].map((h) => h.textContent?.replace(/\s+/g, " ").trim());
    expect(titles).toEqual(["Alpha (1)", "Zebra (1)", "Ohne Waffe (1)"]);
    expect(localStorage.getItem("loadsGroup")).toBe("weapon");
  });

  it("Listenzeile öffnet die Laborierung, Link im Namen funktioniert", async () => {
    mount(<LoadsView />);
    await screen.findByText("Zebra-Last");
    fireEvent.click(screen.getByRole("button", { name: "Liste" }));
    fireEvent.click(screen.getByText("Alpha-Last").closest("tr")!);
    expect(location.hash).toBe("#/load/3");
    expect(screen.getByText("Alpha-Last").getAttribute("href")).toBe("#/load/3");
  });

  it("englische Oberfläche", async () => {
    mount(<LoadsView />, { lang: "en" });
    await screen.findByText("Zebra-Last");
    expect(screen.getByRole("button", { name: "By firearm" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Cards" })).toBeTruthy();
  });

  it("defekter localStorage-Wert wird ignoriert", async () => {
    localStorage.setItem("loadsView", "kaputt");
    const view = mount(<LoadsView />);
    await screen.findByText("Zebra-Last");
    expect(view.container.querySelector("table")).toBeNull();
  });
});

describe("Serie: Laborierungen", () => {
  it("fügt die Serie einer weiteren Laborierung hinzu und kann sie wieder entfernen", async () => {
    mount(<SeriesView id={7} />);
    const chips = await screen.findByText("Laborierungen dieser Serie");
    const panel = chips.parentElement!;
    expect(within(panel).getByText("Zebra-Last")).toBeTruthy();
    const select = within(panel).getByLabelText("Laborierung zuordnen") as HTMLSelectElement;
    expect([...select.options].map((o) => o.textContent)).toEqual(["Laborierung wählen …", "Ohne", "Alpha-Last"]); // Zebra-Last ist schon dabei
    expect((within(panel).getByRole("button", { name: "Hinzufügen" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(select, { target: { value: "3" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Hinzufügen" }));
    await waitFor(() => expect(within(panel).getByText("Alpha-Last")).toBeTruthy());
    expect(calls.some((c) => c.method === "PUT" && c.url === "/api/series/7/loads/3")).toBe(true);
    fireEvent.click(within(panel).getByRole("button", { name: "Aus „Zebra-Last“ nehmen" }));
    await waitFor(() => expect([...panel.querySelectorAll(".chip")].map((c) => c.textContent?.replace("×", "").trim())).toEqual(["Alpha-Last"]));
    expect(calls.some((c) => c.method === "DELETE" && c.url === "/api/series/7/loads/1")).toBe(true);
    expect(seriesState.load_ids).toEqual([3]);
  });

  it("zeigt MIP ohne Nachkommastellen", async () => {
    const view = mount(<SeriesView id={7} />);
    await screen.findByText("Laborierungen dieser Serie");
    const text = view.container.textContent ?? "";
    expect(text).toContain("350"); // Ø-MIP 349,6
    expect(text).toContain("340"); // min. 340,2
    expect(text).not.toMatch(/349,6|340,2/);
  });

  it("Exportlink verweist auf CSV mit Sprache und Einheiten", async () => {
    mount(<SeriesView id={7} />, { lang: "en", units: "imp" });
    const a = (await screen.findByText("CSV export")).closest("a")!;
    expect(a.getAttribute("href")).toBe("/api/export/series/7.csv?lang=en&units=imp");
  });
});

describe("Laborierung: Ladeleiter", () => {
  const detail = (trial: string) => (url: string) => {
    if (url === "/api/loads/5") return new Response(JSON.stringify({ ...load(5, "Leiter", null, null), trial_type: trial, series: [] }), { headers: { "content-type": "application/json" } });
    if (url.startsWith("/api/series")) return new Response("[]", { headers: { "content-type": "application/json" } });
    return undefined;
  };

  it("weist bei einer Ladeleiter darauf hin, dass die Gesamtkennzahlen wenig aussagen", async () => {
    fakeFetch(detail("ladder"));
    mount(<LoadView id={5} />);
    expect(await screen.findByText(/Ladeleiter: Ø, SD und ES fassen alle Stufen/)).toBeTruthy();
  });

  it("zeigt den Hinweis bei einer Einzelmessung nicht", async () => {
    fakeFetch(detail("single"));
    const view = mount(<LoadView id={5} />);
    await waitFor(() => expect(view.container.querySelector(".stat-groups")).toBeTruthy());
    expect(view.container.textContent).not.toContain("fassen alle Stufen");
  });
});

describe("System", () => {
  it("schaltet Sprache und Einheiten um", () => {
    const setLang = vi.fn();
    const setUnits = vi.fn();
    mount(<SystemView />, { setLang, setUnits });
    fireEvent.click(screen.getByRole("button", { name: "English" }));
    fireEvent.click(screen.getByRole("button", { name: "fps · ft-lbf" }));
    expect(setLang).toHaveBeenCalledWith("en");
    expect(setUnits).toHaveBeenCalledWith("imp");
  });

  it("zeigt Version, Handbuchlink mit zwei Stellen und Sicherungslink", () => {
    mount(<SystemView />);
    expect(screen.getByRole("note").textContent).toContain("keine Laborierungsentwicklung");
    expect(screen.getByRole("link", { name: "Abgrenzung und Haftungsausschluss" }).getAttribute("href")).toBe("/manual/0.0/de/#disclaimer");
    expect(screen.getByText("0.0.1")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Handbuch 0\.0/ }).getAttribute("href")).toBe("/manual/0.0/de/");
    expect(screen.getByRole("link", { name: "Sicherung herunterladen" }).getAttribute("href")).toBe("/api/system/backup");
  });

  const pickFile = (view: ReturnType<typeof mount>) => {
    const input = view.container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["x"], "sicherung.sqlite3");
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    fireEvent.change(input);
  };

  it("Wiederherstellen: erst nach Bestätigung, mit Schutz-Header, zeigt das Ergebnis", async () => {
    fakeFetch((url) => (url === "/api/system/restore" ? new Response(JSON.stringify({ weapons: 1, loads: 2, series: 3, shots: 15 }), { status: 200 }) : undefined));
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const view = mount(<SystemView />);
    pickFile(view);
    expect(confirm).toHaveBeenCalled();
    await Promise.resolve();
    expect(calls.some((c) => c.url === "/api/system/restore")).toBe(false); // abgebrochen: nichts gesendet
    confirm.mockReturnValue(true);
    pickFile(view);
    await screen.findByText(/Wiederhergestellt: 2 Laborierungen, 3 Serien, 15 Schüsse/);
    const call = calls.find((c) => c.url === "/api/system/restore")!;
    expect(call.method).toBe("POST");
    expect(call.headers).toMatchObject({ "X-LoadLog-Confirm": "restore" });
  });

  it("Wiederherstellen: Fehler des Servers wird übersetzt angezeigt", async () => {
    fakeFetch((url) =>
      url === "/api/system/restore"
        ? new Response(JSON.stringify({ detail: { code: "backup_invalid", message: "x", params: {} } }), { status: 400 })
        : undefined,
    );
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const view = mount(<SystemView />, { lang: "en" });
    pickFile(view);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Not a valid LoadLog backup");
  });
});
