import { describe, expect, it } from "vitest";
import { isRelevant, isUploadFile, sourcesFromInput } from "../src/importSources";
import { crc32, zipStore } from "../src/zip";

const enc = new TextEncoder();

/** Liest das Zentralverzeichnis zurück (unabhängige Gegenprobe zum Schreiber). */
function readZip(z: Uint8Array) {
  const v = new DataView(z.buffer, z.byteOffset, z.byteLength);
  const eocd = z.length - 22;
  expect(v.getUint32(eocd, true)).toBe(0x06054b50);
  const n = v.getUint16(eocd + 10, true);
  let p = v.getUint32(eocd + 16, true);
  const out: { name: string; crc: number; data: string }[] = [];
  for (let i = 0; i < n; i++) {
    expect(v.getUint32(p, true)).toBe(0x02014b50);
    const crc = v.getUint32(p + 16, true);
    const size = v.getUint32(p + 24, true);
    const nameLen = v.getUint16(p + 28, true);
    const lho = v.getUint32(p + 42, true);
    const name = new TextDecoder().decode(z.slice(p + 46, p + 46 + nameLen));
    expect(v.getUint32(lho, true)).toBe(0x04034b50);
    const start = lho + 30 + v.getUint16(lho + 26, true);
    out.push({ name, crc, data: new TextDecoder().decode(z.slice(start, start + size)) });
    p += 46 + nameLen;
  }
  return out;
}

describe("zip writer", () => {
  it("computes the standard CRC32", () => {
    expect(crc32(enc.encode("123456789"))).toBe(0xcbf43926);
    expect(crc32(new Uint8Array())).toBe(0);
  });
  it("writes a readable archive", () => {
    const z = zipStore([
      { name: "LBR/SR0001/SR0001.lbr", data: enc.encode("abc") },
      { name: "LBR/SR0001/TRK/Shot0001 Track.csv", data: enc.encode("Zeit;Wert äöü") },
      { name: "leer.txt", data: new Uint8Array() },
    ]);
    const files = readZip(z);
    expect(files.map((f) => f.name)).toEqual(["LBR/SR0001/SR0001.lbr", "LBR/SR0001/TRK/Shot0001 Track.csv", "leer.txt"]);
    expect(files[0].data).toBe("abc");
    expect(files[1].data).toBe("Zeit;Wert äöü");
    expect(files[0].crc).toBe(crc32(enc.encode("abc")));
  });
});

describe("import sources", () => {
  it("recognises the files the server needs", () => {
    expect(isRelevant("LBR/SR0012/SR0012.lbr")).toBe(true);
    expect(isRelevant("SD/LBR/SR0012/SR0012 Report.csv")).toBe(true);
    expect(isRelevant("LBR/SR0012/TRK/Shot0003 Track.csv")).toBe(true);
    expect(isRelevant("LBR/SR0012/notes.txt")).toBe(false);
    expect(isRelevant("LBR/LBR-0000000.LID")).toBe(false);
  });
  it("accepts zip and grtload uploads", () => {
    expect(isUploadFile("card.ZIP")).toBe(true);
    expect(isUploadFile("load.grtload")).toBe(true);
    expect(isUploadFile("photo.png")).toBe(false);
  });
  it("makes one source per plain file and one folder source per directory pick", () => {
    const f = (name: string, rel = "") => ({ name, webkitRelativePath: rel }) as unknown as File; // Node 18 kennt File nicht
    expect(sourcesFromInput([f("a.zip"), f("b.grtload")]).map((s) => s.kind)).toEqual(["file", "file"]);
    const folder = sourcesFromInput([f("SR0001.lbr", "LBR/SR0001/SR0001.lbr"), f("x.csv", "LBR/SR0001/x.csv")]);
    expect(folder).toHaveLength(1);
    expect(folder[0]).toMatchObject({ kind: "folder", name: "LBR" });
  });
});
