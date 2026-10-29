import { describe, expect, it } from "vitest";
import { TEXTS } from "../src/i18n";
import { errorText, seriesLabel, sortSeries } from "../src/seriesSort";

const mk = (number: number, charge_gr: number | null, name: string | null = null) => ({ number, charge_gr, name });

describe("series label and sorting", () => {
  it("uses the name or falls back to 'Series N'", () => {
    expect(seriesLabel(mk(15, 40), "Series")).toBe("Series 15");
    expect(seriesLabel(mk(0, 40, "Handnotiz"), "Series")).toBe("Handnotiz");
  });
  const list = [mk(10, 41.5), mk(2, 40), mk(0, null, "Probe"), mk(3, 40.5)];
  it("keeps server order for date and does not mutate", () => {
    expect(sortSeries(list, "date", "Series").map((s) => s.number)).toEqual([10, 2, 0, 3]);
    expect(list.map((s) => s.number)).toEqual([10, 2, 0, 3]);
  });
  it("sorts by charge with empty charges last", () => {
    expect(sortSeries(list, "charge", "Series").map((s) => s.number)).toEqual([2, 3, 10, 0]);
  });
  it("sorts by name with natural number order", () => {
    expect(sortSeries(list, "name", "Series").map((s) => s.number)).toEqual([0, 2, 3, 10]);
  });
});

describe("chart error text", () => {
  it("extracts FastAPI details", () => {
    expect(errorText(422, JSON.stringify({ detail: "1 bis 60 Serien angeben" }))).toBe("1 bis 60 Serien angeben");
    expect(errorText(422, JSON.stringify({ detail: [{ msg: "ungültig" }] }))).toBe("ungültig");
  });
  it("falls back to the status", () => {
    expect(errorText(502, "<html>Bad gateway</html>")).toBe("HTTP 502");
    expect(errorText(500, "{}")).toBe("HTTP 500");
  });
  it("has texts in both languages", () => {
    for (const k of ["name", "nameHint", "sortBy", "sortDate", "sortCharge", "sortName", "chartError"] as const) {
      expect(TEXTS.de[k]).toBeTruthy();
      expect(TEXTS.en[k]).toBeTruthy();
    }
  });
});
