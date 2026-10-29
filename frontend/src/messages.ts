import { TEXTS } from "./i18n";
import type { Lang } from "./units";

/** Meldung des Servers: stabiler Code, Parameter und deutscher Rückfalltext. */
export interface Note {
  code: string;
  message: string;
  params: Record<string, unknown>;
}

let current: Lang = "de";
/** Sprache für Meldungen, die außerhalb von Komponenten entstehen (z. B. Fehler aus api.ts). */
export const setMessageLang = (lang: Lang) => {
  current = lang;
};

export const isNote = (x: unknown): x is Note =>
  typeof x === "object" && x !== null && typeof (x as Note).code === "string" && typeof (x as Note).message === "string";

/** Meldung in der Oberflächensprache; unbekannte Codes fallen auf den Servertext zurück. */
export function renderNote(n: Note, lang: Lang = current): string {
  const tpl = (TEXTS[lang] as Record<string, string>)[`msg_${n.code}`];
  if (!tpl) return n.message;
  return tpl.replace(/\{(\w+)\}/g, (m, k: string) => {
    const v = n.params?.[k];
    if (v === undefined || v === null) return m;
    return isNote(v) ? renderNote(v, lang) : String(v);
  });
}

/** Hinweis (Note oder einfacher Text) darstellen. */
export const renderAny = (x: Note | string, lang: Lang = current) => (typeof x === "string" ? x : renderNote(x, lang));
