// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { chartFileName, saveSvg, svgSize } from "../src/chartExport";

afterEach(() => vi.restoreAllMocks());

describe("chartExport", () => {
  it("liest die Größe aus dem viewBox", () => {
    expect(svgSize('<svg xmlns="x" viewBox="0 0 720 320"></svg>')).toEqual({ w: 720, h: 320 });
    expect(svgSize('<svg viewBox="0 0 800.5 400"></svg>')).toEqual({ w: 800.5, h: 400 });
    expect(svgSize("<svg></svg>")).toEqual({ w: 720, h: 320 });
  });

  it("leitet Dateinamen aus der Adresse ab", () => {
    expect(chartFileName("/api/charts/series/7.svg?lang=de&units=si", "png")).toBe("loadlog-series-7.png");
    expect(chartFileName("/api/charts/series/7/sequence.svg?window=3", "svg")).toBe("loadlog-series-7-sequence.svg");
    expect(chartFileName("/api/charts/compare.svg?ids=1,2", "svg")).toBe("loadlog-compare.svg");
    expect(chartFileName("/api/charts/ladder/5.svg?by=charge", "png")).toBe("loadlog-ladder-5.png");
    expect(chartFileName("/irgendwas", "svg")).toBe("loadlog-irgendwas.svg");
  });

  it("speichert das SVG als Datei", async () => {
    const created: Blob[] = [];
    vi.stubGlobal("URL", { ...URL, createObjectURL: (b: Blob) => (created.push(b), "blob:x"), revokeObjectURL: () => undefined });
    const clicks: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      clicks.push(this.download);
    });
    saveSvg("<svg></svg>", "loadlog-test.svg");
    expect(clicks).toEqual(["loadlog-test.svg"]);
    expect(created).toHaveLength(1);
    expect(created[0].type).toContain("image/svg+xml");
    expect(await created[0].text()).toBe("<svg></svg>");
    vi.unstubAllGlobals();
  });
});
