import type { Load } from "./api";

/** Wert des Statusfilters: aktive (ohne ausgemusterte), alle, ohne Status oder ein bestimmter Status. */
export type StatusFilter = "active" | "all" | "none" | "draft" | "testing" | "validated" | "retired";

/** Felder, in denen die Suche nach Text sucht. */
const SEARCH_KEYS = [
  "name", "weapon_name", "powder_maker", "powder_name", "powder_lot", "bullet_maker", "bullet_type", "bullet_lot",
  "primer", "case_maker", "notes",
] as const;

/** Laborierungen nach Suchtext (alle Wörter müssen vorkommen, Groß-/Kleinschreibung egal) und Status filtern.
 *  "active" blendet ausgemusterte aus, außer es wird gesucht: wer einen Namen eintippt, soll ihn auch dann finden. */
export function filterLoads<T extends Partial<Pick<Load, (typeof SEARCH_KEYS)[number]>> & { status?: string | null }>(list: T[], query: string, status: StatusFilter): T[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  return list.filter((l) => {
    if (status === "active") {
      if (l.status === "retired" && words.length === 0) return false;
    } else if (status === "none" ? l.status : status !== "all" && l.status !== status) return false;
    if (words.length === 0) return true;
    const hay = SEARCH_KEYS.map((k) => l[k] ?? "").join(" ").toLowerCase();
    return words.every((w) => hay.includes(w));
  });
}

/** Anzahl der durch den Filter "active" ausgeblendeten (ausgemusterten) Laborierungen; 0, wenn gesucht wird oder ein anderer Filter gilt. */
export function hiddenRetired(list: { status?: string | null }[], query: string, status: StatusFilter): number {
  if (status !== "active" || query.trim()) return 0;
  return list.filter((l) => l.status === "retired").length;
}
