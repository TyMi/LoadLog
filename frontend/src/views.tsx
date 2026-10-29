import type { ComponentChildren } from "preact";
import { useCallback, useEffect, useRef, useState } from "preact/hooks";
import { type BcFit, type Load, type LoadData, type SeriesDetail, type SeriesSummary, type Stats, type TrialType, type Weapon, api, urls } from "./api";
import { type TrackLine, nearestPoint, parsePoints } from "./chartPick";
import { runImport, type Aggregate } from "./importRun";
import { type Source, isUploadFile, sourcesFromDrop, sourcesFromInput } from "./importSources";
import { type GroupBy, type LoadViewMode, groupLoads } from "./loadGroups";
import { renderAny } from "./messages";
import { mipBasis } from "./mipBasis";
import { togglePick, toggleAll } from "./selection";
import { type SortKey, errorText, seriesLabel, sortSeries } from "./seriesSort";
import { go, useApp } from "./app";
import { LOAD_GROUPS, type Key } from "./i18n";
import { dOut, dateRange, eOut, fmt, parseNum, unitNames, vOut } from "./units";

// ---------- Hilfen ----------
function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    fn().then((d) => alive && (setData(d), setError(null))).catch((e) => alive && setError(String(e.message ?? e)));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, setData, error, reload: () => setTick((x) => x + 1) };
}

function Loading({ error }: { error: string | null }) {
  const { t } = useApp();
  return error ? <div class="msg err" role="alert">{t("errorPrefix")}: {error}</div> : <p class="muted">{t("loading")}</p>;
}

function SvgChart({ url, hover, onPick }: { url: string; hover?: boolean; onPick?: (shot: number) => void }) {
  const { t } = useApp();
  const [svg, setSvg] = useState("");
  const [fail, setFail] = useState<string | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number; label: string; val: string; shot: number } | null>(null);
  useEffect(() => {
    let alive = true;
    setFail(null);
    fetch(url)
      .then(async (r) => {
        const body = await r.text();
        if (!alive) return;
        if (r.ok) setSvg(body);
        else {
          setSvg("");
          setFail(errorText(r.status, body));
        }
      })
      .catch((e) => {
        if (!alive) return;
        setSvg("");
        setFail(String(e?.message ?? e));
      });
    return () => {
      alive = false;
    };
  }, [url]);
  // Overlay: nächstgelegenen Messpunkt aller Tracks (data-vals) zur Maus suchen
  const onMove = (e: MouseEvent) => {
    const box = e.currentTarget as HTMLElement;
    const el = box.querySelector("svg");
    const ctm = el?.getScreenCTM();
    if (!el || !ctm) return;
    const pt = el.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const m = pt.matrixTransform(ctm.inverse());
    const lines: TrackLine[] = [];
    el.querySelectorAll("polyline[data-vals]").forEach((pl) => {
      lines.push({
        shot: Number(pl.getAttribute("data-shot")),
        label: pl.getAttribute("data-label") ?? "",
        points: parsePoints(pl.getAttribute("points") ?? ""),
        vals: (pl.getAttribute("data-vals") ?? "").split(";"),
      });
    });
    const b = nearestPoint(lines, m.x, m.y);
    if (!b) return setTip(null);
    const sp = el.createSVGPoint();
    sp.x = b.x;
    sp.y = b.y;
    const s = sp.matrixTransform(ctm);
    const r = box.getBoundingClientRect();
    setTip({ x: s.x - r.left, y: s.y - r.top, label: b.label, val: b.val, shot: b.shot });
  };
  // SVG stammt vom eigenen Server (serverseitig erzeugt und escaped)
  return (
    <div class={`chart${tip && onPick ? " pick" : ""}`} onMouseMove={hover ? onMove : undefined} onMouseLeave={() => setTip(null)} onClick={() => tip && onPick?.(tip.shot)}>
      {fail !== null && <div class="msg err" role="alert">{t("chartError")}: {fail}</div>}
      <div dangerouslySetInnerHTML={{ __html: svg }} />
      <p class="sr-only">{t("chartTableHint")}</p>
      {tip && (
        <>
          <span class="chart-dot" style={{ left: `${tip.x}px`, top: `${tip.y}px` }} />
          <div class="chart-tip" style={{ left: `${tip.x}px`, top: `${tip.y}px` }}>
            <strong>{tip.label}</strong>
            <br />
            {tip.val}
          </div>
        </>
      )}
    </div>
  );
}

function StatCards({ s, total, weightsG, loadGr, overridden, bc }: { s: Stats; total?: number; weightsG?: (number | null)[]; loadGr?: number | null; overridden?: { count: number; total: number }; bc?: { g1: BcFit; g7: BcFit } }) {
  const { t, lang, units } = useApp();
  const basis = weightsG ? mipBasis(weightsG, loadGr, lang, { mipBasis: t("mipBasis"), mipMixed: t("mipMixed"), mipNoWeight: t("mipNoWeight"), mipMismatch: t("mipMismatch"), mipOverridden: t("mipOverridden") }, overridden) : null;
  const u = unitNames(units);
  const v = (x: number | null) => fmt(x === null ? null : vOut(x, units), 1, lang);
  const showBc = bc !== undefined && (bc.g1.avg !== null || bc.g7.avg !== null);
  const bcCard = (name: string, f: BcFit) => (
    <div class="card" title={t("bcHint")}>
      <div class="l">{t("bc")} {name} · {f.n} {t("counted")}</div>
      <div class="v">{fmt(f.avg, 3, lang)}{f.sd !== null ? <span class="muted small"> ± {fmt(f.sd, 3, lang)}</span> : null}</div>
    </div>
  );
  return (
    <>
      <div class="stat-groups">
        <section aria-labelledby="grp-speed">
          <h2 class="grp" id="grp-speed">{t("groupSpeed")}</h2>
          <div class="cards cards4">
            <div class="card"><div class="l">{t("avg")} ({u.v})</div><div class="v">{v(s.avg)}</div></div>
            <div class="card"><div class="l">{t("sd")} ({u.v})</div><div class="v">{v(s.sd)}</div></div>
            <div class="card"><div class="l">{t("es")} ({u.v})</div><div class="v">{v(s.es)}</div></div>
            <div class="card"><div class="l">{t("minmax")} ({u.v})</div><div class="v">{v(s.vmin)}–{v(s.vmax)}</div></div>
          </div>
        </section>
        <section aria-labelledby="grp-energy">
          <h2 class="grp" id="grp-energy">{t("groupEnergy")}</h2>
          <div class="cards cards2">
            <div class="card">
              <div class="l">{t("energy")} ({u.e}) · {s.n}{total !== undefined ? `/${total}` : ""} {t("counted")}</div>
              <div class="v">{fmt(s.energy_avg_j === null ? null : eOut(s.energy_avg_j, units), 0, lang)}</div>
            </div>
            <div class="card">
              <div class="l">{t("impulse")} · {t("impulseMin")} {fmt(s.mip_min, 0, lang)}</div>
              <div class="v">{fmt(s.mip_avg, 0, lang)}</div>
            </div>
          </div>
        </section>
        {showBc && bc && (
          <section aria-labelledby="grp-bc">
            <h2 class="grp" id="grp-bc">{t("groupBallistics")}</h2>
            <div class="cards cards2">
              {bcCard("G1", bc.g1)}
              {bcCard("G7", bc.g7)}
            </div>
          </section>
        )}
      </div>
      {showBc && <p class="muted small" style={{ margin: "4px 0 0" }}>{t("bcHint")}</p>}
      {basis && <p class="muted small" style={{ margin: "4px 0 12px" }}>{basis.text}{basis.warn && <> · <strong style={{ color: "var(--amber)" }}>{basis.warn}</strong></>}</p>}
    </>
  );
}

