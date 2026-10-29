import { describe, expect, it, vi } from "vitest";
import { api } from "../src/api";
import { TEXTS } from "../src/i18n";
import { sourcesFromDrop } from "../src/importSources";
import { renderNote } from "../src/messages";
import { errorText, formatDetail } from "../src/seriesSort";

describe("error details", () => {
  it("makes validation errors readable", () => {
    const detail = [{ type: "less_than_equal", loc: ["body", "charge_gr"], msg: "Input should be less than or equal to 500" }];
    expect(formatDetail(detail)).toBe("charge_gr: Input should be less than or equal to 500");
    expect(formatDetail([{ loc: ["query", "ids"], msg: "a" }, { loc: ["body", "name"], msg: "b" }])).toBe("ids: a; name: b");
    expect(formatDetail("Nicht gefunden")).toBe("Nicht gefunden");
    expect(formatDetail({ x: 1 })).toBe('{"x":1}');
  });
  it("is used for chart errors too", () => {
    expect(errorText(422, JSON.stringify({ detail: [{ loc: ["query", "ids"], msg: "bad" }] }))).toBe("ids: bad");
  });
  it("has the new texts in both languages", () => {
    for (const k of ["navigation", "language", "noLabradarFiles", "actionFailed"] as const) {
      expect(TEXTS.de[k]).toBeTruthy();
      expect(TEXTS.en[k]).toBeTruthy();
    }
  });
});

describe("drop handling", () => {
  const file = (name: string) => ({ name }) as unknown as File;
  const item = (f: File | null, entry: unknown) => ({ kind: "file", getAsFile: () => f, webkitGetAsEntry: () => entry });
  it("keeps entries and files together when getAsFile() is null", async () => {
    const dir = {
      isFile: false,
      isDirectory: true,
      name: "LBR",
      fullPath: "/LBR",
      createReader: () => {
        let done = false;
        return {
          readEntries: (ok: (e: unknown[]) => void) => {
            ok(done ? [] : [{ isFile: true, isDirectory: false, name: "SR0001.lbr", fullPath: "/LBR/SR0001/SR0001.lbr", file: (f: (x: File) => void) => f(file("SR0001.lbr")) }]);
            done = true;
          },
        };
      },
    };
    const dt = {
      items: [
        item(null, { isFile: true, isDirectory: false, name: "weg.txt" }), // kein File lesbar: darf die Zuordnung nicht verschieben
        item(null, dir),
        item(file("karte.zip"), { isFile: true, isDirectory: false, name: "karte.zip" }),
      ],
    } as unknown as DataTransfer;
    const out = await sourcesFromDrop(dt);
    expect(out.map((s) => `${s.kind}:${s.name}`)).toEqual(["folder:LBR", "file:karte.zip"]);
    const folder = out[0];
    expect(folder.kind === "folder" && folder.files.map((f) => f.path)).toEqual(["LBR/SR0001/SR0001.lbr"]);
  });
});

describe("Servermeldungen mit Code", () => {
  const note = { code: "ids_count", message: "1 bis 60 Serien angeben", params: { max: 60 } };
  it("werden je Sprache übersetzt", () => {
    expect(renderNote(note, "en")).toBe("Specify 1 to 60 series");
    expect(renderNote(note, "de")).toBe("1 bis 60 Serien angeben");
  });
  it("verschachtelte Meldungen werden mit übersetzt", () => {
    const n = { code: "series_skipped", message: "x", params: { label: { code: "series_label", message: "Serie 7", params: { no: 7 } }, reason: { code: "csv_no_series", message: "r", params: {} } } };
    expect(renderNote(n, "en")).toBe("Series 7 skipped: Report without series number");
  });
  it("unbekannter Code fällt auf den Servertext zurück", () => {
    expect(renderNote({ code: "neu", message: "Serientext", params: {} }, "en")).toBe("Serientext");
  });
  it("errorText liest den Code aus der Fehlerantwort", () => {
    expect(errorText(404, JSON.stringify({ detail: { code: "not_found", message: "Nicht gefunden: x", params: { what: "series 5" } } }))).toBe("Nicht gefunden: series 5");
  });
});


describe("Importfehler werden lesbar angezeigt", () => {
  it("zeigt die übersetzte Meldung statt [object Object]", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: { code: "zip_invalid", message: "Keine gültige ZIP-Datei", params: {} } }), { status: 400 })));
    await expect(api.importZip(new File(["x"], "x.zip"))).rejects.toThrow("Keine gültige ZIP-Datei");
    vi.unstubAllGlobals();
  });
  it("die neuen Meldungscodes sind in beiden Sprachen übersetzt", () => {
    for (const code of ["length_required", "cross_site_blocked", "file_unreadable", "series_number_adjusted", "weight_out_of_range", "upload_too_large"]) {
      expect(renderNote({ code, message: "x", params: { max: 50, name: "a", label: "L", head: 1 } }, "en")).not.toBe("x");
      expect(renderNote({ code, message: "x", params: { max: 50, name: "a", label: "L", head: 1 } }, "de")).not.toBe("x");
    }
  });
});
