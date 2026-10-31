// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/preact";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppCtx } from "../src/app";
import { tr } from "../src/i18n";
import { setMessageLang } from "../src/messages";
import type { Lang, Units } from "../src/units";
import { ImportView, LoadView, LoadsView, SeriesView, SettingsView, TrashView } from "../src/views";

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
let keepState = 5;

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
    if (url === "/api/settings" && method === "PATCH") {
      keepState = (JSON.parse(String(init?.body)) as { backup_keep: number }).backup_keep;
      return json({ backup_keep: keepState });
    }
    if (url === "/api/settings") return json({ backup_keep: keepState });
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
  keepState = 5;
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

  it("sucht und filtert nach Status; zeigt den Status als Marke", async () => {
    const withStatus = [{ ...LOADS[0], status: "validated" }, { ...LOADS[1], status: "draft", powder_name: "Anderes Pulver" }, { ...LOADS[2], status: null }];
    fakeFetch((url) => (url === "/api/loads" ? new Response(JSON.stringify(withStatus), { headers: { "content-type": "application/json" } }) : undefined));
    const view = mount(<LoadsView />);
    await screen.findByText("Zebra-Last");
    expect([...view.container.querySelectorAll(".chip")].map((c) => c.textContent)).toEqual(["bewährt", "Entwurf"]);
    const search = screen.getByLabelText("Suchen");
    fireEvent.input(search, { target: { value: "anderes" } });
    await waitFor(() => expect(screen.queryByText("Zebra-Last")).toBeNull());
    expect(screen.getByText("Ohne")).toBeTruthy();
    fireEvent.input(search, { target: { value: "" } });
    const select = screen.getByLabelText("Status") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "none" } });
    await waitFor(() => expect(screen.getByText("Alpha-Last")).toBeTruthy());
    expect(screen.queryByText("Zebra-Last")).toBeNull();
    fireEvent.input(search, { target: { value: "gibtsnicht" } });
    await screen.findByText("Keine Laborierung passt zu Suche und Filter.");
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

  it("speichert die Gruppengröße als freien Text an der Serie", async () => {
    const patches: Record<string, unknown>[] = [];
    fakeFetch((url, init) => {
      if (url === "/api/series/7" && init?.method === "PATCH") {
        patches.push(JSON.parse(String(init.body)));
        return new Response(JSON.stringify(seriesState), { headers: { "content-type": "application/json" } });
      }
      return undefined;
    });
    mount(<SeriesView id={7} />);
    const input = (await screen.findByLabelText(/Gruppengröße/)) as HTMLInputElement;
    expect(input.value).toBe("");
    fireEvent.input(input, { target: { value: " 25 mm auf 100 m " } });
    fireEvent.click(screen.getAllByRole("button", { name: "Speichern" })[0]);
    await waitFor(() => expect(patches).toHaveLength(1));
    expect(patches[0].group_text).toBe("25 mm auf 100 m");
  });

  it("zeigt V0 über die Schussfolge, das Mittelungsfenster ändert die Abfrage", async () => {
    mount(<SeriesView id={7} />, { lang: "en", units: "imp" });
    await screen.findByText("V0 over the shot sequence");
    await waitFor(() => expect(calls.some((c) => c.url === "/api/charts/series/7/sequence.svg?window=3&lang=en&units=imp&theme=dark")).toBe(true));
    fireEvent.change(screen.getByLabelText("Average over"), { target: { value: "5" } });
    await waitFor(() => expect(calls.some((c) => c.url === "/api/charts/series/7/sequence.svg?window=5&lang=en&units=imp&theme=dark")).toBe(true));
  });

  it("Diagramme lassen sich als SVG speichern (Dateiname nach Diagramm)", async () => {
    const names: string[] = [];
    vi.stubGlobal("URL", { ...URL, createObjectURL: () => "blob:x", revokeObjectURL: () => undefined });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.download);
    });
    mount(<SeriesView id={7} />);
    await screen.findByText("V0 über die Schussfolge");
    await waitFor(() => expect(screen.getAllByRole("button", { name: "Als SVG speichern" })).toHaveLength(2));
    const buttons = screen.getAllByRole("button", { name: "Als SVG speichern" });
    fireEvent.click(buttons[0]);
    fireEvent.click(buttons[1]);
    expect(names).toEqual(["loadlog-series-7.svg", "loadlog-series-7-sequence.svg"]);
    expect(screen.getAllByRole("button", { name: "Als PNG speichern" })).toHaveLength(2);
  });

  it("zeigt MIP ohne Nachkommastellen", async () => {
    const view = mount(<SeriesView id={7} />);
    await screen.findByText("Laborierungen dieser Serie");
    const text = view.container.textContent ?? "";
    expect(text).toContain("350"); // Ø-MIP 349,6
    expect(text).toContain("340"); // min. 340,2
    expect(text).not.toMatch(/349,6|340,2/);
  });

  it("Schusstabelle trägt Beschriftungen an den Zellen (Kartenansicht auf dem Handy)", async () => {
    const view = mount(<SeriesView id={7} />, { units: "si" });
    await screen.findByText("Laborierungen dieser Serie");
    const table = view.container.querySelector("table.rt-shots")!;
    expect(table).toBeTruthy();
    const labels = [...table.querySelectorAll("tbody tr:first-child td[data-label]")].map((td) => td.getAttribute("data-label"));
    expect(labels).toEqual(expect.arrayContaining(["V0 (m/s)", "Energie (J)", "MIP", "Zeit", "Signal"]));
    expect(table.querySelector("td.c-status button")).toBeTruthy(); // Schuss ausschließen bleibt erreichbar
  });

  it("Schuss ausschließen aktualisiert die Seite (Antwort enthält die Laborierungen)", async () => {
    fakeFetch((url, init) => {
      if (url === "/api/series/7/shots/1/excluded" && init?.method === "PUT") {
        seriesState = { ...seriesState, shots: [{ ...shot(1), excluded: true }, shot(2)] };
        return new Response(JSON.stringify(seriesState), { headers: { "content-type": "application/json" } });
      }
      return undefined;
    });
    const view = mount(<SeriesView id={7} />, { units: "si" });
    await screen.findByText("Laborierungen dieser Serie");
    const first = view.container.querySelector("table.rt-shots tbody tr:first-child td.c-status button")!;
    expect(first.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(first);
    await waitFor(() => expect(view.container.querySelector("table.rt-shots tbody tr:first-child td.c-status button")!.getAttribute("aria-pressed")).toBe("true"));
    expect(screen.getByText("Laborierungen dieser Serie")).toBeTruthy(); // Seite lebt noch
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

  it("Duplizieren legt einen Entwurf an und öffnet ihn; Ursprung und Varianten sind verlinkt", async () => {
    const bodies: unknown[] = [];
    fakeFetch((url, init) => {
      if (url === "/api/loads/5/duplicate" && init?.method === "POST") {
        bodies.push(JSON.parse(String(init.body)));
        return new Response(JSON.stringify({ ...load(9, "Leiter (Kopie)", null, null), status: "draft", parent_id: 5 }), { status: 201, headers: { "content-type": "application/json" } });
      }
      if (url === "/api/loads/5") {
        return new Response(JSON.stringify({ ...load(5, "Leiter", null, null), series: [], parent: { id: 2, name: "Vorlage", status: "validated" }, variants: [{ id: 7, name: "Variante B", status: "testing" }] }), { headers: { "content-type": "application/json" } });
      }
      return detail("single")(url);
    });
    const view = mount(<LoadView id={5} />);
    const link = await screen.findByRole("link", { name: "Vorlage" });
    expect(link.getAttribute("href")).toBe("#/load/2");
    expect(screen.getByRole("link", { name: "Variante B" }).getAttribute("href")).toBe("#/load/7");
    expect(view.container.textContent).toContain("(in Prüfung)");
    fireEvent.click(screen.getByRole("button", { name: "Duplizieren" }));
    await waitFor(() => expect(bodies).toEqual([{ name: "Leiter (Kopie)" }]));
    await waitFor(() => expect(window.location.hash).toBe("#/load/9"));
  });

  it("speichert den Status der Laborierung", async () => {
    const puts: Record<string, unknown>[] = [];
    fakeFetch((url, init) => {
      if (url === "/api/loads/5" && init?.method === "PUT") {
        puts.push(JSON.parse(String(init.body)));
        return new Response(JSON.stringify(load(5, "Leiter", null, null)), { headers: { "content-type": "application/json" } });
      }
      return detail("single")(url);
    });
    const view = mount(<LoadView id={5} />);
    const select = (await screen.findAllByRole("combobox")).find((el) => (el as HTMLSelectElement).querySelector('option[value="testing"]')) as HTMLSelectElement;
    expect(select.value).toBe("");
    fireEvent.change(select, { target: { value: "testing" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Speichern" })[0]);
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0].status).toBe("testing");
    expect(view.container.textContent).not.toContain("Ungültig");
  });

  it("zeigt den Hinweis bei einer Einzelmessung nicht", async () => {
    fakeFetch(detail("single"));
    const view = mount(<LoadView id={5} />);
    await waitFor(() => expect(view.container.querySelector(".stat-groups")).toBeTruthy());
    expect(view.container.textContent).not.toContain("fassen alle Stufen");
  });
  it("Import in die Laborierung: vorhandene Serien nur auf Wunsch zuordnen", async () => {
    const posts: string[] = [];
    fakeFetch((url, init) => {
      if (url.startsWith("/api/import") && init?.method === "POST") {
        posts.push(url);
        return new Response(JSON.stringify({ imported: [], skipped: 2, assigned: 2, warnings: [], load_id: 5 }), { headers: { "content-type": "application/json" } });
      }
      return detail("single")(url);
    });
    const view = mount(<LoadView id={5} />);
    const box = (await screen.findByLabelText("Vorhandene Serien auch dieser Laborierung zuordnen")) as HTMLInputElement;
    const pick = () => {
      const input = view.container.querySelector('input[type="file"][multiple]') as HTMLInputElement;
      Object.defineProperty(input, "files", { value: [new File(["x"], "karte.zip")], configurable: true });
      fireEvent.change(input);
    };
    pick();
    await waitFor(() => expect(posts).toEqual(["/api/import?load_id=5"]));
    fireEvent.click(box);
    pick();
    await waitFor(() => expect(posts).toHaveLength(2));
    expect(posts[1]).toBe("/api/import?load_id=5&assign_existing=true");
    await screen.findByText(/2 vorhandene zugeordnet/);
  });
});

describe("Einstellungen", () => {
  it("schaltet Sprache und Einheiten um", () => {
    const setLang = vi.fn();
    const setUnits = vi.fn();
    mount(<SettingsView />, { setLang, setUnits });
    fireEvent.click(screen.getByRole("button", { name: "English" }));
    fireEvent.click(screen.getByRole("button", { name: "fps · ft-lbf" }));
    expect(setLang).toHaveBeenCalledWith("en");
    expect(setUnits).toHaveBeenCalledWith("imp");
  });

  it("zeigt Version, Handbuchlink mit zwei Stellen und Sicherungslink", () => {
    mount(<SettingsView />);
    expect(screen.getByRole("note").textContent).toContain("keine Laborierungsentwicklung");
    expect(screen.getByRole("link", { name: "Abgrenzung und Haftungsausschluss" }).getAttribute("href")).toBe("/manual/0.0/de/#disclaimer");
    expect(screen.getByText("0.0.1")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Handbuch 0\.0/ }).getAttribute("href")).toBe("/manual/0.0/de/");
    expect(screen.getByRole("link", { name: "Sicherung herunterladen" }).getAttribute("href")).toBe("/api/system/backup");
  });

  it("zeigt die Zahl der Sicherheitskopien und speichert eine Änderung", async () => {
    mount(<SettingsView />);
    const input = (await screen.findByLabelText("Sicherheitskopien behalten")) as HTMLInputElement;
    expect(input.value).toBe("5");
    fireEvent.input(input, { target: { value: "8" } });
    fireEvent.change(input);
    await screen.findByText("Gespeichert.");
    expect(keepState).toBe(8);
    expect(calls.some((c) => c.method === "PATCH" && c.url === "/api/settings")).toBe(true);
  });

  it("weist ungültige Eingaben für die Zahl der Sicherheitskopien ab", async () => {
    mount(<SettingsView />);
    const input = (await screen.findByLabelText("Sicherheitskopien behalten")) as HTMLInputElement;
    fireEvent.input(input, { target: { value: "2,5" } });
    fireEvent.change(input);
    await screen.findByRole("alert");
    expect(keepState).toBe(5);
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
    const view = mount(<SettingsView />);
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
    const view = mount(<SettingsView />, { lang: "en" });
    pickFile(view);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Not a valid LoadLog backup");
  });
});


