import { setMessageLang } from "./messages";
import { createContext } from "preact";
import { useContext, useEffect, useState } from "preact/hooks";
import { api } from "./api";
import { type Key, tr } from "./i18n";
import type { Lang, Units } from "./units";
import { urls } from "./api";
import { CompareView, ImportView, LoadView, LoadsView, SeriesView, SettingsView, WeaponsView } from "./views";

interface Ctx {
  lang: Lang;
  units: Units;
  pdf: boolean;
  version: string;
  manualVersion: string;
  setLang: (l: Lang) => void;
  setUnits: (u: Units) => void;
  t: (k: Key) => string;
}
export const AppCtx = createContext<Ctx>({
  lang: "de", units: "si", pdf: false, version: "", manualVersion: "", setLang: () => {}, setUnits: () => {}, t: (k) => k,
});
export const useApp = () => useContext(AppCtx);

function stored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    if (v && (allowed as readonly string[]).includes(v)) return v as T;
  } catch {
    /* localStorage nicht verfügbar */
  }
  return fallback;
}

function useHash(): string {
  const [h, setH] = useState(location.hash.slice(1) || "/");
  useEffect(() => {
    const on = () => setH(location.hash.slice(1) || "/");
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return h;
}

export const go = (path: string) => {
  location.hash = path;
};

export function App() {
  const [lang, setLang] = useState<Lang>(() => stored("lang", ["de", "en"] as const, navigator.language.startsWith("de") ? "de" : "en"));
  const [units, setUnits] = useState<Units>(() => stored("units", ["si", "imp"] as const, "si"));
  const [pdf, setPdf] = useState(false);
  const [ver, setVer] = useState({ version: "", manual: "" });
  const route = useHash();

  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      localStorage.setItem("lang", lang);
      localStorage.setItem("units", units);
    } catch {
      /* ignorieren */
    }
  }, [lang, units]);
  useEffect(() => {
    api.health().then((h) => { setPdf(h.pdf); setVer({ version: h.version, manual: h.manual_version }); }).catch(() => setPdf(false));
  }, []);

  setMessageLang(lang); // Fehler aus api.ts entstehen außerhalb der Komponenten
  const ctx: Ctx = { lang, units, pdf, version: ver.version, manualVersion: ver.manual, setLang, setUnits, t: (k) => tr(lang, k) };
  const t = ctx.t;
  const parts = route.split("/").filter(Boolean);
  let view;
  if (parts[0] === "load" && parts[1]) view = <LoadView key={parts[1]} id={parts[1] === "new" ? null : Number(parts[1])} />;
  else if (parts[0] === "series" && parts[1]) view = <SeriesView key={parts[1]} id={Number(parts[1])} />;
  else if (parts[0] === "compare" && parts[1]) view = <CompareView ids={parts[1].split(",").map(Number).filter(Number.isFinite)} />;
  else if (parts[0] === "import") view = <ImportView />;
  else if (parts[0] === "weapons") view = <WeaponsView />;
  else if (parts[0] === "settings") view = <SettingsView />;
  else view = <LoadsView />;
  const active = parts[0] === "import" || parts[0] === "weapons" || parts[0] === "settings" ? parts[0] : "loads";
  const cur = (k: string) => (active === k ? "page" : undefined);

  return (
    <AppCtx.Provider value={ctx}>
      <header>
        <a class="brand" href="#/">
          <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
            <circle cx="13" cy="13" r="11" fill="none" stroke="#f5a623" stroke-width="2" />
            <circle cx="13" cy="13" r="6" fill="none" stroke="#6db3ff" stroke-width="2" />
            <circle cx="13" cy="13" r="2" fill="#f5a623" />
          </svg>
          LoadLog
        </a>
        <nav class="top" aria-label={t("navigation")}>
          <a href="#/" aria-current={cur("loads")}>{t("navLoads")}</a>
          <a href="#/import" aria-current={cur("import")}>{t("navImport")}</a>
          <a href="#/weapons" aria-current={cur("weapons")}>{t("navWeapons")}</a>
          <a href={urls.manual(lang, ctx.manualVersion)} target="_blank" rel="noopener">{t("manual")}</a>
          <a href="#/settings" aria-current={cur("settings")}>{t("navSettings")}</a>
        </nav>
      </header>
      <main>{view}</main>
      <footer>LoadLog {ctx.version}</footer>
    </AppCtx.Provider>
  );
}
