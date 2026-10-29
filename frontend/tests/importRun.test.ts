import { describe, expect, it } from "vitest";
import { TEXTS } from "../src/i18n";
import { emptyAggregate, merge } from "../src/importRun";

describe("import aggregation", () => {
  it("sums results of several sources", () => {
    let a = emptyAggregate();
    a = merge(a, { imported: [{ id: 1, number: 1 }], skipped: 2, warnings: ["w1"], load_id: null });
    a = merge(a, { imported: [{ id: 2, number: 1 }, { id: 3, number: 2 }], skipped: 0, warnings: [], load_id: 7 });
    expect(a.imported.map((i) => i.id)).toEqual([1, 2, 3]);
    expect(a.skipped).toBe(2);
    expect(a.warnings).toEqual(["w1"]);
    expect(a.load_id).toBe(7);
    expect(a.sources).toBe(2);
  });
  it("keeps the last load id when later sources have none", () => {
    let a = merge(emptyAggregate(), { imported: [], skipped: 0, warnings: [], load_id: 4 });
    a = merge(a, { imported: [], skipped: 0, warnings: [], load_id: null });
    expect(a.load_id).toBe(4);
  });
  it("has the new import and delete texts in both languages", () => {
    for (const k of ["chooseFolder", "importNothing", "deleteSelected", "deleteSeriesConfirm", "deleteFailed"] as const) {
      expect(TEXTS.de[k]).toBeTruthy();
      expect(TEXTS.en[k]).toBeTruthy();
    }
  });
});
