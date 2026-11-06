import MiniSearch from "minisearch";
import { normalizeText, buildSynonyms, canonicalize } from "./normalize.js";

export const FIELDS = ["title", "speaker", "reciter", "topics", "series", "description", "surah"];
export const BOOST = { title: 3, speaker: 2.5, reciter: 2.5, topics: 2, series: 1.5, description: 1, surah: 2 };
const STOP = new Set("a an the of in on at to for with and or is are was how what why do does your you i we it its my me this that from by as be about into".split(" "));

function stem(w) {
  if (w.length > 4 && w.endsWith("ies")) return w.slice(0, -3) + "y";
  if (w.length > 3 && w.endsWith("s") && !w.endsWith("ss") && !w.endsWith("us")) return w.slice(0, -1);
  return w;
}
export function processTerm(term) {
  const t = term.toLowerCase();
  return STOP.has(t) ? null : stem(t);
}
export const indexOptions = { fields: FIELDS, idField: "id", processTerm };
export const searchOptions = { boost: BOOST, fuzzy: 0.2, prefix: true, combineWith: "OR" };

// Bare surah names that are also ordinary words/people: only treated as a surah when written "surah X".
const AMBIGUOUS = new Set("muhammad ibrahim yusuf maryam nuh hud yunus luqman saba fatir nas fil asr qadr fath nasr sad qaf jinn feel".split(" "));

export function loadIndex(json) {
  return MiniSearch.loadJSON(json, indexOptions);
}

export function makeSearcher(index, videos, surahs, synonymGroups) {
  const syn = buildSynonyms(synonymGroups);
  const byId = new Map(videos.map((v) => [v.id, v]));
  const surahOf = new Map();
  for (const s of surahs) for (const v of s.v) surahOf.set(normalizeText(v), s.n);

  function detectSurah(q) {
    const nq = normalizeText(q);
    const m = nq.match(/^(?:surah|surat|sura|chapter)\s+(.+)$/);
    const bare = m ? m[1] : nq;
    const n = surahOf.get(bare) ?? surahOf.get(nq);
    if (n == null) return null;
    if (!m && AMBIGUOUS.has(bare)) return null;
    if (!m && /^\d+$/.test(bare)) return null;
    return { n, rest: m ? m[1] : nq };
  }

  return function search(q) {
    const det = detectSurah(q);
    const out = new Map();
    if (det) {
      // Surah query: exact-term text match on the surah's name (no fuzzy/prefix, speakers ignored), plus every video tagged with that surah.
      const s = surahs[det.n - 1];
      const bare = normalizeText(s.en).replace(/^(al|an|ar|as|at|az|ad|ash|adh|aal) /, "").replace(/ /g, "");
      const extra = /^[a-z]+$/.test(det.rest) ? det.rest : "";
      const term = [...new Set([bare, extra])].filter(Boolean).join(" ");
      const cq = canonicalize(term, syn);
      const opts = { boost: { ...BOOST, speaker: 0, reciter: 0 }, fuzzy: false, prefix: false, combineWith: "OR" };
      for (const h of index.search(cq, opts)) out.set(h.id, h.score);
      for (const v of videos) if (v.su.includes(det.n)) out.set(v.id, (out.get(v.id) ?? 0) + 1000);
    } else {
      for (const h of index.search(canonicalize(q, syn), searchOptions)) out.set(h.id, h.score);
    }
    const hits = [...out].map(([id, score]) => ({ id, score })).sort((a, b) => b.score - a.score);
    return { surah: det ? surahs[det.n - 1] : null, hits, byId };
  };
}
