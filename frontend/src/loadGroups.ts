export type GroupBy = "none" | "weapon";
export type LoadViewMode = "cards" | "list";

export interface Group<T> {
  key: string;
  title: string | null; // null = keine Überschrift (ungruppiert)
  items: T[];
}

interface WithWeapon {
  weapon_id?: number | null;
  weapon_name: string | null;
}

/** Laborierungen nach Waffe gruppieren. Gruppen alphabetisch, "ohne Waffe" zuletzt; die Reihenfolge innerhalb bleibt erhalten. */
export function groupLoads<T extends WithWeapon>(list: T[], by: GroupBy, noWeapon: string): Group<T>[] {
  if (by === "none") return [{ key: "all", title: null, items: list }];
  const groups = new Map<string, Group<T>>();
  for (const l of list) {
    const key = l.weapon_id ? `w${l.weapon_id}` : "none";
    const g = groups.get(key) ?? { key, title: l.weapon_id ? (l.weapon_name ?? noWeapon) : noWeapon, items: [] };
    g.items.push(l);
    groups.set(key, g);
  }
  return [...groups.values()].sort((a, b) =>
    a.key === "none" ? 1 : b.key === "none" ? -1 : (a.title ?? "").localeCompare(b.title ?? "", undefined, { numeric: true }),
  );
}
