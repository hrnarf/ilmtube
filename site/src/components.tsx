import type { ComponentChildren } from "preact";
import { useEffect, useRef, useState } from "preact/hooks";
import { useData } from "./ctx";
import type { Video } from "./lib/data";
import { dur, thumb, views, ago, ytLink } from "./lib/format";
import { href, go } from "./lib/router";
import { fraction, getProgress, savePosition } from "./lib/store";

export function Header({ q }: { q: string }) {
  const [theme, setTheme] = useState(() => { try { return localStorage.getItem("ilmtube:theme") || ""; } catch { return ""; } });
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme; else delete document.documentElement.dataset.theme;
    try { theme ? localStorage.setItem("ilmtube:theme", theme) : localStorage.removeItem("ilmtube:theme"); } catch { /* ignore */ }
  }, [theme]);
  const dark = theme ? theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  return (
    <header class="top">
      <a class="logo" href="#/" aria-label="IlmTube home"><span class="mark">▶</span> IlmTube</a>
      <form class="searchbar" role="search" onSubmit={(e) => { e.preventDefault(); const v = new FormData(e.currentTarget as HTMLFormElement).get("q") as string; if (v.trim()) go("/search", { q: v.trim() }); }}>
        <input name="q" type="search" value={q} placeholder="Search lectures, speakers, surahs…" aria-label="Search" enterkeyhint="search" />
      </form>
      <nav class="nav">
        <a href="#/topics">Topics</a>
        <a href="#/shorts">Shorts</a>
        <button class="icon" aria-label="Toggle theme" onClick={() => setTheme(dark ? "light" : "dark")}>{dark ? "☀" : "☾"}</button>
      </nav>
    </header>
  );
}

export function Footer() {
  return (
    <footer class="foot">
      Videos belong to their channels. Inclusion isn't endorsement of every view. AI is used only to organise videos, never to produce religious content.
    </footer>
  );
}

export function ProgressBar({ value }: { value: number }) {
  return <div class="bar" role="progressbar" aria-valuenow={Math.round(value * 100)}><i style={{ width: `${Math.round(value * 100)}%` }} /></div>;
}

export function VideoCard({ v, ep, compact, eager }: { v: Video; ep?: number; compact?: boolean; eager?: boolean }) {
  const d = useData();
  const ch = d.channels[v.c];
  const sp = v.sp.map((id) => d.speakerById.get(id)?.name).filter(Boolean).join(", ");
  const f = fraction(getProgress(v.id));
  return (
    <a class={`card${compact ? " compact" : ""}`} href={href(`/watch/${v.id}`)}>
      <div class="thumb">
        <img src={thumb(v.id)} alt="" loading={eager ? "eager" : "lazy"} {...(eager ? { fetchpriority: "high" } : {})} width="320" height="180" />
        <span class="len">{dur(v.s)}</span>
        {f > 0 && <ProgressBar value={f} />}
      </div>
      <div class="meta">
        <h3>{ep ? <span class="ep">Ep. {ep} · </span> : null}{v.t}</h3>
        <p>{sp || ch.t}</p>
        <p class="dim">{views(v.v)} · {ago(v.p)}</p>
      </div>
    </a>
  );
}

export function Shelf({ title, more, children }: { title: string; more?: { label: string; href: string }; children: ComponentChildren }) {
  return (
    <section class="shelf">
      <div class="shelf-h"><h2>{title}</h2>{more && <a href={more.href}>{more.label}</a>}</div>
      <div class="row">{children}</div>
    </section>
  );
}

export function Chip({ href: h, on, children }: { href: string; on?: boolean; children: ComponentChildren }) {
  return <a class={`chip${on ? " on" : ""}`} href={h}>{children}</a>;
}

declare global { interface Window { YT?: any; onYouTubeIframeAPIReady?: () => void } }
let ytReady: Promise<void> | null = null;
export function loadYT(): Promise<void> {
  if (window.YT?.Player) return Promise.resolve();
  ytReady ??= new Promise((res, rej) => {
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => { prev?.(); res(); };
    const s = document.createElement("script");
    s.src = "https://www.youtube.com/iframe_api";
    s.onerror = () => rej(new Error("YouTube API failed to load"));
    document.head.appendChild(s);
  });
  return ytReady;
}

/** Official embed via youtube-nocookie. Saves the position every 10s and resumes from it. */
export function Player({ id, onEnded, autoplay }: { id: string; onEnded?: () => void; autoplay?: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  const [fallback, setFallback] = useState(false);
  useEffect(() => {
    let player: any, timer: number | undefined, dead = false;
    setFallback(false);
    loadYT().then(() => {
      if (dead || !box.current) return;
      const target = document.createElement("div");
      box.current.replaceChildren(target);
      const p = getProgress(id);
      const start = p && fraction(p) < 0.92 ? p.t : 0;
      const tick = () => { try { savePosition(id, player.getCurrentTime(), player.getDuration()); } catch { /* player not ready */ } };
      player = new window.YT.Player(target, {
        host: "https://www.youtube-nocookie.com", videoId: id,
        playerVars: { rel: 0, playsinline: 1, start, autoplay: autoplay ? 1 : 0 },
        events: {
          onStateChange: (e: any) => {
            window.clearInterval(timer);
            if (e.data === 1) timer = window.setInterval(tick, 10000);
            if (e.data === 2) tick();
            if (e.data === 0) { tick(); onEnded?.(); }
          },
          onError: () => setFallback(true),
        },
      });
    }).catch(() => setFallback(true));
    return () => {
      dead = true; window.clearInterval(timer);
      try { savePosition(id, player.getCurrentTime(), player.getDuration()); player.destroy(); } catch { /* ignore */ }
    };
  }, [id]);
  return (
    <div class="player">
      {fallback
        ? <iframe src={`https://www.youtube-nocookie.com/embed/${id}?rel=0`} title="Video player" allow="accelerometer; encrypted-media; picture-in-picture; fullscreen" allowFullScreen />
        : <div ref={box} />}
      <a class="yt" href={ytLink(id)} target="_blank" rel="noopener">Watch on YouTube ↗</a>
    </div>
  );
}