function Bars({ n }: { n: number | null }) {
  return (
    <span class="bars" role="img" aria-label={n ? `${n}/5` : "–"}>
      {[1, 2, 3, 4, 5].map((k) => <i key={k} class={n && k <= n ? "on" : ""} style={{ height: `${4 + k * 3}px` }} />)}
    </span>
  );
}

function Field({ label, children, wide }: { label: string; children: ComponentChildren; wide?: boolean }) {
  return (
    <label class="field" style={wide ? { flexBasis: "100%" } : undefined}>
      <span class="flabel">{label}</span>
      {children}
    </label>
  );
}

function Msg({ ok, err }: { ok?: string | null; err?: string | null }) {
  return err ? <div class="msg err" role="alert">{err}</div> : ok ? <div class="msg" role="status">{ok}</div> : null;
}

const reportLinks = (pdf: boolean, pdfUrl: string, htmlUrl: string, t: (k: Key) => string, csvUrl?: string) => (
  <>
    {csvUrl && <a class="btn ghost" href={csvUrl} download>{t("exportCsv")}</a>}
    {pdf ? <a class="btn" href={pdfUrl} download>{t("reportPdf")}</a> : <span class="muted small">{t("pdfUnavailable")}</span>}
    <a class="btn ghost" href={htmlUrl} target="_blank" rel="noopener">{t("reportHtml")}</a>
  </>
);

const dateText = (iso: string | null, lang: string) => (iso ? new Date(iso).toLocaleDateString(lang === "de" ? "de-DE" : "en-GB") : "–");

