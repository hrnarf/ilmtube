import type MiniSearch from "minisearch";
import type { Surah, Video } from "./data";

export function loadIndex(json: string): MiniSearch;
export function makeSearcher(
  index: MiniSearch, videos: Video[], surahs: Surah[], synonymGroups: string[][],
): (q: string) => { surah: Surah | null; hits: { id: string; score: number }[]; byId: Map<string, Video> };
export const indexOptions: object;
export const searchOptions: object;
export const BOOST: Record<string, number>;
export const FIELDS: string[];
