import { describe, expect, it } from "vitest";
import { groupLoads } from "../src/loadGroups";

const L = (id: number, weapon_id: number | null, weapon_name: string | null) => ({ id, weapon_id, weapon_name });
const data = [L(1, 2, "Zebra"), L(2, null, null), L(3, 1, "Alpha"), L(4, 2, "Zebra")];

describe("groupLoads", () => {
  it("ohne Gruppierung eine Gruppe ohne Titel, Reihenfolge bleibt", () => {
    const g = groupLoads(data, "none", "Ohne Waffe");
    expect(g).toHaveLength(1);
    expect(g[0].title).toBeNull();
    expect(g[0].items.map((x) => x.id)).toEqual([1, 2, 3, 4]);
  });
  it("nach Waffe: alphabetisch, ohne Waffe zuletzt", () => {
    const g = groupLoads(data, "weapon", "Ohne Waffe");
    expect(g.map((x) => x.title)).toEqual(["Alpha", "Zebra", "Ohne Waffe"]);
    expect(g[1].items.map((x) => x.id)).toEqual([1, 4]);
  });
  it("gleichnamige Waffen mit verschiedener ID bleiben getrennt", () => {
    const g = groupLoads([L(1, 1, "X"), L(2, 2, "X")], "weapon", "-");
    expect(g).toHaveLength(2);
  });
  it("leere Liste", () => {
    expect(groupLoads([], "weapon", "-")).toEqual([]);
  });
});