describe("Papierkorb", () => {
  const trashState = () => ({
    series: [{ id: 3, number: 3, name: null, deleted_at: "2030-02-01T09:15:00", shots_total: 8, taken_at: "2030-01-15T10:00:00" }],
    loads: [{ id: 4, name: "Alte Ladung", status: "retired", deleted_at: "2030-02-02T18:30:00", series_count: 2 }],
  });

  it("zeigt gelöschte Laborierungen und Serien mit Datum und stellt sie wieder her", async () => {
    let state = trashState();
    fakeFetch((url, init) => {
      const json = (b: unknown) => new Response(JSON.stringify(b), { headers: { "content-type": "application/json" } });
      if (url === "/api/trash" && (init?.method ?? "GET") === "GET") return json(state);
      if (url === "/api/trash/series/3/restore" && init?.method === "POST") {
        state = { ...state, series: [] };
        return json({ restored: "series", id: 3 });
      }
      return undefined;
    });
    const view = mount(<TrashView />);
    await screen.findByText("Alte Ladung (ausgemustert)");
    expect(view.container.textContent).toContain("02.02.2030 18:30");
    expect(view.container.textContent).toContain("01.02.2030 09:15");
    expect(screen.getByText("Serie 3")).toBeTruthy();
    const row = screen.getByText("Serie 3").closest("tr")!;
    fireEvent.click(within(row).getByRole("button", { name: "Wiederherstellen" }));
    await waitFor(() => expect(screen.queryByText("Serie 3")).toBeNull());
    expect(calls.some((c) => c.method === "POST" && c.url === "/api/trash/series/3/restore")).toBe(true);
    expect(screen.getByText("Alte Ladung (ausgemustert)")).toBeTruthy();
  });

  it("löscht endgültig nur nach Rückfrage und kann den Papierkorb leeren", async () => {
    let state = trashState();
    const answers = [false, true, true];
    vi.stubGlobal("confirm", vi.fn(() => answers.shift() ?? false));
    fakeFetch((url, init) => {
      const json = (b: unknown) => new Response(JSON.stringify(b), { headers: { "content-type": "application/json" } });
      if (url === "/api/trash" && (init?.method ?? "GET") === "GET") return json(state);
      if (url === "/api/trash/loads/4" && init?.method === "DELETE") {
        state = { ...state, loads: [] };
        return json({ series: 0, loads: 1 });
      }
      if (url === "/api/trash" && init?.method === "DELETE") {
        state = { series: [], loads: [] };
        return json({ series: 1, loads: 0 });
      }
      return undefined;
    });
    mount(<TrashView />);
    const loadRow = (await screen.findByText("Alte Ladung (ausgemustert)")).closest("tr")!;
    fireEvent.click(within(loadRow).getByRole("button", { name: "Endgültig löschen" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false); // abgelehnt: nichts geschickt
    fireEvent.click(within(loadRow).getByRole("button", { name: "Endgültig löschen" }));
    await waitFor(() => expect(screen.queryByText("Alte Ladung (ausgemustert)")).toBeNull());
    fireEvent.click(screen.getByRole("button", { name: "Papierkorb leeren" }));
    await screen.findByText("Der Papierkorb ist leer.");
    expect(calls.filter((c) => c.method === "DELETE").map((c) => c.url)).toEqual(["/api/trash/loads/4", "/api/trash"]);
  });
});


// ---- Import und Laborierung (LL-17) ----
const jsonRes = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "content-type": "application/json" } });
const freeSeries = (n: number) => ({ ...SERIES, id: 20 + n, number: n, name: null, load_id: null, load_ids: [] as number[], shots: undefined, loads: undefined, load: undefined });

