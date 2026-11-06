import { useEffect, useMemo, useState } from "preact/hooks";
import { Chip, Player, ProgressBar, Shelf, VideoCard } from "./components";
import { useData } from "./ctx";
import type { Data, Video } from "./lib/data";
import { fetchIndex, loadDescs } from "./lib/data";
import { ago, dur, thumb, views, ytLink } from "./lib/format";
import { go, href, type Route } from "./lib/router";
import { fraction, getHistory, getProgress, isDone, getLater, toggleLater } from "./lib/store";
import { loadIndex, makeSearcher } from "./lib/searchcore.js";

const Grid = ({ children }: { children: preact.ComponentChildren }) => <div class="grid">{children}</div>;
const Empty = ({ children }: { children: preact.ComponentChildren }) => <p class="empty">{children}</p>;
const vids = (d: Data, ids: string[]) => ids.map((i) => d.byId.get(i)).filter((v): v is Video => !!v);

// ---------- search (index is loaded lazily on first use) ----------
let searcherP: Promise<ReturnType<typeof makeSearcher>> | null = null;
function useSearcher(d: Data) {
  const [s, setS] = useState<ReturnType<typeof makeSearcher> | null>(null);
  useEffect(() => {
    searcherP ??= fetchIndex().then((json) => makeSearcher(loadIndex(json), d.videos, d.surahs, d.synonyms));
    searcherP.then((fn) => setS(() => fn));
  }, []);
  return s;
}

const DUR: Record<string, (s: number) => boolean> = { lt10: (s) => s < 600, "10-30": (s) => s >= 600 && s < 1800, "30-60": (s) => s >= 1800 && s < 3600, "60+": (s) => s >= 3600 };

export function Search({ route }: { route: Route }) {
  const d = useData();
  const searcher = useSearcher(d);
  const q = route.query.get("q") ?? "";
  const f = (k: string) => route.query.get(k) ?? "";
  const [more, setMore] = useState(60);
  const set = (k: string, v: string) => {
    const next = Object.fromEntries(route.query.entries());
    if (v) next[k] = v; else delete next[k];
    go("/search", next);
  };
  const res = useMemo(() => (searcher && q ? searcher(q) : null), [searcher, q]);
  const list = useMemo(() => {
    if (!res) return [];
    let out = res.hits.map((h) => res.byId.get(h.id)!).filter(Boolean);
    const now = Date.now();
    out = out.filter((v) =>
      (!f("topic") || v.tp.some((t) => t === f("topic") || t.startsWith(`${f("topic")}.`))) &&
      (!f("speaker") || v.sp.includes(f("speaker"))) && (!f("channel") || String(v.c) === f("channel")) &&
      (!f("type") || v.ty === f("type")) && (!f("dur") || DUR[f("dur")](v.s)) && (!f("aud") || v.au.includes(f("aud"))) &&
      (!f("date") || now - new Date(v.p).getTime() < (f("date") === "month" ? 30 : 365) * 864e5));
    if (f("sort") === "new") out = [...out].sort((a, b) => b.p.localeCompare(a.p));
    if (f("sort") === "top") out = [...out].sort((a, b) => b.q - a.q);
    return out;
  }, [res, route.query.toString()]);
  const sel = (k: string, label: string, opts: [string, string][]) => (
    <select aria-label={label} class={f(k) ? "on" : ""} value={f(k)} onChange={(e) => set(k, (e.target as HTMLSelectElement).value)}>
      <option value="">{label}</option>{opts.map(([v, t]) => <option value={v}>{t}</option>)}
    </select>
  );
  const types = [...new Set(d.videos.map((v) => v.ty))].sort();
  return (
    <main>
      <h1 class="sr">Search</h1>
      {!q && <Empty>Type a topic, speaker or surah in the search bar.</Empty>}
      {q && !searcher && <Empty>Loading search…</Empty>}
      {res?.surah && (
        <a class="surahcard" href={href(`/search`, { q: `surah ${res.surah.en}` })}>
          <span class="ar">{res.surah.ar}</span>
          <span><b>Surah {res.surah.en}</b><br /><small>{res.surah.n} · {res.surah.count ? `${res.surah.count} video${res.surah.count > 1 ? "s" : ""} in the library` : "no videos tagged with this surah yet"}</small></span>
        </a>
      )}
      {res && (
        <>
          <div class="filters">
            {sel("topic", "Topic", d.topics.flatMap((p) => [[p.id, p.name] as [string, string], ...p.children.map((c) => [c.id, `  ${p.name} › ${c.name}`] as [string, string])]))}
            {sel("speaker", "Speaker", d.speakers.map((s) => [s.id, s.name]))}
            {sel("channel", "Channel", d.channels.map((c) => [String(c.i), c.t]))}
            {sel("type", "Type", types.map((t) => [t, t]))}
            {sel("dur", "Duration", [["lt10", "< 10 min"], ["10-30", "10–30 min"], ["30-60", "30–60 min"], ["60+", "60+ min"]])}
            {sel("date", "Date", [["month", "Past month"], ["year", "Past year"]])}
            {sel("aud", "Audience", ["general", "youth", "sisters", "brothers", "reverts", "kids", "parents"].map((a) => [a, a]))}
            {sel("sort", "Sort: relevance", [["new", "Newest"], ["top", "Top"]])}
          </div>
          <p class="dim">{list.length} result{list.length === 1 ? "" : "s"} for “{q}”</p>
          {list.length === 0 ? <Empty>No matches. Try fewer words or another spelling.</Empty> : (
            <Grid>{list.slice(0, more).map((v) => <VideoCard v={v} />)}</Grid>
          )}
          {list.length > more && <button class="more" onClick={() => setMore(more + 60)}>Show more</button>}
        </>
      )}
    </main>
  );
}

