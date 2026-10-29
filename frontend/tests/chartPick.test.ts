import { describe, expect, it } from "vitest";
import { TEXTS } from "../src/i18n";
import { nearestPoint, parsePoints } from "../src/chartPick";

const lines = [
  { shot: 1, label: "Schuss 1", points: [[0, 0], [10, 10]] as [number, number][], vals: ["a", "b"] },
  { shot: 2, label: "Schuss 2", points: [[0, 20], [10, 22]] as [number, number][], vals: ["c", "d"] },
];

describe("chart hover/pick", () => {
  it("finds the nearest point across all lines", () => {
    expect(nearestPoint(lines, 9, 21)).toMatchObject({ shot: 2, val: "d" });
    expect(nearestPoint(lines, 1, 1)).toMatchObject({ shot: 1, val: "a" });
  });
  it("returns null when nothing is close enough", () => {
    expect(nearestPoint(lines, 200, 200)).toBeNull();
    expect(nearestPoint([], 0, 0)).toBeNull();
  });
  it("parses SVG point lists", () => {
    expect(parsePoints("1.5,2 3,4.25\n5,6")).toEqual([[1.5, 2], [3, 4.25], [5, 6]]);
    expect(parsePoints("")).toEqual([]);
  });
  it("has BC texts in both languages", () => {
    for (const k of ["bc", "bcHint"] as const) {
      expect(TEXTS.de[k]).toBeTruthy();
      expect(TEXTS.en[k]).toBeTruthy();
    }
  });
});

describe("import texts", () => {
  it("exist in both languages", () => {
    for (const k of ["importHereTitle", "importHereHint", "importedInto", "openLoad"] as const) {
      expect(TEXTS.de[k]).toBeTruthy();
      expect(TEXTS.en[k]).toBeTruthy();
    }
  });
});

describe("compare back link", () => {
  it("points to the common load, else the overview", async () => {
    const { backTarget } = await import("../src/views");
    expect(backTarget([{ load_ids: [7] }, { load_ids: [7] }])).toBe("#/load/7");
    expect(backTarget([{ load_ids: [7] }, { load_ids: [8] }])).toBe("#/");
    expect(backTarget([{ load_ids: [] }])).toBe("#/");
    expect(backTarget([{ load_ids: [3, 7] }, { load_ids: [7, 9] }])).toBe("#/load/7"); // Serie in mehreren Laborierungen
    expect(backTarget([])).toBe("#/");
  });
});