describe("Importseite", () => {
  const pickFiles = (view: ReturnType<typeof mount>, files: File[]) => {
    const input = view.container.querySelector('input[type="file"][multiple]') as HTMLInputElement;
    Object.defineProperty(input, "files", { value: files, configurable: true });
    fireEvent.change(input);
  };

  it("importiert eine ZIP und zeigt Ergebnis, Hinweise und die Liste der nicht zugeordneten Serien", async () => {
    let free = [freeSeries(1)];
    fakeFetch((url, init) => {
      if (url === "/api/series?unassigned=true") return jsonRes(free);
      if (url === "/api/import" && init?.method === "POST") {
        free = [freeSeries(1), freeSeries(2), freeSeries(3)];
        return jsonRes({ imported: [{ id: 22, number: 2 }, { id: 23, number: 3 }], skipped: 1, warnings: [{ code: "duplicate_series", message: "x", params: { label: "Serie 1", id: 21 } }], load_id: null });
      }
      return undefined;
    });
    const view = mount(<ImportView />);
    await screen.findByText("Serie 1");
    pickFiles(view, [new File(["x"], "karte.zip")]);
    await screen.findByText(/2 importiert · 1 bereits vorhanden/);
    expect(view.container.textContent).toContain("Serie 1 ist bereits als Serie 21 vorhanden und wurde übersprungen");
    await screen.findByText("Serie 3");
    expect(calls.filter((c) => c.method === "POST").map((c) => c.url)).toEqual(["/api/import"]);
  });

  it("meldet Fehler des Servers übersetzt und lehnt unbekannte Dateien ab", async () => {
    fakeFetch((url, init) => {
      if (url === "/api/series?unassigned=true") return jsonRes([]);
      if (url === "/api/import" && init?.method === "POST") return jsonRes({ detail: { code: "no_series", message: "roh", params: {} } }, 400);
      return undefined;
    });
    const view = mount(<ImportView />);
    await screen.findByText("Noch nichts vorhanden.");
    pickFiles(view, [new File(["x"], "notizen.txt")]);
    await screen.findByText(/Keine ZIP/);
    expect(calls.some((c) => c.method === "POST")).toBe(false);
    pickFiles(view, [new File(["x"], "karte.zip")]);
    await screen.findByText(/karte\.zip: Keine LabRadar-Serien gefunden/);
  });

  it("ordnet ausgewählte Serien einer Laborierung zu und nimmt es auf Wunsch zurück", async () => {
    const patches: { url: string; body: Record<string, unknown> }[] = [];
    fakeFetch((url, init) => {
      if (url === "/api/series?unassigned=true") return jsonRes([freeSeries(1), freeSeries(2)]);
      const m = url.match(/^\/api\/series\/(\d+)$/);
      if (m && init?.method === "PATCH") {
        patches.push({ url, body: JSON.parse(String(init.body)) });
        return jsonRes(freeSeries(Number(m[1]) - 20));
      }
      return undefined;
    });
    mount(<ImportView />);
    fireEvent.click(await screen.findByLabelText("Serien wählen Serie 1"));
    fireEvent.click(screen.getByLabelText("Serien wählen Serie 2"));
    expect(screen.getByText("2 ausgewählt")).toBeTruthy();
    const assign = screen.getByRole("button", { name: /^Zuordnen/ }) as HTMLButtonElement;
    expect(assign.disabled).toBe(true); // ohne Ziel
    fireEvent.change(screen.getByLabelText("Laborierung zuordnen"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: /^Zuordnen/ }));
    await screen.findByText(/2 Serien zugeordnet zu „Alpha-Last"/);
    expect(patches.map((p) => [p.url, p.body])).toEqual([["/api/series/21", { load_id: 3 }], ["/api/series/22", { load_id: 3 }]]);
    fireEvent.click(screen.getByRole("button", { name: "Rückgängig" }));
    await waitFor(() => expect(patches).toHaveLength(4));
    expect(patches.slice(2).map((p) => p.body)).toEqual([{ load_id: null }, { load_id: null }]);
  });

  it("löscht ausgewählte Serien nur nach Rückfrage (Papierkorb)", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    fakeFetch((url, init) => {
      if (init?.method === "DELETE") return new Response(null, { status: 204 });
      return url === "/api/series?unassigned=true" ? jsonRes([freeSeries(1), freeSeries(2)]) : undefined;
    });
    mount(<ImportView />);
    fireEvent.click(await screen.findByLabelText("Alle auswählen"));
    fireEvent.click(screen.getByRole("button", { name: /^Löschen \(2\)/ }));
    expect(confirmSpy.mock.calls[0][0]).toContain("Papierkorb");
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    confirmSpy.mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: /^Löschen \(2\)/ }));
    await waitFor(() => expect(calls.filter((c) => c.method === "DELETE").map((c) => c.url)).toEqual(["/api/series/21", "/api/series/22"]));
  });
});

