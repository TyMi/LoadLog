import type { Load } from "./api";

/** Wert des Statusfilters: alle, ohne Status oder ein bestimmter Status. */
export type StatusFilter = "all" | "none" | "draft" | "testing" | "validated" | "retired";

/** Felder, in denen die Suche nach Text sucht. */
const SEARCH_KEYS = [
  "name", "weapon_name", "powder_maker", "powder_name", "powder_lot", "bullet_maker", "bullet_type", "bullet_lot",
  "primer", "case_maker", "notes",
] as const;

/** Laborierungen nach Suchtext (alle Wörter müssen vorkommen, Groß-/Kleinschreibung egal) und Status filtern. */
export function filterLoads<T extends Partial<Pick<Load, (typeof SEARCH_KEYS)[number]>> & { status?: string | null }>(list: T[], query: string, status: StatusFilter): T[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  return list.filter((l) => {
    if (status === "none" ? l.status : status !== "all" && l.status !== status) return false;
    if (words.length === 0) return true;
    const hay = SEARCH_KEYS.map((k) => l[k] ?? "").join(" ").toLowerCase();
    return words.every((w) => hay.includes(w));
  });
}
