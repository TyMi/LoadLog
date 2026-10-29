// Importquellen aus Drag & Drop oder Dateiauswahl: ZIP- und GRT-Dateien werden einzeln hochgeladen,
// jeder Ordner (eine SD-Karte) wird zu einer ZIP gebündelt. Zwei Karten dürfen nicht in eine ZIP,
// weil beide dieselben Serien-Nummern (SR0001 ...) haben können.
import { zipStore } from "./zip";

export type Source =
  | { kind: "file"; name: string; file: File }
  | { kind: "folder"; name: string; files: { path: string; file: File }[] };

/** Nur diese Dateien braucht der Server (Serien-.lbr, Report- und Track-CSV); alles andere bleibt auf dem Rechner. */
export const isRelevant = (path: string) => /(?:^|\/)SR\d{3,4}\/(?:SR\d{3,4}\.lbr|SR\d{3,4} Report\.csv|TRK\/Shot\d{3,4} Track\.csv)$/i.test(path.replace(/\\/g, "/"));

export const isUploadFile = (name: string) => /\.(zip|grtload)$/i.test(name);

interface Entry {
  isFile: boolean;
  isDirectory: boolean;
  name: string;
  fullPath: string;
  file?: (ok: (f: File) => void, fail: (e: unknown) => void) => void;
  createReader?: () => { readEntries: (ok: (e: Entry[]) => void, fail: (e: unknown) => void) => void };
}

const readAll = async (dir: Entry): Promise<Entry[]> => {
  const reader = dir.createReader!();
  const out: Entry[] = [];
  for (;;) {
    const batch = await new Promise<Entry[]>((ok, fail) => reader.readEntries(ok, fail));
    if (batch.length === 0) return out; // readEntries liefert Blöcke, bis es leer zurückkommt
    out.push(...batch);
  }
};

const walk = async (e: Entry, into: { path: string; file: File }[]): Promise<void> => {
  if (e.isFile) {
    const file = await new Promise<File>((ok, fail) => e.file!(ok, fail));
    into.push({ path: e.fullPath.replace(/^\//, ""), file });
  } else if (e.isDirectory) {
    for (const c of await readAll(e)) await walk(c, into);
  }
};

/** Alles, was auf die Ablagefläche gezogen wurde (mehrere Dateien und/oder Ordner). */
export async function sourcesFromDrop(dt: DataTransfer): Promise<Source[]> {
  // Einträge müssen synchron ausgelesen werden, bevor die DataTransfer-Liste ungültig wird
  const items: { entry: Entry | null; file: File | null }[] = [];
  for (const item of Array.from(dt.items ?? [])) {
    if (item.kind !== "file") continue;
    items.push({ entry: (item as unknown as { webkitGetAsEntry?: () => Entry | null }).webkitGetAsEntry?.() ?? null, file: item.getAsFile() });
  }
  const out: Source[] = [];
  for (const { entry, file } of items) {  // Eintrag und Datei bleiben zusammen, auch wenn getAsFile() null liefert
    if (entry?.isDirectory) {
      const files: { path: string; file: File }[] = [];
      await walk(entry, files);
      out.push({ kind: "folder", name: entry.name, files });
    } else if (file) {
      out.push({ kind: "file", name: file.name, file });
    }
  }
  return out;
}

/** Aus <input type=file multiple> bzw. <input webkitdirectory>. */
export function sourcesFromInput(files: File[]): Source[] {
  const withPath = files.filter((f) => (f as File & { webkitRelativePath?: string }).webkitRelativePath);
  if (withPath.length > 0) {
    const root = (withPath[0] as File & { webkitRelativePath: string }).webkitRelativePath.split("/")[0];
    return [{ kind: "folder", name: root, files: withPath.map((f) => ({ path: (f as File & { webkitRelativePath: string }).webkitRelativePath, file: f })) }];
  }
  return files.map((f) => ({ kind: "file", name: f.name, file: f }));
}

/** Datei für den Upload: ZIP/GRT unverändert, Ordner als ZIP der relevanten Dateien. */
export async function toUpload(s: Source, noFiles: (name: string) => string = (n) => `${n}: no LabRadar files found`): Promise<File> {
  if (s.kind === "file") return s.file;
  const rel = s.files.filter((f) => isRelevant(f.path));
  if (rel.length === 0) throw new Error(noFiles(s.name));
  const entries = await Promise.all(rel.map(async (f) => ({ name: f.path, data: new Uint8Array(await f.file.arrayBuffer()) })));
  return new File([zipStore(entries) as BlobPart], `${s.name}.zip`, { type: "application/zip" });
}
