import type { Note } from "./messages";
import { errorText, formatDetail } from "./seriesSort";
import type { Lang, Units } from "./units";

export interface Stats {
  n: number;
  avg: number | null;
  sd: number | null;
  es: number | null;
  vmin: number | null;
  vmax: number | null;
  energy_avg_j: number | null;
  mip_avg: number | null;
  mip_min: number | null;
}
export interface Weapon {
  id: number;
  name: string;
  caliber?: string | null;
  barrel_length_mm?: number | null;
  twist?: string | null;
  notes?: string | null;
}
export type TrialType = "single" | "ladder" | "seating";
export type LoadStatus = "draft" | "testing" | "validated" | "retired";
export interface LoadData {
  name: string;
  status?: LoadStatus | null;
  trial_type: TrialType;
  weapon_id?: number | null;
  powder_maker?: string | null;
  powder_name?: string | null;
  powder_lot?: string | null;
  charge_gr?: number | null;
  case_maker?: string | null;
  case_firings?: number | null;
  case_trim_mm?: number | null;
  primer?: string | null;
  bullet_maker?: string | null;
  bullet_type?: string | null;
  bullet_weight_gr?: number | null;
  bullet_lot?: string | null;
  coal_mm?: number | null;
  seating_depth_mm?: number | null;
  seating_ref?: string | null;
  crimp?: string | null;
  temperature_c?: number | null;
  notes?: string | null;
}
export interface LoadRef {
  id: number;
  name: string;
  status: LoadStatus | null;
}
export interface Load extends LoadData {
  id: number;
  parent_id?: number | null;
  weapon_name: string | null;
  series_count: number;
  shots_total: number;
  stats: Stats;
}
export interface SeriesSummary {
  id: number;
  number: number;
  name: string | null;
  device_id: string | null;
  load_id: number | null; // erste Laborierung
  load_ids: number[]; // alle Laborierungen der Serie
  taken_at: string | null;
  charge_gr: number | null;
  seating_depth_mm: number | null;
  note: string | null;
  group_text: string | null;
  trigger_mode: string | null;
  shots_total: number;
  weight_g: number | null;
  weight_override_g: number | null;
  weight_measured_g: number | null;
  stats: Stats;
}
export interface Shot {
  number: number;
  taken_at: string;
  weight_g: number;
  v0_ms: number;
  energy0_j: number;
  power_factor: number | null;
  signal_strength: number | null;
  excluded: boolean;
  distances_m: number[];
  velocities_ms: number[];
  energies_j: number[];
  mip: number | null;
}
export interface BcFit {
  n: number;
  avg: number | null;
  sd: number | null;
}
export interface SeriesDetail extends SeriesSummary {
  bc: { g1: BcFit; g7: BcFit };
  shots: Shot[];
  load: (LoadData & { id: number }) | null;
  loads: (LoadData & { id: number })[];
}
export interface TrashSeries {
  id: number;
  number: number;
  name: string | null;
  deleted_at: string;
  shots_total: number;
  taken_at: string | null;
}
export interface TrashLoad {
  id: number;
  name: string;
  status: LoadStatus | null;
  deleted_at: string;
  series_count: number;
}
export interface ImportResult {
  imported: { id: number; number: number }[];
  skipped: number;
  assigned?: number; // vorhandene Serien, die zusätzlich der Laborierung zugeordnet wurden
  warnings: (Note | string)[];
  load_id: number | null;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = formatDetail(j.detail);
    } catch {
      /* Text bleibt statusText */
    }
    throw new ApiError(res.status, msg);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  health: () => req<{ status: string; pdf: boolean; version: string; manual_version: string }>("GET", "/api/health"),
  restore: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/system/restore", { method: "POST", body: form, headers: { "X-LoadLog-Confirm": "restore" } });
    if (!res.ok) throw new ApiError(res.status, errorText(res.status, await res.text()));
    return (await res.json()) as { weapons: number; loads: number; series: number; shots: number };
  },
  settings: () => req<{ backup_keep: number }>("GET", "/api/settings"),
  setSettings: (body: { backup_keep: number }) => req<{ backup_keep: number }>("PATCH", "/api/settings", body),
  loads: () => req<Load[]>("GET", "/api/loads"),
  load: (id: number) => req<Load & { weapon: Weapon | null; parent: LoadRef | null; variants: LoadRef[]; series: SeriesSummary[] }>("GET", `/api/loads/${id}`),
  createLoad: (d: Partial<LoadData>) => req<Load>("POST", "/api/loads", d),
  updateLoad: (id: number, d: Partial<LoadData>) => req<Load>("PUT", `/api/loads/${id}`, d),
  trash: () => req<{ series: TrashSeries[]; loads: TrashLoad[] }>("GET", "/api/trash"),
  restoreTrash: (kind: "series" | "loads", id: number) => req<unknown>("POST", `/api/trash/${kind}/${id}/restore`),
  purgeTrash: (kind: "series" | "loads", id: number) => req<unknown>("DELETE", `/api/trash/${kind}/${id}`),
  emptyTrash: () => req<unknown>("DELETE", "/api/trash"),
  duplicateLoad: (id: number, name: string) => req<Load>("POST", `/api/loads/${id}/duplicate`, { name }),
  deleteLoad: (id: number) => req<void>("DELETE", `/api/loads/${id}`),
  applyWeight: (id: number, clear = false) =>
    req<{ series: number; weight_override_g: number | null }>("POST", `/api/loads/${id}/apply-weight${clear ? "?clear=true" : ""}`),
  weapons: () => req<Weapon[]>("GET", "/api/weapons"),
  createWeapon: (d: Partial<Weapon>) => req<Weapon>("POST", "/api/weapons", d),
  updateWeapon: (id: number, d: Partial<Weapon>) => req<Weapon>("PUT", `/api/weapons/${id}`, d),
  deleteWeapon: (id: number) => req<void>("DELETE", `/api/weapons/${id}`),
  series: (unassigned = false) => req<SeriesSummary[]>("GET", `/api/series?unassigned=${unassigned}`),
  seriesDetail: (id: number) => req<SeriesDetail>("GET", `/api/series/${id}`),
  addToLoad: (sid: number, lid: number) => req<SeriesSummary>("PUT", `/api/series/${sid}/loads/${lid}`),
  removeFromLoad: (sid: number, lid: number) => req<SeriesSummary>("DELETE", `/api/series/${sid}/loads/${lid}`),
  patchSeries: (id: number, d: Record<string, unknown>) => req<SeriesSummary>("PATCH", `/api/series/${id}`, d),
  deleteSeries: (id: number) => req<void>("DELETE", `/api/series/${id}`),
  setExcluded: (id: number, n: number, excluded: boolean) =>
    req<SeriesDetail>("PUT", `/api/series/${id}/shots/${n}/excluded`, { excluded }),
  async importZip(file: File, loadId?: number, assignExisting = false): Promise<ImportResult> {
    const form = new FormData();
    form.append("file", file);
    const query = loadId === undefined ? "" : `?load_id=${loadId}${assignExisting ? "&assign_existing=true" : ""}`;
    const res = await fetch(`/api/import${query}`, { method: "POST", body: form });
    if (!res.ok) {
      const j = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, formatDetail(j.detail));
    }
    return res.json();
  },
};

