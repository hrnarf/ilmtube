// Builds public/data/search-index.json (serialized MiniSearch) from the JSON written by pipeline/build.py.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import MiniSearch from "minisearch";
import { buildSynonyms, canonicalize } from "../src/lib/normalize.js";
import { indexOptions } from "../src/lib/searchcore.js";

const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "public", "data");
const rd = (f) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"));
const desc = rd("desc.json"), videos = rd("videos.json"), speakers = rd("speakers.json"), reciters = rd("reciters.json");
const series = rd("series.json"), topics = rd("topics.json"), surahs = rd("surahs.json"), syn = buildSynonyms(rd("synonyms.json"));

const spById = new Map(speakers.map((s) => [s.id, s]));
const reById = new Map(reciters.map((s) => [s.id, s]));
const topicName = new Map();
for (const p of topics) { topicName.set(p.id, p.name); for (const c of p.children) topicName.set(c.id, `${p.name} ${c.name}`); }
const c = (s) => canonicalize(s, syn);

const index = new MiniSearch(indexOptions);
index.addAll(videos.map((v) => ({
  id: v.id,
  title: c(v.t),
  speaker: c(v.sp.map((id) => [spById.get(id)?.name, ...(spById.get(id)?.aliases ?? [])].join(" ")).join(" ")),
  reciter: c(v.r ? [reById.get(v.r)?.name, ...(reById.get(v.r)?.aliases ?? [])].join(" ") : ""),
  topics: c(v.tp.map((t) => topicName.get(t) ?? t).join(" ")),
  series: c((v.se ?? []).map(([i]) => series[i]?.t).join(" ")),
  description: c(desc[v.id] ?? ""),
  surah: c(v.su.map((n) => [surahs[n - 1].en, ...surahs[n - 1].v].join(" ")).join(" ")),
})));
const json = JSON.stringify(index);
fs.writeFileSync(path.join(dir, "search-index.json"), json);
console.log(`search-index.json: ${(json.length / 1024).toFixed(0)} KB raw, ${videos.length} docs`);
