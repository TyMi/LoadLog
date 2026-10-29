import { isNote, renderNote } from "./messages";

export interface Labeled {
  name: string | null;
  number: number;
}
export type SortKey = "date" | "charge" | "name";

export const seriesLabel = (s: Labeled, word: string) => s.name || `${word} ${s.number}`;

/** Serien sortiert (Kopie). "date" = Reihenfolge des Servers (erster Schuss); leere Pulvermengen stehen hinten. */
export function sortSeries<T extends Labeled & { charge_gr: number | null }>(list: T[], by: SortKey, word: string): T[] {
  const out = [...list];
  if (by === "charge") {
    out.sort((a, b) => (a.charge_gr ?? Infinity) - (b.charge_gr ?? Infinity));
  } else if (by === "name") {
    out.sort((a, b) => seriesLabel(a, word).localeCompare(seriesLabel(b, word), undefined, { numeric: true }));
  }
  return out;
}

/** Pydantic-/FastAPI-Fehlerdetails lesbar machen: "Feld: Meldung; Feld2: Meldung". */
export function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (isNote(detail)) return renderNote(detail);
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d) => {
        const loc = Array.isArray(d?.loc) ? d.loc.filter((x: unknown) => x !== "body" && x !== "query" && x !== "path").join(".") : "";
        return d?.msg ? (loc ? `${loc}: ${d.msg}` : String(d.msg)) : "";
      })
      .filter(Boolean);
    if (parts.length) return parts.join("; ");
  }
  return JSON.stringify(detail);
}

/** Lesbarer Text für eine fehlgeschlagene Anfrage (FastAPI liefert {"detail": ...}). */
export function errorText(status: number, body: string): string {
  try {
    const d = JSON.parse(body)?.detail;
    if (d !== undefined && d !== "") return formatDetail(d);
  } catch {
    /* kein JSON */
  }
  return `HTTP ${status}`;
}
