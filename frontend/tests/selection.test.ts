import { describe, expect, it } from "vitest";
import { TEXTS } from "../src/i18n";
import { toggleAll, togglePick } from "../src/selection";

describe("selection", () => {
  it("toggles single ids", () => {
    expect(togglePick([], 3)).toEqual([3]);
    expect(togglePick([3, 4], 3)).toEqual([4]);
  });
  it("selects all, then clears", () => {
    expect(toggleAll([], [1, 2, 3])).toEqual([1, 2, 3]);
    expect(toggleAll([1], [1, 2, 3])).toEqual([1, 2, 3]);
    expect(toggleAll([1, 2, 3], [1, 2, 3])).toEqual([]);
    expect(toggleAll([], [])).toEqual([]);
  });
  it("has texts in both languages", () => {
    for (const k of ["selectAll", "chooseLoad", "assignSelected", "assignedN", "undo", "selectedN", "assignFailed"] as const) {
      expect(TEXTS.de[k]).toBeTruthy();
      expect(TEXTS.en[k]).toBeTruthy();
    }
  });
});
