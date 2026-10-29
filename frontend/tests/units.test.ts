import { describe, expect, it } from "vitest";
import { TEXTS, LOAD_GROUPS } from "../src/i18n";
import { dOut, dateRange, eOut, fmt, grains, parseNum, vOut } from "../src/units";

describe("units", () => {
  it("converts SI to imperial", () => {
    expect(vOut(304.8, "imp")).toBeCloseTo(1000, 6);
    expect(vOut(300, "si")).toBe(300);
    expect(dOut(9.144, "imp")).toBeCloseTo(10, 6);
    expect(eOut(1.3558179483314, "imp")).toBeCloseTo(1, 9);
    expect(grains(11.6638)).toBeCloseTo(180, 2);
  });
  it("formats the shot date as single value or range", () => {
    expect(dateRange(["2030-03-01T10:00:00", "2030-03-01T10:05:00"], "de")).toBe("01.03.2030");
    expect(dateRange(["2030-03-02T23:59:00", "2030-03-01T10:00:00"], "en")).toBe("01/03/2030 – 02/03/2030");
    expect(dateRange([], "de")).toBe("–");
  });
  it("formats with locale decimal separator", () => {
    expect(fmt(289.34, 1, "de")).toBe("289,3");
    expect(fmt(289.34, 1, "en")).toBe("289.3");
    expect(fmt(null, 1, "de")).toBe("–");
    expect(fmt(NaN, 1, "en")).toBe("–");
  });
  it("parses numbers with comma or dot", () => {
    expect(parseNum("42,5")).toBe(42.5);
    expect(parseNum(" 42.5 ")).toBe(42.5);
    expect(parseNum("")).toBeNull();
    expect(parseNum("abc")).toBeUndefined();
  });
});

describe("i18n", () => {
  it("has identical keys and no empty strings in both languages", () => {
    expect(Object.keys(TEXTS.de).sort()).toEqual(Object.keys(TEXTS.en).sort());
    for (const lang of ["de", "en"] as const)
      for (const [k, v] of Object.entries(TEXTS[lang])) expect(v, `${lang}.${k}`).not.toBe("");
  });
  it("has a label for every load form field", () => {
    for (const g of LOAD_GROUPS) {
      expect(TEXTS.de[g.title]).toBeTruthy();
      for (const f of g.fields) expect(Object.keys(TEXTS.de)).toContain(f.key);
    }
  });
});

import { fromDraft } from "../src/views";

describe("load form conversion", () => {
  const base = { name: " Test ", trial_type: "ladder", weapon_id: "3" } as Record<string, string>;
  it("converts numbers (comma/dot), integers and empty values", () => {
    const { data, bad } = fromDraft({ ...base, charge_gr: "42,5", case_firings: "2.4", powder_name: "  P  ", notes: "" });
    expect(bad).toEqual([]);
    expect(data).toMatchObject({ name: "Test", trial_type: "ladder", weapon_id: 3, charge_gr: 42.5, case_firings: 2, powder_name: "P", notes: null, coal_mm: null });
  });
  it("reports invalid numbers", () => {
    expect(fromDraft({ ...base, charge_gr: "abc", coal_mm: "71,2x" }).bad.sort()).toEqual(["charge_gr", "coal_mm"]);
  });
});
