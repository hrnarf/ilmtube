import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { loadYT } from "./components";
import { useData } from "./ctx";
import { loadShorts, type Video } from "./lib/data";
import { ago, thumb, views, ytLink } from "./lib/format";
import { href, type Route } from "./lib/router";

// Once the viewer taps for sound, later clips start unmuted (browsers allow sound after a tap).
let soundPref = false;

/** Mix channels round-robin (newest first within each) so one channel doesn't fill a whole stretch of the feed. */
function mix(list: Video[]): Video[] {
  const by = new Map<number, Video[]>();
  for (const v of [...list].sort((a, b) => b.p.localeCompare(a.p))) (by.get(v.c) ?? by.set(v.c, []).get(v.c)!).push(v);
  const lanes = [...by.values()], out: Video[] = [];
  for (let i = 0; out.length < list.length; i++) for (const l of lanes) if (l[i]) out.push(l[i]);
  return out;
}

function ShortPlayer({ id }: { id: string }) {
  const box = useRef<HTMLDivElement>(null);
  const player = useRef<any>(null);
  const [muted, setMuted] = useState(!soundPref);
  const [paused, setPaused] = useState(false);
  const [fallback, setFallback] = useState(false);
  useEffect(() => {
    let dead = false;
    loadYT().then(() => {
      if (dead || !box.current) return;
      const target = document.createElement("div");
      box.current.replaceChildren(target);
      player.current = new window.YT.Player(target, {
        host: "https://www.youtube-nocookie.com", videoId: id, width: "100%", height: "100%",
        playerVars: { autoplay: 1, mute: soundPref ? 0 : 1, controls: 0, loop: 1, playlist: id, playsinline: 1, rel: 0, modestbranding: 1, fs: 0, disablekb: 1 },
        events: { onReady: (e: any) => { if (!soundPref) e.target.mute(); e.target.playVideo(); }, onError: () => setFallback(true) },
      });
    }).catch(() => setFallback(true));
    return () => { dead = true; try { player.current?.destroy(); } catch { /* ignore */ } player.current = null; };
  }, [id]);
  const tap = () => {
    const p = player.current;
    if (!p) return;
    try {
      if (muted) { p.unMute(); soundPref = true; setMuted(false); }
      else if (paused) { p.playVideo(); setPaused(false); }
      else { p.pauseVideo(); setPaused(true); }
    } catch { /* player not ready */ }
  };
  if (fallback) {
    return <iframe class="short-frame" title="Short" allow="autoplay; encrypted-media; picture-in-picture" allowFullScreen
      src={`https://www.youtube-nocookie.com/embed/${id}?autoplay=1&mute=1&loop=1&playlist=${id}&playsinline=1&rel=0`} />;
  }
  return (
    <>
      <div class="short-frame" ref={box} />
      <button class="tap" aria-label={muted ? "Turn sound on" : paused ? "Play" : "Pause"} onClick={tap}>
        {muted && <span class="badge">🔇 Tap for sound</span>}
        {!muted && paused && <span class="badge big">▶</span>}
      </button>
    </>
  );
}

export function Shorts({ route }: { route: Route }) {
  const d = useData();
  const topic = route.query.get("topic") ?? "";
  const startId = route.path[1];
  const [all, setAll] = useState<Video[] | null>(null);
  const [active, setActive] = useState(0);
  const [playing, setPlaying] = useState(-1);
  const reel = useRef<HTMLDivElement>(null);
  useEffect(() => { loadShorts().then(setAll); }, []);
  const list = useMemo(() => (all ? mix(all.filter((v) => !topic || v.tp.some((t) => t.startsWith(`${topic}.`)))) : []), [all, topic]);
  const counts = useMemo(() => d.topics.map((p) => ({ p, n: (all ?? []).filter((v) => v.tp.some((t) => t.startsWith(`${p.id}.`))).length })).filter((x) => x.n), [all]);

  // Jump to the linked clip (or the top) once the list is ready.
  useEffect(() => {
    const el = reel.current;
    if (!el || !list.length) return;
    const i = Math.max(0, list.findIndex((v) => v.id === startId));
    el.scrollTop = i * el.clientHeight;
    setActive(i);
  }, [list]);

  // Which slide is on screen; the player only mounts once the viewer settles on it.
  useEffect(() => {
    const t = setTimeout(() => setPlaying(active), 180);
    return () => clearTimeout(t);
  }, [active]);
  useEffect(() => {
    const v = list[playing];
    if (v) history.replaceState(null, "", href(`/shorts/${v.id}`, { topic: topic || undefined }));
  }, [playing]);

  const go = (i: number) => {
    const el = reel.current;
    if (el && i >= 0 && i < list.length) el.scrollTo({ top: i * el.clientHeight, behavior: "smooth" });
  };
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "INPUT") return;
      if (e.key === "ArrowDown" || e.key === "j") { e.preventDefault(); go(active + 1); }
      if (e.key === "ArrowUp" || e.key === "k") { e.preventDefault(); go(active - 1); }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [active, list]);

  let raf = 0;
  const onScroll = () => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      const el = reel.current;
      if (el) setActive(Math.round(el.scrollTop / el.clientHeight));
    });
  };

  return (
    <div class="reelwrap">
      <div class="reel-top">
        <a class="back" href="#/" aria-label="Back to IlmTube">←</a>
        <div class="reel-chips" role="tablist" aria-label="Filter shorts by topic">
          <a class={`chip${!topic ? " on" : ""}`} href={href("/shorts")}>All</a>
          {counts.map(({ p, n }) => <a class={`chip${topic === p.id ? " on" : ""}`} href={href("/shorts", { topic: p.id })}>{p.name} <small>{n}</small></a>)}
        </div>
        {list.length > 0 && <span class="count">{Math.min(active + 1, list.length)}/{list.length}</span>}
      </div>
      {!all && <p class="reel-msg">Loading…</p>}
      {all && !list.length && <p class="reel-msg">No shorts in this topic yet.</p>}
      <div class="reel" ref={reel} onScroll={onScroll}>
        {list.map((v, i) => {
          const near = Math.abs(i - active) <= 1;
          const sp = v.sp.map((id) => d.speakerById.get(id)?.name).filter(Boolean).join(", ");
          return (
            <section class="slide" aria-label={v.t} key={v.id}>
              {near && (
                <div class="stage">
                  <img class="poster" src={thumb(v.id)} alt="" />
                  {i === playing && <ShortPlayer id={v.id} />}
                  <div class="info">
                    <h2>{v.t}</h2>
                    <p>{d.channels[v.c].t}{sp ? ` · ${sp}` : ""} · {views(v.v)} · {ago(v.p)}</p>
                    <div class="info-row">
                      {v.tp.slice(0, 2).map((t) => <a class="chip" href={href("/shorts", { topic: t.split(".")[0] })}>{d.topicName.get(t)}</a>)}
                      <a class="chip yt" href={ytLink(v.id)} target="_blank" rel="noopener">Watch on YouTube ↗</a>
                    </div>
                  </div>
                </div>
              )}
            </section>
          );
        })}
      </div>
      <div class="rail">
        <button aria-label="Previous short" disabled={active <= 0} onClick={() => go(active - 1)}>▲</button>
        <button aria-label="Next short" disabled={active >= list.length - 1} onClick={() => go(active + 1)}>▼</button>
      </div>
    </div>
  );
}