const q = (o: Record<string, string | number | boolean | undefined>) =>
  Object.entries(o)
    .filter(([, v]) => v !== undefined)
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join("&");

export const urls = {
  seriesChart: (id: number, o: { sel?: number; lang: Lang; units: Units }) =>
    `/api/charts/series/${id}.svg?${q({ ...o, theme: "dark" })}`,
  sequenceChart: (id: number, o: { window: number; lang: Lang; units: Units }) =>
    `/api/charts/series/${id}/sequence.svg?${q({ ...o, theme: "dark" })}`,
  energyChart: (id: number, o: { lang: Lang; units: Units }) => `/api/charts/series/${id}/energy.svg?${q({ ...o, theme: "dark" })}`,
  compareChart: (ids: number[], o: { trend: boolean; lang: Lang; units: Units }) =>
    `/api/charts/compare.svg?${q({ ids: ids.join(","), ...o, theme: "dark" })}`,
  ladderChart: (id: number, o: { by: "charge" | "seating"; lang: Lang; units: Units }) =>
    `/api/charts/ladder/${id}.svg?${q({ ...o, theme: "dark" })}`,
  reportSeries: (id: number, o: { lang: Lang; units: Units }) => `/api/reports/series/${id}?${q(o)}`,
  reportLoad: (id: number, o: { lang: Lang; units: Units }) => `/api/reports/load/${id}?${q(o)}`,
  reportCompare: (ids: number[], o: { lang: Lang; units: Units }) => `/api/reports/compare?${q({ ids: ids.join(","), ...o })}`,
  manual: (lang: Lang, version?: string) => `/manual/${version ? `${version}/` : ""}${lang}/`,
  backup: "/api/system/backup",
  exportSeries: (id: number, o: { lang: Lang; units: Units }) => `/api/export/series/${id}.csv?${q(o)}`,
  exportLoad: (id: number, o: { lang: Lang; units: Units }) => `/api/export/load/${id}.csv?${q(o)}`,
};
