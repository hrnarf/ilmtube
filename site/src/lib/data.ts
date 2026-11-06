export interface Video {
  id: string; c: number; t: string; p: string; s: number; v: number; q: number; ty: string;
  tp: string[]; sp: string[]; r?: string; su: number[]; au: string[]; cf: number; se?: [number, number][]; tr?: number;
}
export interface Channel { i: number; id: string; t: string; handle: string; thumb: string; subs: number; n: number; ns: number }
export interface TopicParent { id: string; name: string; n: number; children: { id: string; name: string; n: number }[] }
export interface Entity { id: string; name: string; aliases: string[]; n: number; ns: number; tp: string[]; su: number[] }
export interface Series { id: string; t: string; c: number; v: string[] }
export interface Surah { n: number; en: string; ar: string; v: string[]; count: number }
export interface Data {
  videos: Video[]; channels: Channel[]; topics: TopicParent[]; speakers: Entity[]; reciters: Entity[];
  series: Series[]; surahs: Surah[]; shelves: { noteworthy: string[]; timeless: Record<string, string[]> }; synonyms: string[][];
  byId: Map<string, Video>; shortCount: number; topicName: Map<string, string>; speakerById: Map<string, Entity>;
}

const url = (f: string) => new URL(`data/${f}`, document.baseURI).toString();
const get = async <T,>(f: string): Promise<T> => {
  const r = await fetch(url(f));
  if (!r.ok) throw new Error(`${f}: ${r.status}`);
  return r.json();
};

export async function loadData(): Promise<Data> {
  const [videos, channels, topics, speakers, reciters, series, surahs, shelves, synonyms] = await Promise.all([
    get<Video[]>("videos.json"), get<Channel[]>("channels.json"), get<TopicParent[]>("topics.json"),
    get<Entity[]>("speakers.json"), get<Entity[]>("reciters.json"), get<Series[]>("series.json"), get<Surah[]>("surahs.json"),
    get<Data["shelves"]>("shelves.json"), get<string[][]>("synonyms.json"),
  ]);
  const topicName = new Map<string, string>();
  for (const p of topics) { topicName.set(p.id, p.name); for (const c of p.children) topicName.set(c.id, c.name); }
  return {
    videos, channels, topics, speakers, reciters, series, surahs, shelves, synonyms,
    byId: new Map(videos.map((v) => [v.id, v])), shortCount: channels.reduce((n, c) => n + c.ns, 0), topicName, speakerById: new Map(speakers.map((s) => [s.id, s])),
  };
}

export const fetchIndex = () => fetch(url("search-index.json")).then((r) => r.text());

let shortsP: Promise<Video[]> | null = null;
export const loadShorts = () => (shortsP ??= get<Video[]>("shorts.json"));
let descP: Promise<Record<string, string>> | null = null;
export const loadDescs = () => (descP ??= get<Record<string, string>>("desc.json"));
