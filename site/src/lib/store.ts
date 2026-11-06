// Per-viewer state in localStorage (no accounts). Every access is guarded: storage can be blocked or empty.
export interface Progress { t: number; d: number; at: number }
interface State { history: Record<string, Progress>; later: string[]; liked: string[] }
const KEY = "ilmtube:v1";
let mem: State = { history: {}, later: [], liked: [] };

function load(): State {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) mem = { ...mem, ...JSON.parse(raw) };
  } catch { /* use in-memory */ }
  return mem;
}
function save() { try { localStorage.setItem(KEY, JSON.stringify(mem)); } catch { /* ignore */ } }

let loaded = false;
const state = () => { if (!loaded) { load(); loaded = true; } return mem; };

export const getHistory = () => state().history;
export const getProgress = (id: string): Progress | undefined => state().history[id];
export function savePosition(id: string, t: number, d: number) {
  if (!isFinite(t) || !isFinite(d) || d <= 0) return;
  state().history[id] = { t: Math.floor(t), d: Math.floor(d), at: Date.now() };
  save();
}
export const fraction = (p?: Progress) => (p && p.d ? Math.min(p.t / p.d, 1) : 0);
export const isDone = (p?: Progress) => fraction(p) >= 0.92;
export const getLater = () => state().later;
export function toggleLater(id: string) {
  const s = state();
  s.later = s.later.includes(id) ? s.later.filter((x) => x !== id) : [id, ...s.later];
  save();
}
export const getLiked = () => state().liked;
export function toggleLiked(id: string) {
  const s = state();
  s.liked = s.liked.includes(id) ? s.liked.filter((x) => x !== id) : [id, ...s.liked];
  save();
}
