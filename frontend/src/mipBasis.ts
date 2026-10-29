import { fmt, grains } from "./units";
import type { Lang } from "./units";

export interface MipBasis {
  text: string;
  warn?: string;
}

interface Words {
  mipBasis: string;
  mipMixed: string;
  mipNoWeight: string;
  mipMismatch: string;
  mipOverridden: string;
}

/** Erklärt, mit welchem Geschossgewicht der MIP berechnet wurde (Gewicht je Schuss aus der Messung, nicht aus der Laborierung). */
export function mipBasis(weightsG: (number | null | undefined)[], loadGr: number | null | undefined, lang: Lang, w: Words, overridden?: { count: number; total: number }): MipBasis {
  const ws = [...new Set(weightsG.filter((x): x is number => !!x && x > 0).map((x) => Math.round(x * 100) / 100))].sort((a, b) => a - b);
  if (ws.length === 0) return { text: w.mipNoWeight };
  const show = (g: number) => `${fmt(g, 2, lang)} g (${fmt(grains(g), 0, lang)} gr)`;
  let text = ws.length === 1 ? `${w.mipBasis} ${show(ws[0])}` : `${w.mipMixed} ${ws.map(show).join(", ")}`;
  if (overridden && overridden.count > 0) text += ` · ${w.mipOverridden} (${overridden.count}/${overridden.total})`;
  const off = loadGr && loadGr > 0 && ws.some((g) => Math.abs(grains(g) - loadGr) / loadGr > 0.01);
  return off ? { text, warn: `${w.mipMismatch} ${fmt(loadGr, 0, lang)} gr` } : { text };
}