// ---------- Einstellungen ----------
export function SettingsView() {
  const { t, lang, units, pdf, version, manualVersion, setLang, setUnits } = useApp();
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const [busy, setBusy] = useState(false);
  const restore = async (e: Event) => {
    const input = e.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (!file || !confirm(`${t("restoreConfirm")}\n${file.name}`)) return;
    setBusy(true);
    try {
      const r = await api.restore(file);
      setMsg({ ok: `${t("restoreDone")}: ${r.loads} ${t("loadsTitle")}, ${r.series} ${t("seriesPl")}, ${r.shots} ${t("shots")}` });
    } catch (err) {
      setMsg({ err: `${t("actionFailed")}: ${(err as Error).message}` });
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <h1>{t("navSettings")}</h1>
      <section class="panel col">
        <h2>{t("sysDisplay")}</h2>
        <div class="row">
          <span class="flabel">{t("language")}</span>
          <div class="seg" role="group" aria-label={t("language")}>
            <button aria-pressed={lang === "de"} onClick={() => setLang("de")}>Deutsch</button>
            <button aria-pressed={lang === "en"} onClick={() => setLang("en")}>English</button>
          </div>
          <span class="flabel">{t("units")}</span>
          <div class="seg" role="group" aria-label={t("units")}>
            <button aria-pressed={units === "si"} onClick={() => setUnits("si")}>m/s · J</button>
            <button aria-pressed={units === "imp"} onClick={() => setUnits("imp")}>fps · ft-lbf</button>
          </div>
        </div>
        <div class="muted small">{t("sysDisplayHint")}</div>
      </section>
      <section class="panel col">
        <h2>{t("sysData")}</h2>
        <div class="row">
          <a class="btn" href={urls.backup} download>{t("backupDownload")}</a>
          <label class="btn" aria-disabled={busy}>
            {t("restoreFile")}
            <input type="file" accept=".sqlite3,.sqlite,.db,application/vnd.sqlite3" disabled={busy} onChange={restore} style={{ display: "none" }} />
          </label>
        </div>
        <div class="muted small">{t("backupHint")}</div>
        <div class="muted small"><strong>{t("restoreTitle")}:</strong> {t("restoreHint")}</div>
        {msg.ok && <div role="status">{msg.ok}</div>}
        {msg.err && <div role="alert" style={{ color: "var(--red, #ff8a80)" }}>{msg.err}</div>}
      </section>
      <section class="panel col">
        <h2>{t("sysInfo")}</h2>
        <div>{t("versionLabel")}: <span class="mono">{version || "–"}</span></div>
        <div><a href={urls.manual(lang, manualVersion)} target="_blank" rel="noopener">{t("manual")} {manualVersion}</a> <span class="muted small">({t("manualVersionHint")})</span></div>
        <div>{t("pdfStatus")}: {pdf ? t("available") : t("pdfUnavailable")}</div>
        <div class="note-box" role="note">{t("disclaimerShort")} <a href={`${urls.manual(lang, manualVersion)}#disclaimer`} target="_blank" rel="noopener">{t("disclaimerLink")}</a></div>
      </section>
    </>
  );
}

// ---------- Laborierungen ----------
function usePref<T extends string>(key: string, allowed: readonly T[], fallback: T): [T, (v: T) => void] {
  const [v, setV] = useState<T>(() => {
    try {
      const x = localStorage.getItem(key);
      if (x && (allowed as readonly string[]).includes(x)) return x as T;
    } catch {
      /* localStorage nicht verfügbar */
    }
    return fallback;
  });
  const set = (n: T) => {
    setV(n);
    try {
      localStorage.setItem(key, n);
    } catch {
      /* egal */
    }
  };
  return [v, set];
}

export function LoadsView() {
  const { t, lang, units } = useApp();
  const { data, error } = useAsync(() => api.loads(), []);
  const [mode, setMode] = usePref<LoadViewMode>("loadsView", ["cards", "list"], "cards");
  const [group, setGroup] = usePref<GroupBy>("loadsGroup", ["none", "weapon"], "none");
  if (!data) return <Loading error={error} />;
  const u = unitNames(units);
  const vText = (x: number | null) => fmt(x === null ? null : vOut(x, units), 1, lang);
  const info = (l: Load) => [l.powder_name, l.charge_gr ? `${fmt(l.charge_gr, 1, lang)} gr` : null, l.bullet_weight_gr ? `${fmt(l.bullet_weight_gr, 0, lang)} gr` : null].filter(Boolean).join(" · ");
  const groups = groupLoads(data, group, t("noWeaponGroup"));
  const card = (l: Load) => (
    <article class="panel col" key={l.id}>
      <div>
        <h2>{l.name}</h2>
        <div class="muted small">
          {t(`trial_${l.trial_type}` as Key)} · {l.series_count} {t("seriesPl")} · {l.shots_total} {t("shots")}
          {l.weapon_name && group === "none" ? ` · ${l.weapon_name}` : ""}
        </div>
        <div class="muted small">{info(l)}</div>
      </div>
      <div class="row mono small">
        <span>Ø {vText(l.stats.avg)} {u.v}</span>
        <span>SD {vText(l.stats.sd)}</span>
        <span>ES {vText(l.stats.es)}</span>
      </div>
      <a class="btn" href={`#/load/${l.id}`}>{t("open")}</a>
    </article>
  );
  const list = (items: Load[]) => (
    <table class="loads-list">
      <thead>
        <tr>
          <th>{t("loadName")}</th><th>{t("trialType")}</th>
          {group === "none" && <th>{t("weapon")}</th>}
          <th class="n">{t("seriesPl")}</th><th class="n">{t("shots")}</th>
          <th>{t("grpPowder")} · {t("grpBullet")}</th>
          <th class="n">Ø {u.v}</th><th class="n">SD</th><th class="n">ES</th>
        </tr>
      </thead>
      <tbody>
        {items.map((l) => (
          <tr key={l.id} class="pickable" onClick={() => go(`/load/${l.id}`)}>
            <td><a href={`#/load/${l.id}`} onClick={(e) => e.stopPropagation()}>{l.name}</a></td>
            <td>{t(`trial_${l.trial_type}` as Key)}</td>
            {group === "none" && <td>{l.weapon_name ?? "–"}</td>}
            <td class="n">{l.series_count}</td><td class="n">{l.shots_total}</td>
            <td class="small">{info(l) || "–"}</td>
            <td class="n">{vText(l.stats.avg)}</td><td class="n">{vText(l.stats.sd)}</td><td class="n">{vText(l.stats.es)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
  return (
    <>
      <div class="row">
        <h1 class="grow">{t("loadsTitle")}</h1>
        <div class="seg" role="group" aria-label={t("groupLabel")}>
          <button aria-pressed={group === "none"} onClick={() => setGroup("none")}>{t("groupNone")}</button>
          <button aria-pressed={group === "weapon"} onClick={() => setGroup("weapon")}>{t("groupWeapon")}</button>
        </div>
        <div class="seg" role="group" aria-label={t("viewLabel")}>
          <button aria-pressed={mode === "cards"} onClick={() => setMode("cards")}>{t("viewCards")}</button>
          <button aria-pressed={mode === "list"} onClick={() => setMode("list")}>{t("viewList")}</button>
        </div>
        <a class="btn primary" href="#/load/new">{t("newLoad")}</a>
      </div>
      {data.length === 0 && <p class="muted">{t("none")}</p>}
      {groups.map((g) => (
        <section key={g.key} class="load-group">
          {g.title !== null && <h2 class="group-title">{g.title} <span class="muted small">({g.items.length})</span></h2>}
          {mode === "cards" ? <div class="grid-cards">{g.items.map(card)}</div> : list(g.items)}
        </section>
      ))}
    </>
  );
}

type Draft = Record<string, string>;
const NUM_FIELDS = new Set(LOAD_GROUPS.flatMap((g) => g.fields.filter((f) => f.kind !== "text" && f.kind !== "area").map((f) => f.key)));

function toDraft(load: Partial<LoadData> | null, lang: string): Draft {
  const d: Draft = { name: load?.name ?? "", trial_type: load?.trial_type ?? "single", weapon_id: load?.weapon_id ? String(load.weapon_id) : "" };
  for (const g of LOAD_GROUPS)
    for (const f of g.fields) {
      const v = (load as Record<string, unknown> | null)?.[f.key];
      d[f.key] = v === null || v === undefined ? "" : lang === "de" ? String(v).replace(".", ",") : String(v);
    }
  return d;
}

export function fromDraft(d: Draft): { data: Record<string, unknown>; bad: string[] } {
  const data: Record<string, unknown> = { name: d.name.trim(), trial_type: d.trial_type, weapon_id: d.weapon_id ? Number(d.weapon_id) : null };
  const bad: string[] = [];
  for (const g of LOAD_GROUPS)
    for (const f of g.fields) {
      const raw = d[f.key] ?? "";
      if (NUM_FIELDS.has(f.key)) {
        const n = parseNum(raw);
        if (n === undefined) bad.push(f.key);
        else data[f.key] = n === null ? null : f.kind === "int" ? Math.round(n) : n;
      } else data[f.key] = raw.trim() === "" ? null : raw.trim();
    }
  return { data, bad };
}

function LoadImport({ loadId, onDone }: { loadId: number; onDone: () => void }) {
  const { t, lang } = useApp();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const input = useRef<HTMLInputElement>(null);
  const folder = useRef<HTMLInputElement>(null);
  const upload = async (sources: Source[]) => {
    const usable = sources.filter((s) => s.kind === "folder" || isUploadFile(s.name));
    if (usable.length === 0) return setMsg({ err: t("importNothing") });
    setBusy(true);
    setMsg({});
    const r = await runImport(usable, loadId, undefined, (n) => `${n}: ${t("noLabradarFiles")}`);
    const text = `${r.imported.length} ${t("importedInto")} · ${r.skipped} ${t("skippedN")}${r.warnings.length ? ` · ${r.warnings.map((w) => renderAny(w, lang)).join(" · ")}` : ""}`;
    setMsg(r.errors.length ? { ok: r.imported.length ? text : undefined, err: r.errors.join(" · ") } : { ok: text });
    setBusy(false);
    onDone();
  };
  const pick = (e: Event) => {
    const el = e.currentTarget as HTMLInputElement;
    upload(sourcesFromInput(Array.from(el.files ?? [])));
    el.value = "";
  };
  return (
    <div class="row" style={{ marginTop: 12 }}>
      <input ref={input} type="file" multiple accept=".zip,.grtload,application/zip" hidden onChange={pick} />
      <input ref={folder} type="file" hidden {...{ webkitdirectory: true, directory: true }} onChange={pick} />
      <button class="btn" disabled={busy} onClick={() => input.current?.click()}>{busy ? t("importing") : `${t("importHereTitle")} …`}</button>
      <button class="btn" disabled={busy} onClick={() => folder.current?.click()}>{t("chooseFolder")}</button>
      <span class="muted small grow">{t("importHereHint")}</span>
      {msg.ok && <span class="small" role="status">{msg.ok}</span>}
      {msg.err && <span class="small" role="alert" style={{ color: "var(--red, #ff8a80)" }}>{msg.err}</span>}
    </div>
  );
}

export function LoadView({ id }: { id: number | null }) {
  const { t, lang, units, pdf } = useApp();
  const { data, error, reload } = useAsync(() => (id === null ? Promise.resolve(null) : api.load(id)), [id]);
  const weapons = useAsync(() => api.weapons(), []);
  const free = useAsync(() => api.series(false), []);
  const allLoads = useAsync(() => api.loads(), []);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [bad, setBad] = useState<string[]>([]);
  const [info, setInfo] = useState<{ ok?: string; err?: string }>({});
  const [picked, setPicked] = useState<number[]>([]);
  const [ladderBy, setLadderBy] = useState<"charge" | "seating">("charge");

  useEffect(() => {
    if (id === null) setDraft(toDraft(null, lang));
    else if (data) setDraft((cur) => cur ?? toDraft(data, lang));
  }, [data, id, lang]);

  if (id !== null && !data) return <Loading error={error} />;
  if (!draft) return <Loading error={null} />;
  const set = (k: string, v: string) => setDraft({ ...draft, [k]: v });

  const save = async () => {
    const { data: payload, bad: b } = fromDraft(draft);
    setBad(b);
    if (b.length) return setInfo({ err: t("invalidNumber") });
    if (!String(payload.name)) return setInfo({ err: t("loadName") });
    try {
      if (id === null) go(`/load/${(await api.createLoad(payload as unknown as LoadData)).id}`);
      else {
        await api.updateLoad(id, payload as Partial<LoadData>);
        setInfo({ ok: t("saved") });
        reload();
      }
    } catch (e) {
      setInfo({ err: String((e as Error).message) });
    }
  };
  const remove = async () => {
    if (id !== null && confirm(`${t("confirmDelete")}\n${t("deleteLoadHint")}`)) {
      await api.deleteLoad(id);
      go("/");
    }
  };
  const assign = async (sid: number) => {
    if (id === null) return;
    try {
      await api.addToLoad(sid, id);
      reload();
      free.reload();
    } catch (e) {
      setInfo({ err: `${t("actionFailed")}: ${(e as Error).message}` });
    }
  };
  const unlink = async (sid: number) => {
    if (id === null) return;
    try {
      await api.removeFromLoad(sid, id);
      setPicked((p) => p.filter((x) => x !== sid));
      reload();
      free.reload();
    } catch (e) {
      setInfo({ err: `${t("actionFailed")}: ${(e as Error).message}` });
    }
  };
  const loadName = (lid: number) => (allLoads.data ?? []).find((l) => l.id === lid)?.name ?? `#${lid}`;
  const addable = (free.data ?? []).filter((s) => id !== null && !s.load_ids.includes(id)).sort((a, b) => Number(a.load_ids.length > 0) - Number(b.load_ids.length > 0));
  const toggle = (sid: number) => setPicked((p) => (p.includes(sid) ? p.filter((x) => x !== sid) : [...p, sid]));
  const [sortBy, setSortBy] = useState<SortKey>("date");
  const series = sortSeries(data?.series ?? [], sortBy, t("series"));
  const u = unitNames(units);
  const distinct = (k: "charge_gr" | "seating_depth_mm") => new Set(series.map((s) => s[k]).filter((x) => x !== null)).size;
  const allIds = series.map((s) => s.id);

  return (
    <>
      <div class="row">
        <a class="btn ghost" href="#/">← {t("back")}</a>
        <h1 class="grow">{id === null ? t("newLoad") : draft.name || t("loadsTitle")}</h1>
        {id !== null && reportLinks(pdf, urls.reportLoad(id, { lang, units }), urls.reportLoad(id, { lang, units }) + "&format=html", t, urls.exportLoad(id, { lang, units }))}
      </div>
      <div class="sidebar-layout">
        <section class="panel side col" aria-label={t("loadName")}>
          <div class="row">
            <Field label={t("loadName")}><input type="text" value={draft.name} maxLength={200} onInput={(e) => set("name", e.currentTarget.value)} /></Field>
            <Field label={t("trialType")}>
              <select value={draft.trial_type} onChange={(e) => set("trial_type", e.currentTarget.value as TrialType)}>
                {(["single", "ladder", "seating"] as const).map((k) => <option value={k}>{t(`trial_${k}` as Key)}</option>)}
              </select>
            </Field>
            <Field label={t("weapon")}>
              <select value={draft.weapon_id} onChange={(e) => set("weapon_id", e.currentTarget.value)}>
                <option value="">{t("noWeapon")}</option>
                {(weapons.data ?? []).map((w) => <option value={w.id}>{w.name}{w.caliber ? ` (${w.caliber})` : ""}</option>)}
              </select>
            </Field>
          </div>
          {LOAD_GROUPS.map((g) => (
            <div key={g.title}>
              <h3>{t(g.title)}</h3>
              <div class="row">
                {g.fields.map((f) => (
                  <Field label={t(f.key as Key)} wide={f.kind === "area"} key={f.key}>
                    {f.kind === "area" ? (
                      <textarea value={draft[f.key]} maxLength={4000} onInput={(e) => set(f.key, e.currentTarget.value)} />
                    ) : (
                      <input type="text" inputMode={f.kind === "text" ? "text" : "decimal"} class={bad.includes(f.key) ? "bad" : ""} value={draft[f.key]} maxLength={200} onInput={(e) => set(f.key, e.currentTarget.value)} />
                    )}
                  </Field>
                ))}
              </div>
            </div>
          ))}
          <div class="row">
            <button class="btn primary" onClick={save}>{t("save")}</button>
            {id !== null && <button class="btn danger" onClick={remove}>{t("deleteLoad")}</button>}
          </div>
          <Msg ok={info.ok} err={info.err} />
        </section>

        {id !== null && data && (
          <div class="main col">
            <h3>{t("loadStats")}</h3>
            {data.trial_type === "ladder" && <p class="small">{t("ladderStatsHint")}</p>}
            <StatCards s={data.stats} total={data.shots_total} weightsG={series.map((x) => x.weight_g)} loadGr={data.bullet_weight_gr} overridden={{ count: series.filter((x) => x.weight_override_g).length, total: series.length }} />
            <section class="panel">
              <div class="row">
                <h2 class="grow">{t("seriesPl")}</h2>
                {series.length >= 2 && (
                  <label class="muted small row" style={{ gap: 6 }}>
                    {t("sortBy")}
                    <select style={{ width: "auto" }} value={sortBy} onChange={(e) => setSortBy(e.currentTarget.value as SortKey)}>
                      <option value="date">{t("sortDate")}</option>
                      <option value="charge">{t("sortCharge")}</option>
                      <option value="name">{t("sortName")}</option>
                    </select>
                  </label>
                )}
                {id !== null && data?.bullet_weight_gr ? (
                  <button class="btn" title={t("applyWeightConfirm")} onClick={async () => { if (!confirm(t("applyWeightConfirm"))) return; try { await api.applyWeight(id); reload(); } catch (e) { setInfo({ err: `${t("actionFailed")}: ${(e as Error).message}` }); } }}>{t("applyWeight")} ({fmt(data.bullet_weight_gr, 0, lang)} gr)</button>
                ) : null}
                {id !== null && series.some((x) => x.weight_override_g) ? (
                  <button class="btn ghost" onClick={async () => { try { await api.applyWeight(id, true); reload(); } catch (e) { setInfo({ err: `${t("actionFailed")}: ${(e as Error).message}` }); } }}>{t("clearWeight")}</button>
                ) : null}
                {picked.length >= 2 && <a class="btn" href={`#/compare/${series.filter((s) => picked.includes(s.id)).map((s) => s.id).join(",")}`}>{t("compareSelected")}</a>}
                {series.length >= 2 && <a class="btn ghost" href={`#/compare/${allIds.join(",")}`}>{t("compareTitle")}</a>}
              </div>
              {series.length === 0 && <p class="muted">{t("none")}</p>}
              {series.length > 0 && (
                <div style={{ overflowX: "auto" }}>
                  <table>
                    <thead><tr><th><span class="muted small">{t("selectSeries")}</span></th><th>{t("series")}</th><th class="n">{t("charge_gr")}</th><th class="n">{t("seating_depth_mm")}</th><th class="n">{t("shots")}</th><th class="n">Ø ({u.v})</th><th class="n">SD</th><th class="n">ES</th><th><span class="muted small">{t("removeHere")}</span></th></tr></thead>
                    <tbody>
                      {series.map((s) => (
                        <tr key={s.id}>
                          <td><input type="checkbox" aria-label={`${t("selectSeries")} ${s.number}`} checked={picked.includes(s.id)} onChange={() => toggle(s.id)} style={{ width: 20, height: 20 }} /></td>
                          <td><a href={`#/series/${s.id}`}>{seriesLabel(s, t("series"))}</a> <span class="muted small">{dateText(s.taken_at, lang)}</span></td>
                          <td class="n">{fmt(s.charge_gr, 1, lang)}</td><td class="n">{fmt(s.seating_depth_mm, 2, lang)}</td>
                          <td class="n">{s.stats.n}/{s.shots_total}</td>
                          <td class="n">{fmt(s.stats.avg === null ? null : vOut(s.stats.avg, units), 1, lang)}</td>
                          <td class="n">{fmt(s.stats.sd === null ? null : vOut(s.stats.sd, units), 1, lang)}</td>
                          <td class="n">{fmt(s.stats.es === null ? null : vOut(s.stats.es, units), 1, lang)}</td>
                          <td><button class="btn ghost" title={t("removeHereHint")} aria-label={`${t("removeHere")}: ${seriesLabel(s, t("series"))}`} onClick={() => unlink(s.id)}>×</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {id !== null && <LoadImport loadId={id} onDone={() => { reload(); free.reload(); }} />}
              {addable.length > 0 && (
                <div class="row" style={{ marginTop: 12 }}>
                  <label class="muted small" for="assign">{t("addExisting")}</label>
                  <select id="assign" style={{ width: "auto" }} value="" onChange={(e) => e.currentTarget.value && assign(Number(e.currentTarget.value))}>
                    <option value="">{t("selectSeries")}</option>
                    {addable.map((s) => <option value={s.id}>{seriesLabel(s, t("series"))} · {dateText(s.taken_at, lang)}{s.load_ids.length > 0 ? ` · ${t("alsoIn")} ${s.load_ids.map(loadName).join(", ")}` : ""}</option>)}
                  </select>
                </div>
              )}
            </section>
            {allIds.length >= 1 && (
              <section class="panel">
                <h2>{t("compareTitle")}</h2>
                <SvgChart url={urls.compareChart(allIds, { trend: true, lang, units })} />
              </section>
            )}
            {(distinct("charge_gr") >= 2 || distinct("seating_depth_mm") >= 2) && (
              <section class="panel">
                <div class="row">
                  <h2 class="grow">{t("ladderTitle")}</h2>
                  <div class="seg" role="group">
                    <button aria-pressed={ladderBy === "charge"} onClick={() => setLadderBy("charge")}>{t("byCharge")}</button>
                    <button aria-pressed={ladderBy === "seating"} onClick={() => setLadderBy("seating")}>{t("bySeating")}</button>
                  </div>
                </div>
                <SvgChart url={urls.ladderChart(id, { by: ladderBy, lang, units })} />
              </section>
            )}
          </div>
        )}
      </div>
    </>
  );
}

// ---------- Serie ----------
export function SeriesView({ id }: { id: number }) {
  const { t, lang, units, pdf } = useApp();
  const { data, setData, error } = useAsync(() => api.seriesDetail(id), [id]);
  const loads = useAsync(() => api.loads(), []);
  const [sel, setSel] = useState<number | null>(null);
  const [addLoad, setAddLoad] = useState("");
  const [meta, setMeta] = useState<Record<string, string> | null>(null);
  const [info, setInfo] = useState<{ ok?: string; err?: string }>({});

  useEffect(() => {
    if (data && !meta)
      setMeta({
        name: data.name ?? "", weight_gr: data.weight_override_g ? String(Math.round((data.weight_override_g / 0.06479891) * 100) / 100).replace(".", lang === "de" ? "," : ".") : "", trigger_mode: data.trigger_mode ?? "", note: data.note ?? "",
        charge_gr: data.charge_gr === null ? "" : String(data.charge_gr).replace(".", lang === "de" ? "," : "."),
        seating_depth_mm: data.seating_depth_mm === null ? "" : String(data.seating_depth_mm).replace(".", lang === "de" ? "," : "."),
      });
    if (data && sel === null) setSel((data.shots.find((s) => !s.excluded) ?? data.shots[0])?.number ?? null);
  }, [data, lang]);

  if (!data || !meta) return <Loading error={error} />;
  const u = unitNames(units);
  const shot = data.shots.find((s) => s.number === sel) ?? null;
  const impulseAt = (v: number) => (shot && shot.weight_g > 0 ? fmt(0.1 * shot.weight_g * v, 1, lang) : "–");
  const failed = (e: unknown) => setInfo({ err: `${t("actionFailed")}: ${(e as Error).message}` });
  const toggleShot = async (n: number, excluded: boolean) => {
    try {
      setData(await api.setExcluded(id, n, excluded));
    } catch (e) {
      failed(e);
    }
  };
  const saveMeta = async () => {
    const charge = parseNum(meta.charge_gr);
    const seat = parseNum(meta.seating_depth_mm);
    const wgr = parseNum(meta.weight_gr);
    if (charge === undefined || seat === undefined || wgr === undefined || (wgr !== null && wgr <= 0)) return setInfo({ err: t("invalidNumber") });
    try {
      await api.patchSeries(id, {
        name: meta.name.trim() || null, weight_override_g: wgr === null ? null : Math.round(wgr * 0.06479891 * 10000) / 10000, trigger_mode: meta.trigger_mode || null,
        note: meta.note.trim() || null, charge_gr: charge, seating_depth_mm: seat,
      });
      setData(await api.seriesDetail(id));
      setInfo({ ok: t("saved") });
    } catch (e) {
      setInfo({ err: String((e as Error).message) });
    }
  };
  const removeSeries = async () => {
    if (!confirm(t("confirmDelete"))) return;
    try {
      await api.deleteSeries(id);
      go(data.load_id ? `/load/${data.load_id}` : "/");
    } catch (e) {
      failed(e);
    }
  };
  const setM = (k: string, v: string) => setMeta({ ...meta, [k]: v });
  const changeLoads = async (action: () => Promise<unknown>) => {
    try {
      await action();
      setAddLoad("");
      setData(await api.seriesDetail(id));
    } catch (e) {
      failed(e);
    }
  };
  return (
    <>
      <div class="row">
        <a class="btn ghost" href={data.load_id ? `#/load/${data.load_id}` : "#/"}>← {t("back")}</a>
        <div class="grow">
          <h1 style={{ marginBottom: 0 }}>{seriesLabel(data, t("series"))}{data.loads.length ? ` · ${data.loads.map((l) => l.name).join(", ")}` : ""}</h1>
          <div class="muted">{t("date")}: {dateRange(data.shots.map((s) => s.taken_at), lang)}</div>
        </div>
        {reportLinks(pdf, urls.reportSeries(id, { lang, units }), urls.reportSeries(id, { lang, units }) + "&format=html", t, urls.exportSeries(id, { lang, units }))}
      </div>
      <StatCards s={data.stats} total={data.shots_total} weightsG={data.shots.map((x) => x.weight_g)} loadGr={data.load?.bullet_weight_gr} overridden={{ count: data.weight_override_g ? 1 : 0, total: 1 }} bc={data.bc} />
      <section class="panel">
        <div class="row"><h2 class="grow">{t("trackTitle")}</h2><span class="muted small">{t("trackHint")}</span></div>
        <SvgChart hover onPick={setSel} url={urls.seriesChart(id, { sel: sel ?? undefined, lang, units })} />
      </section>
      <div class="sidebar-layout">
        <section class="panel main" aria-label={t("shots")}>
          <h2>{t("shots")}</h2>
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead><tr><th>#</th><th class="n">V0 ({u.v})</th><th class="n">{t("energyCol")} ({u.e})</th><th class="n">{t("impulseCol")}</th><th>{t("time")}</th><th>{t("signal")}</th><th>{t("status")}</th></tr></thead>
              <tbody>
                {data.shots.map((s) => (
                  <tr key={s.number} class={`pickable ${s.number === sel ? "sel" : ""} ${s.excluded ? "ex" : ""}`} onClick={() => setSel(s.number)}>
                    <td><button class="plain" onClick={() => setSel(s.number)} aria-label={`${t("shot")} ${s.number}`}>{s.number}</button></td>
                    <td class="n v0">{fmt(vOut(s.v0_ms, units), 1, lang)}</td>
                    <td class="n">{fmt(eOut(s.energy0_j, units), 0, lang)}</td>
                    <td class="n">{fmt(s.mip, 0, lang)}</td>
                    <td class="mono small">{s.taken_at.slice(11, 19)}</td>
                    <td><Bars n={s.signal_strength} /></td>
                    <td>
                      <button class="btn" style={{ minWidth: 130, justifyContent: "center" }} aria-pressed={s.excluded} onClick={(e) => { e.stopPropagation(); toggleShot(s.number, !s.excluded); }}>
                        {s.excluded ? t("excluded") : t("included")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <div class="side col">
          {shot && (
            <section class="panel" aria-label={t("detail")}>
              <h2>{t("detail")}: {t("shot")} {shot.number}</h2>
              <div class="muted small">{t("signal")}: {shot.signal_strength ?? "–"}/5 · PF {fmt(shot.power_factor, 1, lang)}</div>
              <table>
                <thead><tr><th>{t("distance")} ({u.d})</th><th class="n">V ({u.v})</th><th class="n">E ({u.e})</th><th class="n">MIP</th></tr></thead>
                <tbody>
                  <tr><td class="mono">0</td><td class="n">{fmt(vOut(shot.v0_ms, units), 1, lang)}</td><td class="n">{fmt(eOut(shot.energy0_j, units), 0, lang)}</td><td class="n">{impulseAt(shot.v0_ms)}</td></tr>
                  {shot.distances_m.map((d, i) => (
                    <tr key={i}><td class="mono">{fmt(dOut(d, units), units === "imp" ? 1 : 0, lang)}</td><td class="n">{fmt(vOut(shot.velocities_ms[i], units), 1, lang)}</td><td class="n">{fmt(eOut(shot.energies_j[i], units), 0, lang)}</td><td class="n">{impulseAt(shot.velocities_ms[i])}</td></tr>
                  ))}
                </tbody>
              </table>
              <button class="btn" style={{ marginTop: 10 }} onClick={() => toggleShot(shot.number, !shot.excluded)}>{shot.excluded ? t("includeShot") : t("excludeShot")}</button>
            </section>
          )}
          <section class="panel col">
            <Field label={`${t("name")} (${t("nameHint")})`}><input type="text" maxLength={200} value={meta.name} onInput={(e) => setM("name", e.currentTarget.value)} /></Field>
            <Field label={`${t("weightOverride")} (${t("weightOverrideHint")}; ${t("weightMeasured")}: ${fmt(data.weight_measured_g === null ? null : data.weight_measured_g / 0.06479891, 0, lang)} gr)`}>
              <input type="text" inputMode="decimal" value={meta.weight_gr} onInput={(e) => setM("weight_gr", e.currentTarget.value)} />
            </Field>
            <div>
              <div class="flabel">{t("loadsOfSeries")}</div>
              <div class="row" style={{ marginTop: 6 }}>
                {data.loads.length === 0 && <span class="muted">{t("unassigned")}</span>}
                {data.loads.map((l) => (
                  <span class="chip" key={l.id}>
                    <a href={`#/load/${l.id}`}>{l.name}</a>
                    <button class="chip-x" aria-label={t("removeFromLoad").replace("{name}", l.name)} onClick={() => changeLoads(() => api.removeFromLoad(id, l.id))}>×</button>
                  </span>
                ))}
              </div>
              <div class="row" style={{ marginTop: 8 }}>
                <select aria-label={t("assignTo")} style={{ width: "auto" }} value={addLoad} onChange={(e) => setAddLoad(e.currentTarget.value)}>
                  <option value="">{t("chooseLoadShort")}</option>
                  {(loads.data ?? []).filter((l: Load) => !data.load_ids.includes(l.id)).map((l: Load) => <option value={l.id}>{l.name}</option>)}
                </select>
                <button class="btn" disabled={!addLoad} onClick={() => changeLoads(() => api.addToLoad(id, Number(addLoad)))}>{t("addToLoad")}</button>
              </div>
              <div class="muted small" style={{ marginTop: 4 }}>{t("addToLoadHint")}</div>
            </div>
            <div class="row">
              <Field label={t("charge_gr")}><input type="text" inputMode="decimal" value={meta.charge_gr} onInput={(e) => setM("charge_gr", e.currentTarget.value)} /></Field>
              <Field label={t("seating_depth_mm")}><input type="text" inputMode="decimal" value={meta.seating_depth_mm} onInput={(e) => setM("seating_depth_mm", e.currentTarget.value)} /></Field>
            </div>
            <Field label={t("trigger")}>
              <select value={meta.trigger_mode} onChange={(e) => setM("trigger_mode", e.currentTarget.value)}>
                <option value="">{t("notSet")}</option>
                {(["doppler", "internal", "external"] as const).map((k) => <option value={k}>{t(`trigger_${k}` as Key)}</option>)}
              </select>
            </Field>
            <Field label={t("note")}><textarea value={meta.note} maxLength={4000} onInput={(e) => setM("note", e.currentTarget.value)} /></Field>
            <div class="row">
              <button class="btn primary" onClick={saveMeta}>{t("save")}</button>
              <button class="btn danger" onClick={removeSeries}>{t("deleteSeries")}</button>
            </div>
            <Msg ok={info.ok} err={info.err} />
          </section>
        </div>
      </div>
    </>
  );
}

// ---------- Vergleich ----------
/** Zurück-Ziel des Vergleichs: die gemeinsame Laborierung der Serien, sonst die Übersicht (kein history.back: CSP blockt javascript:-Links). */
export function backTarget(series: { load_ids: number[] }[]): string {
  const common = (series[0]?.load_ids ?? []).filter((id) => series.every((s) => s.load_ids.includes(id)));
  return common.length ? `#/load/${common[0]}` : "#/";
}

export function CompareView({ ids }: { ids: number[] }) {
  const { t, lang, units, pdf } = useApp();
  const [trend, setTrend] = useState(true);
  const { data, error } = useAsync(() => Promise.all(ids.map((i) => api.seriesDetail(i))), [ids.join(",")]);
  if (!data) return <Loading error={error} />;
  const u = unitNames(units);
  let prev: number | null = null;
  return (
    <>
      <div class="row">
        <a class="btn ghost" href={backTarget(data)}>← {t("back")}</a>
        <h1 class="grow">{t("compareTitle")}</h1>
        {reportLinks(pdf, urls.reportCompare(ids, { lang, units }), urls.reportCompare(ids, { lang, units }) + "&format=html", t)}
      </div>
      <section class="panel">
        <div class="row">
          <h2 class="grow">V0 · ±1 SD</h2>
          <button class="btn" aria-pressed={trend} onClick={() => setTrend(!trend)} style={trend ? { background: "var(--border)", fontWeight: 600 } : undefined}>{t("trendOn")}</button>
        </div>
        <SvgChart url={urls.compareChart(ids, { trend, lang, units })} />
      </section>
      <section class="panel" style={{ overflowX: "auto" }}>
        <table>
          <thead><tr><th>{t("series")}</th><th class="n">{t("shots")}</th><th class="n">{t("charge_gr")}</th><th class="n">{t("seating_depth_mm")}</th><th class="n">Ø ({u.v})</th><th class="n">SD</th><th class="n">ES</th><th class="n">Δ Ø</th></tr></thead>
          <tbody>
            {data.map((s: SeriesDetail) => {
              const avg = s.stats.avg === null ? null : vOut(s.stats.avg, units);
              const delta = avg !== null && prev !== null ? avg - prev : null;
              if (avg !== null) prev = avg;
              return (
                <tr key={s.id}>
                  <td><a href={`#/series/${s.id}`}>{seriesLabel(s, t("series"))}</a></td>
                  <td class="n">{s.stats.n}/{s.shots_total}</td><td class="n">{fmt(s.charge_gr, 1, lang)}</td><td class="n">{fmt(s.seating_depth_mm, 2, lang)}</td>
                  <td class="n">{fmt(avg, 1, lang)}</td>
                  <td class="n">{fmt(s.stats.sd === null ? null : vOut(s.stats.sd, units), 1, lang)}</td>
                  <td class="n">{fmt(s.stats.es === null ? null : vOut(s.stats.es, units), 1, lang)}</td>
                  <td class="n">{delta === null ? "–" : `${delta >= 0 ? "+" : "−"}${fmt(Math.abs(delta), 1, lang)}`}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </>
  );
}

// ---------- Import ----------
export function ImportView() {
  const { t, lang } = useApp();
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [result, setResult] = useState<Aggregate | null>(null);
  const [progress, setProgress] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const free = useAsync(() => api.series(true), []);
  const loads = useAsync(() => api.loads(), []);
  const input = useRef<HTMLInputElement>(null);
  const folder = useRef<HTMLInputElement>(null);

  const upload = useCallback(async (sources: Source[]) => {
    const usable = sources.filter((s) => s.kind === "folder" || isUploadFile(s.name));
    if (usable.length === 0) {
      setErr(t("importNothing"));
      return;
    }
    setBusy(true);
    setErr(null);
    setResult(null);
    try {
      setResult(await runImport(usable, undefined, (d, n) => setProgress(n > 1 ? `${d}/${n}` : null), (n) => `${n}: ${t("noLabradarFiles")}`));
      free.reload();
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(false);
      setProgress(null);
    }
  }, []);
  const [picked, setPicked] = useState<number[]>([]);
  const [target, setTarget] = useState("");
  const [done, setDone] = useState<{ ids: number[]; load: string } | null>(null);
  const [assignErr, setAssignErr] = useState<string | null>(null);
  const rows = free.data ?? [];
  // Zuordnung erst auf Knopfdruck; danach lässt sie sich über "Rückgängig" zurücknehmen
  const assignPicked = async () => {
    if (!target || picked.length === 0) return;
    setAssignErr(null);
    try {
      for (const sid of picked) await api.patchSeries(sid, { load_id: Number(target) });
      setDone({ ids: picked, load: (loads.data ?? []).find((l) => String(l.id) === target)?.name ?? "" });
      setPicked([]);
    } catch (e) {
      setAssignErr(`${t("assignFailed")}: ${(e as Error).message}`);
    }
    free.reload();
  };
  const deletePicked = async () => {
    if (picked.length === 0 || !confirm(`${picked.length} ${t("deleteSeriesConfirm")}`)) return;
    setAssignErr(null);
    try {
      for (const sid of picked) await api.deleteSeries(sid);
      setPicked([]);
      setDone(null);
    } catch (e) {
      setAssignErr(`${t("deleteFailed")}: ${(e as Error).message}`);
    }
    free.reload();
  };
  const undo = async () => {
    if (!done) return;
    for (const sid of done.ids) await api.patchSeries(sid, { load_id: null });
    setDone(null);
    free.reload();
  };
  return (
    <>
      <h1>{t("importTitle")}</h1>
      <div
        class={`drop ${over ? "over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={async (e) => { e.preventDefault(); setOver(false); if (e.dataTransfer) upload(await sourcesFromDrop(e.dataTransfer)); }}
      >
        <p class="muted">{t("importHint")}</p>
        <input ref={input} type="file" multiple accept=".zip,.grtload,application/zip" hidden onChange={(e) => { upload(sourcesFromInput(Array.from(e.currentTarget.files ?? []))); e.currentTarget.value = ""; }} />
        <input ref={folder} type="file" hidden {...{ webkitdirectory: true, directory: true }} onChange={(e) => { upload(sourcesFromInput(Array.from(e.currentTarget.files ?? []))); e.currentTarget.value = ""; }} />
        <div class="row" style={{ justifyContent: "center" }}>
          <button class="btn primary" disabled={busy} onClick={() => input.current?.click()}>{busy ? `${t("importing")}${progress ? ` ${progress}` : ""}` : t("chooseFile")}</button>
          <button class="btn" disabled={busy} onClick={() => folder.current?.click()}>{t("chooseFolder")}</button>
        </div>
      </div>
      <Msg err={err} />
      {result && (
        <div class="msg" role="status">
          {result.imported.length} {t("importedN")} · {result.skipped} {t("skippedN")}
          {result.load_id !== null && <> · <a href={`#/load/${result.load_id}`}>{t("openLoad")}</a></>}
          {result.warnings.length > 0 && <div><strong>{t("warnings")}:</strong> {result.warnings.map((w) => renderAny(w, lang)).join(" · ")}</div>}
          {result.errors.length > 0 && <div role="alert" style={{ color: "var(--red, #ff8a80)" }}>{result.errors.join(" · ")}</div>}
        </div>
      )}
      <section class="panel">
        <h2>{t("unassignedSeries")}</h2>
        {done && (
          <div class="msg" role="status">
            {done.ids.length} {t("assignedN")} „{done.load}" <button class="btn" onClick={undo}>{t("undo")}</button>
          </div>
        )}
        <Msg err={assignErr} />
        {rows.length === 0 && <p class="muted">{t("none")}</p>}
        {rows.length > 0 && (
          <>
            <table>
              <thead>
                <tr>
                  <th style={{ width: 36 }}>
                    <input type="checkbox" aria-label={t("selectAll")} checked={rows.every((r) => picked.includes(r.id))} onChange={() => setPicked(toggleAll(picked, rows.map((r) => r.id)))} style={{ width: 20, height: 20 }} />
                  </th>
                  <th>{t("series")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s: SeriesSummary) => (
                  <tr key={s.id} class={`pickable ${picked.includes(s.id) ? "sel" : ""}`} onClick={() => setPicked(togglePick(picked, s.id))}>
                    <td><input type="checkbox" aria-label={`${t("selectSeries")} ${seriesLabel(s, t("series"))}`} checked={picked.includes(s.id)} onChange={() => setPicked(togglePick(picked, s.id))} onClick={(e) => e.stopPropagation()} style={{ width: 20, height: 20 }} /></td>
                    <td><a href={`#/series/${s.id}`} onClick={(e) => e.stopPropagation()}>{seriesLabel(s, t("series"))}</a> <span class="muted small">{dateText(s.taken_at, lang)} · {s.shots_total} {t("shots")}{s.charge_gr !== null ? ` · ${fmt(s.charge_gr, 1, lang)} gr` : ""}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div class="row" style={{ marginTop: 12 }}>
              <span class="muted small">{picked.length} {t("selectedN")}</span>
              <select aria-label={t("assignTo")} style={{ width: "auto", minWidth: 240 }} value={target} onChange={(e) => setTarget(e.currentTarget.value)}>
                <option value="">{t("chooseLoad")}</option>
                {(loads.data ?? []).map((l) => <option value={l.id}>{l.name}</option>)}
              </select>
              <button class="btn primary" disabled={!target || picked.length === 0} onClick={assignPicked}>{t("assignSelected")}{picked.length > 0 ? ` (${picked.length})` : ""}</button>
              <span class="grow" />
              <button class="btn" disabled={picked.length === 0} onClick={deletePicked} style={{ color: "var(--red, #ff8a80)" }}>{t("deleteSelected")}{picked.length > 0 ? ` (${picked.length})` : ""}</button>
            </div>
          </>
        )}
      </section>
    </>
  );
}

// ---------- Waffen ----------
export function WeaponsView() {
  const { t } = useApp();
  const { data, error, reload } = useAsync(() => api.weapons(), []);
  const [form, setForm] = useState<{ id: number | null; name: string; caliber: string; barrel: string; twist: string }>({ id: null, name: "", caliber: "", barrel: "", twist: "" });
  const [err, setErr] = useState<string | null>(null);
  if (!data) return <Loading error={error} />;
  const reset = () => setForm({ id: null, name: "", caliber: "", barrel: "", twist: "" });
  const save = async () => {
    const barrel = parseNum(form.barrel);
    if (barrel === undefined) return setErr(t("invalidNumber"));
    if (!form.name.trim()) return setErr(t("weaponName"));
    const body: Partial<Weapon> = { name: form.name.trim(), caliber: form.caliber.trim() || null, barrel_length_mm: barrel, twist: form.twist.trim() || null };
    try {
      if (form.id === null) await api.createWeapon(body);
      else await api.updateWeapon(form.id, body);
      setErr(null);
      reset();
      reload();
    } catch (e) {
      setErr(String((e as Error).message));
    }
  };
  const edit = (w: Weapon) => setForm({ id: w.id, name: w.name, caliber: w.caliber ?? "", barrel: w.barrel_length_mm === null || w.barrel_length_mm === undefined ? "" : String(w.barrel_length_mm), twist: w.twist ?? "" });
  const remove = async (w: Weapon) => {
    if (confirm(t("confirmDelete"))) {
      await api.deleteWeapon(w.id);
      reload();
    }
  };
  const f = (k: "name" | "caliber" | "barrel" | "twist") => (e: Event) => setForm({ ...form, [k]: (e.currentTarget as HTMLInputElement).value });
  return (
    <>
      <h1>{t("weaponsTitle")}</h1>
      <section class="panel col">
        <div class="row">
          <Field label={t("weaponName")}><input type="text" value={form.name} maxLength={200} onInput={f("name")} /></Field>
          <Field label={t("caliber")}><input type="text" value={form.caliber} maxLength={200} onInput={f("caliber")} /></Field>
          <Field label={t("barrel")}><input type="text" inputMode="decimal" value={form.barrel} onInput={f("barrel")} /></Field>
          <Field label={t("twist")}><input type="text" value={form.twist} maxLength={50} onInput={f("twist")} /></Field>
        </div>
        <div class="row">
          <button class="btn primary" onClick={save}>{t("save")}</button>
          {form.id !== null && <button class="btn" onClick={reset}>{t("cancel")}</button>}
        </div>
        <Msg err={err} />
      </section>
      <section class="panel">
        {data.length === 0 && <p class="muted">{t("none")}</p>}
        <table>
          <tbody>
            {data.map((w) => (
              <tr key={w.id}>
                <td><strong>{w.name}</strong> <span class="muted small">{[w.caliber, w.barrel_length_mm ? `${w.barrel_length_mm} mm` : null, w.twist].filter(Boolean).join(" · ")}</span></td>
                <td style={{ width: 200, textAlign: "right" }}>
                  <button class="btn" onClick={() => edit(w)}>{t("open")}</button>{" "}
                  <button class="btn danger" onClick={() => remove(w)}>{t("remove")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
