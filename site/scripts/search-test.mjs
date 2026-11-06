// Runs the SPEC §7 search test queries against the built index and prints the top 5 for human/automatic checking.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadIndex, makeSearcher } from "../src/lib/searchcore.js";

const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "public", "data");
const rd = (f) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"));
const videos = rd("videos.json"), surahs = rd("surahs.json"), speakers = rd("speakers.json");
const index = loadIndex(fs.readFileSync(path.join(dir, "search-index.json"), "utf8"));
const search = makeSearcher(index, videos, surahs, rd("synonyms.json"));

const queries = process.argv.slice(2).length ? process.argv.slice(2) :
  ["wudhu", "koran", "surah kahf", "yasin", "menk marriage", "patience in hardship", "ramadhan", "stories of the prophets", "jummah", "dealing with grief"];
const spName = new Map(speakers.map((s) => [s.id, s.name]));
for (const q of queries) {
  const r = search(q);
  console.log(`\n## ${q}  (${r.hits.length} hits)${r.surah ? `  [surah card: ${r.surah.n} ${r.surah.en}]` : ""}`);
  for (const h of r.hits.slice(0, 5)) {
    const v = r.byId.get(h.id);
    console.log(`  ${h.score.toFixed(1).padStart(7)}  ${v.t.slice(0, 70).padEnd(70)} | ${v.tp.join(",")} | ${v.sp.map((s) => spName.get(s)).join(",")} | su=${v.su}`);
  }
}