describe("Laborierung: Formular und Zuordnung", () => {
  const base = (url: string) => {
    if (url === "/api/loads/5") return jsonRes({ ...load(5, "Leiter", null, null), series: [], parent: null, variants: [] });
    if (url.startsWith("/api/series")) return jsonRes([]);
    if (url === "/api/weapons") return jsonRes([]);
    return undefined;
  };

  it("legt eine neue Laborierung an: Zahlen mit Komma, leere Felder als null", async () => {
    const posts: Record<string, unknown>[] = [];
    fakeFetch((url, init) => {
      if (url === "/api/loads" && init?.method === "POST") {
        posts.push(JSON.parse(String(init.body)));
        return jsonRes(load(9, "Neu", null, null), 201);
      }
      return url === "/api/weapons" ? jsonRes([]) : undefined;
    });
    const view = mount(<LoadView id={null} />);
    const name = (await screen.findAllByRole("textbox"))[0] as HTMLInputElement;
    fireEvent.input(name, { target: { value: "  Neu  " } });
    const charge = view.container.querySelector("input[inputmode=decimal]") as HTMLInputElement;
    fireEvent.input(charge, { target: { value: "42,5" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Speichern" })[0]);
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0]).toMatchObject({ name: "Neu", trial_type: "single", weapon_id: null, status: null });
    expect(Object.values(posts[0]).includes(42.5)).toBe(true);
    expect(posts[0].notes).toBeNull();
    await waitFor(() => expect(window.location.hash).toBe("#/load/9"));
  });

  it("speichert nicht bei ungültiger Zahl und markiert das Feld", async () => {
    fakeFetch((url) => (url === "/api/weapons" ? jsonRes([]) : undefined));
    const view = mount(<LoadView id={null} />);
    const [name] = (await screen.findAllByRole("textbox")) as HTMLInputElement[];
    fireEvent.input(name, { target: { value: "X" } });
    const num = view.container.querySelector("input[inputmode=decimal]") as HTMLInputElement;
    fireEvent.input(num, { target: { value: "0x10" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Speichern" })[0]);
    await screen.findByText("Ungültige Zahl");
    expect(num.className).toContain("bad");
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("verlangt einen Namen", async () => {
    fakeFetch((url) => (url === "/api/weapons" ? jsonRes([]) : undefined));
    mount(<LoadView id={null} />);
    await screen.findAllByRole("textbox");
    fireEvent.click(screen.getAllByRole("button", { name: "Speichern" })[0]);
    expect((await screen.findByRole("alert")).textContent).toBe("Name");
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("wendet das Gewicht der Laborierung nur nach Rückfrage an", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    fakeFetch((url, init) => {
      if (url.startsWith("/api/loads/5/apply-weight") && init?.method === "POST") return jsonRes({ series: 2, weight_override_g: 11.66 });
      return base(url);
    });
    mount(<LoadView id={5} />);
    const button = await screen.findByRole("button", { name: /Gewicht der Laborierung anwenden/ });
    fireEvent.click(button);
    expect(confirmSpy).toHaveBeenCalled();
    expect(calls.some((c) => c.url.includes("apply-weight"))).toBe(false);
    confirmSpy.mockReturnValue(true);
    fireEvent.click(button);
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url === "/api/loads/5/apply-weight")).toBe(true));
  });
});
