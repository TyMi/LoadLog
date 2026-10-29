import { api, type ImportResult } from "./api";
import { type Source, toUpload } from "./importSources";

export interface Aggregate extends ImportResult {
  errors: string[]; // je Quelle, die nicht importiert werden konnte
  sources: number;
}

export const emptyAggregate = (): Aggregate => ({ imported: [], skipped: 0, warnings: [], load_id: null, errors: [], sources: 0 });

export function merge(into: Aggregate, r: ImportResult): Aggregate {
  return {
    imported: [...into.imported, ...r.imported],
    skipped: into.skipped + r.skipped,
    warnings: [...into.warnings, ...r.warnings],
    load_id: r.load_id ?? into.load_id,
    errors: into.errors,
    sources: into.sources + 1,
  };
}

/** Quellen nacheinander hochladen; ein Fehler bei einer Quelle stoppt die übrigen nicht. */
export async function runImport(sources: Source[], loadId?: number, onProgress?: (done: number, total: number) => void, noFiles?: (name: string) => string): Promise<Aggregate> {
  let agg = emptyAggregate();
  let done = 0;
  for (const s of sources) {
    try {
      agg = merge(agg, await api.importZip(await toUpload(s, noFiles), loadId));
    } catch (e) {
      agg = { ...agg, errors: [...agg.errors, `${s.name}: ${(e as Error).message}`] };
    }
    onProgress?.(++done, sources.length);
  }
  return agg;
}