// ---------- home ----------
export function Home() {
  const d = useData();
  const hist = getHistory();
  const cont = Object.entries(hist)
    .filter(([id, p]) => d.byId.has(id) && !d.byId.get(id)!.id.startsWith("_") && p.t > 5 && !isDone(p))
    .sort((a, b) => b[1].at - a[1].at).slice(0, 10).map(([id]) => d.byId.get(id)!);
  const contSeries = d.series.map((s, i) => {
    const done = s.v.filter((id) => isDone(hist[id])).length, started = s.v.some((id) => hist[id]);
    const next = s.v.findIndex((id) => !isDone(hist[id]));
    const last = Math.max(0, ...s.v.map((id) => hist[id]?.at ?? 0));
    return { s, i, done, started, next, last };
  }).filter((x) => x.started && x.done < x.s.v.length).sort((a, b) => b.last - a.last).slice(0, 4);
  const forYou = useMemo(() => {
    const topic: Record<string, number> = {}, spk: Record<string, number> = {}, ser: Record<number, number> = {};
    const seen = new Set(Object.keys(hist));
    for (const id of seen) {
      const v = d.byId.get(id); if (!v) continue;
      const w = 1 + fraction(hist[id]);
      v.tp.forEach((t) => (topic[t] = (topic[t] ?? 0) + w)); v.sp.forEach((s) => (spk[s] = (spk[s] ?? 0) + w)); v.se?.forEach(([i]) => (ser[i] = (ser[i] ?? 0) + w));
    }
    if (!seen.size) return [];
    return d.videos.filter((v) => !seen.has(v.id) && v.cf >= 0.6)
      .map((v) => ({ v, sc: (v.tp.reduce((a, t) => a + (topic[t] ?? 0), 0) + v.sp.reduce((a, s) => a + (spk[s] ?? 0) * 1.5, 0) + (v.se ?? []).reduce((a, [i]) => a + (ser[i] ?? 0) * 2, 0)) * (1 + Math.max(v.q, 0) / 4) }))
      .filter((x) => x.sc > 0).sort((a, b) => b.sc - a.sc).slice(0, 10).map((x) => x.v);
  }, []);
  const later = getLater().map((id) => d.byId.get(id)).filter((v): v is Video => !!v).slice(0, 10);
  return (
    <main>
      <section class="hero">
        <h1>Learn with trusted voices</h1>
        <p>A searchable library of lectures and reminders from a hand-picked list of channels.</p>
        <form onSubmit={(e) => { e.preventDefault(); const v = new FormData(e.currentTarget as HTMLFormElement).get("q") as string; if (v.trim()) go("/search", { q: v.trim() }); }}>
          <input name="q" type="search" placeholder="Try “wudhu” or “surah kahf”" aria-label="Search the library" />
          <button>Search</button>
        </form>
      </section>
      {cont.length > 0 && <Shelf title="Continue watching">{cont.map((v) => <VideoCard v={v} />)}</Shelf>}
      {contSeries.length > 0 && (
        <Shelf title="Continue series">
          {contSeries.map(({ s, i, done, next }) => (
            <a class="card series-card" href={href(`/series/${i}`)}>
              <div class="meta"><h3>{s.t}</h3><p>{d.channels[s.c].t}</p><ProgressBar value={done / s.v.length} />
                <p class="dim">Resume episode {Math.max(next, 0) + 1} · {done}/{s.v.length} watched</p></div>
            </a>
          ))}
        </Shelf>
      )}
      {forYou.length > 0 && <Shelf title="For you">{forYou.map((v) => <VideoCard v={v} />)}</Shelf>}
      {later.length > 0 && <Shelf title="Watch later">{later.map((v) => <VideoCard v={v} />)}</Shelf>}
      <Shelf title="New & noteworthy">{vids(d, d.shelves.noteworthy).slice(0, 12).map((v, i) => <VideoCard v={v} eager={i < 2} />)}</Shelf>
      <section class="shelf">
        <div class="shelf-h"><h2>Browse topics</h2><a href="#/topics">All topics</a></div>
        <div class="tiles">{d.topics.filter((t) => t.n).map((t) => <a class="tile" href={href(`/topic/${t.id}`)}><b>{t.name}</b><small>{t.n} videos</small></a>)}</div>
      </section>
      <section class="shelf"><div class="shelf-h"><h2>Shorts</h2><a href="#/shorts">Open Shorts</a></div>
        <p class="dim">{d.shortCount} short clips live in their own section so they don't crowd out full lectures.</p></section>
    </main>
  );
}

