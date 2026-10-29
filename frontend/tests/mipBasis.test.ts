import { describe, expect, it } from "vitest";
import { TEXTS } from "../src/i18n";
import { mipBasis } from "../src/mipBasis";

const w = { mipBasis: "Basis", mipMixed: "Mehrere", mipNoWeight: "Kein Gewicht", mipMismatch: "Abweichend", mipOverridden: "überschrieben" };
const G230 = 230 * 0.06479891;

describe("mipBasis", () => {
  it("names the weight taken from the measurement", () => {
    expect(mipBasis([G230, G230], null, "de", w).text).toBe("Basis 14,90 g (230 gr)");
  });
  it("warns when the load's weight differs", () => {
    const r = mipBasis([G230], 185, "de", w);
    expect(r.warn).toBe("Abweichend 185 gr");
    expect(mipBasis([G230], 230, "de", w).warn).toBeUndefined();
    expect(mipBasis([G230], null, "de", w).warn).toBeUndefined();
  });
  it("lists different weights and handles missing ones", () => {
    expect(mipBasis([G230, 11.66], null, "en", w).text).toBe("Mehrere 11.66 g (180 gr), 14.90 g (230 gr)");
    expect(mipBasis([null, 0], null, "de", w).text).toBe("Kein Gewicht");
    expect(mipBasis([], null, "de", w).text).toBe("Kein Gewicht");
  });
  it("marks overridden weights", () => {
    expect(mipBasis([G230], null, "de", w, { count: 2, total: 3 }).text).toBe("Basis 14,90 g (230 gr) · überschrieben (2/3)");
    expect(mipBasis([G230], null, "de", w, { count: 0, total: 3 }).text).toBe("Basis 14,90 g (230 gr)");
  });
  it("has texts in both languages", () => {
    for (const k of ["mipBasis", "mipMixed", "mipNoWeight", "mipMismatch", "mipOverridden", "weightOverride", "weightOverrideHint", "weightMeasured", "applyWeight", "applyWeightConfirm", "clearWeight", "weightApplied"] as const) {
      expect(TEXTS.de[k]).toBeTruthy();
      expect(TEXTS.en[k]).toBeTruthy();
    }
  });
});
