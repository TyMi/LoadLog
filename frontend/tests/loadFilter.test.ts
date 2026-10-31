import { describe, expect, it } from "vitest";
import { filterLoads } from "../src/loadFilter";

const loads = [
  { name: "Leiter A", status: "testing", powder_name: "N140", bullet_type: "SMK", weapon_name: "Sport" },
  { name: "Haupt", status: "validated", powder_name: "Vihtavuori N150", weapon_name: "Sport" },
  { name: "Alt", status: null, powder_name: "H4350", notes: "Test mit Lotwechsel" },
  { name: "Weg", status: "retired" },
];

describe("filterLoads", () => {
  it("ohne Suche und Status bleibt alles", () => expect(filterLoads(loads, "", "all")).toHaveLength(4));
  it("sucht Wörter unabhängig von Groß- und Kleinschreibung in mehreren Feldern", () => {
    expect(filterLoads(loads, "n150", "all").map((l) => l.name)).toEqual(["Haupt"]);
    expect(filterLoads(loads, "sport smk", "all").map((l) => l.name)).toEqual(["Leiter A"]);
    expect(filterLoads(loads, "lotwechsel", "all").map((l) => l.name)).toEqual(["Alt"]);
    expect(filterLoads(loads, "gibtsnicht", "all")).toEqual([]);
  });
  it("filtert nach Status, auch ohne Status", () => {
    expect(filterLoads(loads, "", "validated").map((l) => l.name)).toEqual(["Haupt"]);
    expect(filterLoads(loads, "", "none").map((l) => l.name)).toEqual(["Alt"]);
    expect(filterLoads(loads, "sport", "testing").map((l) => l.name)).toEqual(["Leiter A"]);
  });
});