// ---------- topics ----------
export function Topics() {
  const d = useData();
  return (
    <main><h1>Topics</h1>
      {d.topics.map((p) => (
        <section class="shelf"><div class="shelf-h"><h2><a href={href(`/topic/${p.id}`)}>{p.name}</a></h2><span class="dim">{p.n}</span></div>
          <div class="chips">{p.children.map((c) => <Chip href={href(`/topic/${c.id}`)}>{c.name} <small>{c.n}</small></Chip>)}</div></section>
      ))}
    </main>
  );
}

export function Topic({ route }: { route: Route }) {
  const d = useData();
  const slug = route.path[1] ?? "";
  const parent = d.topics.find((p) => p.id === slug.split(".")[0]);
  const tab = route.query.get("tab") ?? "timeless";
  if (!parent) return <main><Empty>Unknown topic.</Empty></main>;
  const inTopic = (v: Video) => v.tp.some((t) => (slug.includes(".") ? t === slug : t.startsWith(`${slug}.`)));
  const all = d.videos.filter(inTopic);
  const timeless = [...all].filter((v) => v.cf >= 0.6).sort((a, b) => b.q - a.q).slice(0, 48);
  const newest = [...all].sort((a, b) => b.p.localeCompare(a.p)).slice(0, 48);
  const sers = d.series.map((s, i) => ({ s, i, n: s.v.filter((id) => { const v = d.byId.get(id); return v && inTopic(v); }).length })).filter((x) => x.n >= 2).sort((a, b) => b.n - a.n);
  const name = slug.includes(".") ? d.topicName.get(slug) : parent.name;
  const tabs: [string, string][] = [["timeless", "Timeless"], ["new", "Newest"], ["series", "Series"]];
  return (
    <main>
      <p class="crumb"><a href="#/topics">Topics</a> › {slug.includes(".") ? <a href={href(`/topic/${parent.id}`)}>{parent.name}</a> : parent.name}</p>
      <h1>{name} <small class="dim">{all.length} videos</small></h1>
      <div class="chips">{parent.children.map((c) => <Chip href={href(`/topic/${c.id}`)} on={c.id === slug}>{c.name} <small>{c.n}</small></Chip>)}</div>
      <div class="tabs">{tabs.map(([k, t]) => <a class={tab === k ? "on" : ""} href={href(`/topic/${slug}`, { tab: k })}>{t}</a>)}</div>
      {all.length === 0 && <Empty>No videos in this topic yet.</Empty>}
      {tab === "timeless" && <Grid>{timeless.map((v) => <VideoCard v={v} />)}</Grid>}
      {tab === "new" && <Grid>{newest.map((v) => <VideoCard v={v} />)}</Grid>}
      {tab === "series" && (sers.length ? <div class="list">{sers.map(({ s, i, n }) => <a class="row-link" href={href(`/series/${i}`)}><b>{s.t}</b><small>{d.channels[s.c].t} · {n} in this topic · {s.v.length} episodes</small></a>)}</div> : <Empty>No series in this topic yet.</Empty>)}
    </main>
  );
}

