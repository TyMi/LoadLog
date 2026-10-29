// Anzeige-Umrechnung: intern/API immer SI (m/s, m, J, g).
export type Units = "si" | "imp";
export type Lang = "de" | "en";

const MS_PER_FPS = 0.3048;
const M_PER_YD = 0.9144;
const J_PER_FTLBF = 1.3558179483314;
const G_PER_GRAIN = 0.06479891;

export const vOut = (ms: number, u: Units) => (u === "imp" ? ms / MS_PER_FPS : ms);
export const dOut = (m: number, u: Units) => (u === "imp" ? m / M_PER_YD : m);
export const eOut = (j: number, u: Units) => (u === "imp" ? j / J_PER_FTLBF : j);
export const grains = (g: number) => g / G_PER_GRAIN;
export const unitNames = (u: Units) => (u === "imp" ? { v: "fps", d: "yd", e: "ft-lbf" } : { v: "m/s", d: "m", e: "J" });

/** Datum der Schüsse (ISO-Zeitstempel): ein Datum, bei mehreren Tagen "von – bis". Reiner Textschnitt, keine Zeitzonen. */
export function dateRange(isos: string[], lang: Lang): string {
  const days = [...new Set(isos.map((s) => s.slice(0, 10)))].sort();
  if (days.length === 0) return "–";
  const f = (d: string) => (lang === "de" ? `${d.slice(8, 10)}.${d.slice(5, 7)}.${d.slice(0, 4)}` : `${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}`);
  return days.length === 1 ? f(days[0]) : `${f(days[0])} – ${f(days[days.length - 1])}`;
}

export function fmt(x: number | null | undefined, decimals: number, lang: Lang): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "–";
  const s = x.toFixed(decimals);
  return lang === "de" ? s.replace(".", ",") : s;
}

/** Eingabe mit Komma oder Punkt; leer => null; ungültig => undefined. */
export function parseNum(text: string): number | null | undefined {
  const t = text.trim().replace(",", ".");
  if (t === "") return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : undefined;
}