// ---------- speaker ----------
export function Speaker({ route }: { route: Route }) {
  const d = useData();
  const id = route.path[1];
  const sp = d.speakerById.get(id);
  if (!sp) return <main><Empty>Unknown speaker.</Empty></main>;
  const topic = route.query.get("topic") ?? "";
  const all = d.videos.filter((v) => v.sp.includes(id));
  const list = all.filter((v) => !topic || v.tp.some((t) => t.startsWith(topic))).sort((a, b) => b.p.localeCompare(a.p));
  const sers = d.series.map((s, i) => ({ s, i, n: s.v.filter((x) => d.byId.get(x)?.sp.includes(id)).length })).filter((x) => x.n >= 3);
  const tops = [...new Set(all.flatMap((v) => v.tp.map((t) => t.split(".")[0])))];
  return (
    <main>
      <h1>{sp.name}</h1>
      <p class="dim">{all.length} videos{sp.ns ? ` · ${sp.ns} shorts` : ""}{sp.aliases.length ? ` · also: ${sp.aliases.join(", ")}` : ""}</p>
      <div class="chips"><Chip href={href(`/speaker/${id}`)} on={!topic}>All</Chip>{tops.map((t) => <Chip href={href(`/speaker/${id}`, { topic: t })} on={topic === t}>{d.topicName.get(t)}</Chip>)}</div>
      {sers.length > 0 && <Shelf title="Series">{sers.map(({ s, i, n }) => <a class="card series-card" href={href(`/series/${i}`)}><div class="meta"><h3>{s.t}</h3><p class="dim">{n} episodes by {sp.name}</p></div></a>)}</Shelf>}
      <Grid>{list.slice(0, 60).map((v) => <VideoCard v={v} />)}</Grid>
    </main>
  );
}

// ---------- series ----------
export function SeriesPage({ route }: { route: Route }) {
  const d = useData();
  const s = d.series[Number(route.path[1])];
  if (!s) return <main><Empty>Unknown series.</Empty></main>;
  const hist = getHistory();
  const eps = s.v.map((id, n) => ({ v: d.byId.get(id)!, n: n + 1 })).filter((e) => e.v);
  const done = eps.filter((e) => isDone(hist[e.v.id])).length;
  const next = eps.find((e) => !isDone(hist[e.v.id])) ?? eps[0];
  return (
    <main>
      <p class="crumb">{d.channels[s.c].t}</p>
      <h1>{s.t}</h1>
      <ProgressBar value={eps.length ? done / eps.length : 0} />
      <p class="dim">{done} of {eps.length} watched</p>
      {next && <a class="btn" href={href(`/watch/${next.v.id}`)}>{done ? `Resume episode ${next.n}` : "Start episode 1"}</a>}
      <Grid>{eps.map((e) => <VideoCard v={e.v} ep={e.n} />)}</Grid>
    </main>
  );
}

// ---------- video ----------
export function Watch({ route }: { route: Route }) {
  const d = useData();
  const v = d.byId.get(route.path[1]);
  const [later, setLater] = useState(false);
  const [desc, setDesc] = useState("");
  useEffect(() => { setLater(!!v && getLater().includes(v.id)); setDesc(""); if (v) loadDescs().then((m) => setDesc(m[v.id] ?? "")).catch(() => {}); }, [v?.id]);
  if (!v) return <main><Empty>This video isn't in the library.</Empty></main>;
  const ch = d.channels[v.c];
  const [si, ep] = v.se?.[0] ?? [-1, 0];
  const series = si >= 0 ? d.series[si] : null;
  const nextUp = useMemo(() => {
    const out: Video[] = [], seen = new Set([v.id]);
    const add = (x?: Video) => { if (x && !seen.has(x.id) && !x.id.startsWith("_") && out.length < 8) { seen.add(x.id); out.push(x); } };
    if (series) series.v.slice(ep).forEach((id) => add(d.byId.get(id)));
    const same = (f: (x: Video) => boolean) => d.videos.filter(f).sort((a, b) => b.q - a.q).forEach(add);
    same((x) => x.sp.some((s) => v.sp.includes(s)) && x.tp.some((t) => v.tp.includes(t)));
    same((x) => x.tp.some((t) => v.tp.includes(t)) && x.cf >= 0.6);
    return out;
  }, [v.id]);
  return (
    <main class="watch">
      <div class="main-col">
        <Player id={v.id} />
        <h1 class="vt">{v.t}</h1>
        <p class="dim">{ch.t} · {views(v.v)} · {ago(v.p)} · {dur(v.s)}</p>
        <div class="chips">
          {v.sp.map((s) => <Chip href={href(`/speaker/${s}`)}>🎙 {d.speakerById.get(s)?.name}</Chip>)}
          {v.tp.map((t) => <Chip href={href(`/topic/${t}`)}>{d.topicName.get(t)}</Chip>)}
          {series && <Chip href={href(`/series/${si}`)}>Series: {series.t} (ep. {ep})</Chip>}
          <button class="chip" onClick={() => { toggleLater(v.id); setLater(!later); }}>{later ? "✓ Watch later" : "+ Watch later"}</button>
        </div>
        {desc && <p class="desc">{desc}{desc.length >= 280 ? "…" : ""}</p>}
        <a class="btn ghost" href={ytLink(v.id)} target="_blank" rel="noopener">Watch on YouTube ↗</a>
      </div>
      <aside class="side"><h2>Up next</h2>{nextUp.map((x) => <VideoCard v={x} compact />)}</aside>
    </main>
  );
}
