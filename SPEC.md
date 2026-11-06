# IlmTube: build spec

> Working name; rename freely. An Islamic, English-language take on Karpathy's HackerTube.
> A static, searchable library of videos pulled from a **hand-picked allowlist of YouTube channels**,
> organised by topic, speaker, series and surah. Audience: family and fellow Muslims.
> The person building this is an AI agent (Sonnet). Follow the milestones in order and don't skip the acceptance checks.

---

## 0. Principles (do not violate)

1. **The allowlist is the source of trust.** Only channels in `channels.yaml` with `status: active` are ever shown. Nothing is added automatically.
2. **AI labels; it never teaches.** LLMs are used only to *classify, tag and extract names* from existing titles and descriptions. No AI-written summaries, rulings, answers or religious content appear on the site.
3. **No runtime backend in v1.** The pipeline runs at build time. The site is static files plus browser `localStorage`. No accounts.
4. **Respect YouTube's terms.** Embed with the official player (`youtube-nocookie.com`), never download video. Always show the channel name and a link to YouTube. Refresh stored metadata at least every 30 days (the nightly job covers this) and drop videos that become private or deleted.
5. **Search must handle transliteration.** "wudu", "wudhu" and "ablution" are the same query. This matters more than anything else in the search design (see §5.2).

---

## 1. Stack

| Part | Choice |
|---|---|
| Pipeline | Python 3.12, managed with `uv`. Libraries: `httpx`, `pydantic`, `pyyaml` |
| YouTube | YouTube Data API v3 (API key, no OAuth) |
| LLM tagging | **Done by Claude Code itself, not the Anthropic API** (this cloud environment can't use a separate API key). `tag.py prepare` writes batches of ~150 untagged videos to `data/tag_queue/batch_NNN.jsonl`; Claude Code subagents (Sonnet) read a batch plus `prompts/tag_v1.md` and write `data/tags/<video_id>.json`; `tag.py validate` checks every file against the pydantic schema and taxonomy, and re-queues failures. Run several subagents in parallel. |
| Site | Vite + Preact + TypeScript; MiniSearch for client-side search |
| Hosting | GitHub Pages (or Cloudflare Pages), deployed by a GitHub Action |
| Schedule | GitHub Action runs nightly: incremental fetch, rule-based fallback tags for untagged videos (keyword match on taxonomy + surah names), rebuild, deploy. A **weekly scheduled Claude Code session** runs `fetch` → LLM tagging of new videos → `normalize` → commit, replacing the fallback tags |

Secrets: `YOUTUBE_API_KEY` only. In the cloud environment, the network proxy injects it as the `X-Goog-Api-Key` header on requests to `www.googleapis.com`, so the code should send that header from `os.environ.get("YOUTUBE_API_KEY", "proxy-injected")`. In GitHub Actions it is a repository secret. Never commit it.

## 2. Repo layout

```
channels.yaml          # allowlist (human-edited)
taxonomy.yaml          # fixed topic tree (human-edited)
synonyms.yaml          # search synonym groups (human-edited)
speakers.yaml          # canonical speakers + aliases (generated once, then human-edited)
reciters.yaml          # canonical reciters + aliases (same)
pipeline/
  resolve.py  fetch.py  clean.py  tag.py  normalize.py  rank.py  build.py  discover.py
  prompts/tag_v1.md
data/
  raw/                 # API responses cached per channel (git-ignored or committed, see §3.2)
  tags/                # LLM tag cache, keyed by video_id + prompt version
  candidates.json      # reciter/channel discovery output
site/
  src/  public/data/   # build.py writes the JSON here
.github/workflows/nightly.yml  discover.yml
```

## 3. Pipeline

### 3.0 `config.yaml` (test mode)

```yaml
max_videos_per_channel: 500   # TEST MODE: only the 500 most recent uploads per channel. Set to null for a full backfill.
include_shorts: false
```

Every stage (fetch, tag, build) must respect `max_videos_per_channel`. Raising it later must be incremental: fetch and tag only the extra videos, never redo what is cached.

### 3.1 `channels.yaml`

```yaml
- handle: "@muftimenkofficial"     # resolved from the user's "mufti menk" search link
  kind: lectures                   # lectures | recitation | mixed
  single_speaker: Mufti Ismail Menk # optional: tagger may assume this speaker
  status: active                   # active | candidate | paused
- handle: "@AMAUofficial"
  kind: lectures
  status: active
- id: UC3vHW2h22WE-pNi5WJtRIjg      # Yaqeen Institute (many speakers)
  kind: lectures
  status: active
- id: UCtm8rtofLSnaIBi3noB0INg      # Omar Suleiman Personal
  kind: lectures
  single_speaker: Omar Suleiman
  status: active
```

**`resolve.py`** calls `channels.list` (`forHandle=` or `id=`) with `part=snippet,contentDetails,statistics`. It writes the channel ID, title, thumbnail, subscriber count and **uploads playlist ID** back into a generated `data/channels.json`. It also prints each resolved channel name so a human can confirm it's the right one.

### 3.2 `fetch.py`: quota-cheap, incremental

- Get uploads with `playlistItems.list` on the uploads playlist (50 per page, **1 unit** each). On incremental runs, stop paging as soon as a known `videoId` appears.
- Enrich with `videos.list` (`part=snippet,contentDetails,statistics,status,liveStreamingDetails`, 50 IDs per call, 1 unit).
- Get series with `playlists.list` per channel, then `playlistItems.list` per playlist. This records `video → [(playlist_id, position)]`.
- **Never use `search.list`** (100 units) except in `discover.py`.
- Refresh stats for all videos weekly (cheap: about 1 unit per 50 videos). New videos are fetched nightly.
- Budget check: Mufti Menk alone has about 5,900 uploads, roughly 120 units for a full backfill. The default 10,000 units/day is plenty.
- Cache raw responses in `data/raw/<channel_id>/`. Commit `data/tags/` (expensive to rebuild); `data/raw/` can be git-ignored and cached by the Action.

### 3.3 `clean.py`: rule-based exclusion

Exclude, but record the reason in `data/excluded.json`:
- **Shorts:** duration ≤ 180s **and** `HEAD https://www.youtube.com/shorts/{id}` returns 200 (it redirects for normal videos). Keep a config flag `include_shorts: false`.
- `liveBroadcastContent` set to `upcoming` or `live`; videos that aren't public or embeddable (`status.embeddable == false`).
- Duration < 60s for non-Shorts (trailers, bumpers).
- Anything left ambiguous (e.g. "LIVE NOW", "Appeal", "Donate", "Trailer", "Announcement") goes to the tagger, which can return `not_content: true`.

### 3.4 `tag.py`: LLM classification

Input per video: title, first 1,500 characters of the description, channel name, channel `kind`, playlist titles it belongs to, and duration.
Output (strict JSON via structured output / tool schema, validated with pydantic):

```json
{
  "not_content": false,
  "content_type": "lecture",          // lecture | reminder | khutbah | qa | podcast | debate | recitation | documentary | kids | nasheed | other
  "topics": ["fiqh.salah", "seasons.ramadan"],   // 1–3 slugs, MUST exist in taxonomy.yaml
  "speakers": ["Mufti Ismail Menk"],  // people speaking, as written; [] if unknown
  "reciter": null,                    // for recitations only
  "surahs": [18],                     // surah numbers recited OR explained; [] if none
  "riwayah": null,                    // "Hafs" | "Warsh" | ... recitations only, null if not stated
  "audience": ["general"],            // general | youth | sisters | brothers | reverts | kids | parents
  "confidence": 0.86
}
```

Rules for the prompt (`prompts/tag_v1.md`):
- Never invent a speaker. If the title or description doesn't name one, return `[]`. Don't assume the channel owner is the speaker unless the channel is clearly single-speaker (pass that as a hint from `channels.yaml`).
- Surah detection must handle variants: "Al-Kahf", "Kahf", "Surah 18", "Surat al-Kahf", "سورة الكهف".
- Cache results in `data/tags/<video_id>.json` with `prompt_version`. Only re-tag when the prompt version changes or the title or description changes.
- If `confidence < 0.6`, list the video in `reports/low_confidence.md` for a second subagent pass that sees the video's neighbouring playlist titles.
- Write `reports/tagging_sample.md`: 60 random tagged videos as a table (title | topics | speakers | type | surahs) **for human spot-checking**.

### 3.5 `normalize.py`: speakers and reciters

Raw names vary ("Mufti Menk", "Mufti Ismail Menk", "Ismail ibn Musa Menk"). The first time it runs, have a Claude Code subagent cluster all distinct raw names into `speakers.yaml` / `reciters.yaml`:

```yaml
- id: ismail-menk
  name: Mufti Ismail Menk
  aliases: [Mufti Menk, Ismail ibn Musa Menk, Ismail Menk]
```

After that, the files are **human-edited and authoritative**. New, unmatched names go to `reports/unmatched_names.md`; they are never merged silently.
Reciters are entities in their own right, **not channels**: many reciters appear on aggregator channels.

### 3.6 `rank.py`

- `quality = log1p(views) − median(log1p(views))` over the same channel's videos of similar age (bucket by publish year). Add a small boost for like/view ratio. This stops large channels drowning out small ones.
- `trending = quality` with a 30-day half-life decay on age. Used only on the "New & noteworthy" shelf.
- Add a "Timeless" shelf: top `quality` per topic, any age.

### 3.7 `build.py`: site data

Writes to `site/public/data/`:
- `videos.json`: a compact array. Keys: `id, c (channel idx), t, d (desc ≤ 280 chars), p (publish date), s (seconds), v, q (quality), ty, tp [topics], sp [speaker ids], r (reciter id), su [surahs], se [[series id, ep]]`
- `channels.json`, `topics.json` (with counts), `speakers.json`, `reciters.json`, `series.json` (ordered episode lists; skip playlists with fewer than 3 videos or titled "Uploads", "Favorites" or "Shorts"), `surahs.json` (114 entries: English name, Arabic name, transliteration variants).
- `search-index.json`: a serialized MiniSearch index, loaded lazily on first search.
- Target under 1.5 MB gzipped for about 10k videos. Split by type if it's larger.

## 4. Taxonomy (`taxonomy.yaml`)

The topic tree is fixed. The LLM may only choose from it. Two levels; slugs in `parent.child` form.

- **quran**: recitation, tafsir, tajweed, hifz (memorisation), quran-stories
- **aqeedah**: tawheed, names-of-allah, the-unseen (angels, jinn), qadr, death-and-grave, day-of-judgement, jannah, jahannam, signs-of-the-hour
- **seerah-history**: prophet-muhammad, prophets (stories of the prophets), sahabah, women-of-islam, islamic-history
- **hadith**: explanations (e.g. 40 Nawawi), hadith-sciences
- **fiqh**: purification, salah, fasting, zakat-charity, hajj-umrah, halal-haram, finance-business, marriage-divorce, inheritance, funerals
- **spirituality**: dua-dhikr, heart (tazkiyah), patience-gratitude, repentance, tawakkul, sincerity, overcoming-sins
- **character-family**: akhlaq (manners), marriage-relationships, parenting, parents-rights, women, youth, brotherhood-community
- **wellbeing**: grief-loss, anxiety-stress, hope, hardship-trials
- **contemporary**: social-media, work-career, muslims-in-the-west, current-affairs, science-and-islam
- **dawah**: reverts, christianity, atheism, debates
- **seasons**: ramadan, laylat-al-qadr, eid, dhul-hijjah, muharram-ashura, jumuah
- **arabic**: language-learning

## 5. Site

### 5.1 Pages

- **Home**: a big search bar at the top, then these shelves:
  - Continue watching
  - Continue series
  - For you (from local history: weighted topic, speaker and series affinity)
  - Seasonal (see below)
  - New & noteworthy
  - Browse topics (grid)
- **Search**: results with filter chips for topic, speaker, channel, type, duration (<10m, 10–30m, 30–60m, 60m+), date (past month or year, any time) and audience. Sort by relevance, newest or top.
- **Topic**: subtopic chips, plus Timeless / Newest / Series tabs.
- **Speaker**: their videos and series; filter by topic.
- **Series**: ordered episodes, a progress bar and "resume episode N".
- **Video**: the embedded player via the IFrame API (save position every 10s for resume), title, channel, speaker and topic chips, "Watch on YouTube", and *Up next*: same series → same speaker + topic → same topic.
- **Quran section** (`/quran`):
  - **Browse by surah**: a 114-surah grid. Each surah page shows *recitations* (grouped by reciter) **and** *tafsir and lectures* about that surah. This cross-link is a key feature.
  - **Reciters**: a directory with a card per reciter (video count, surahs covered, riwayah if known).
  - **New reciters**: reciters first seen in the last 60 days, plus anything recently approved from discovery (§6).
- **Library**: Watch later, history and liked items (localStorage). **Export/import JSON** so a family can move their history between devices.

**Seasonal shelf.** Compute the Hijri date on the client with `Intl.DateTimeFormat('en-u-ca-islamic-umalqura')`:
- Rajab and Sha'ban: "Preparing for Ramadan"
- Ramadan: Ramadan, Laylat al-Qadr in the last 10 nights, fasting fiqh
- Early Shawwal: Eid
- Dhul Hijjah 1–13: Hajj and the 10 days
- Muharram: Ashura
- **Every Friday**: Surah Al-Kahf recitations and Jumu'ah reminders

### 5.2 Search (the core feature)

- MiniSearch fields and boosts: `title ×3, speaker ×2.5, reciter ×2.5, topics ×2, series ×1.5, description ×1`. Use `fuzzy: 0.2, prefix: true`.
- **Synonym expansion** from `synonyms.yaml`, applied to the query *and* to indexed text (normalise to a canonical form). Strip diacritics and apostrophes first. Seed list:
  - quran, qur'an, koran
  - salah, salat, namaz, prayer
  - wudu, wudhu, wudoo, ablution
  - dua, du'a, supplication
  - zakat, zakah
  - ramadan, ramadhan
  - seerah, sirah, life of the prophet
  - jannah, paradise, heaven
  - jahannam, hellfire, hell
  - nikah, marriage
  - tawbah, tauba, repentance
  - sabr, patience
  - akhlaq, akhlaaq, manners, character
  - hajj, haj
  - umrah, umra
  - jumuah, jummah, jumma, friday
  - kahf, al-kahf, surah 18
  - dajjal, antichrist
  - shaytan, shaitan, satan
  - jinn, djinn
  - Plus all 114 surah-name variants, generated from `surahs.json`.
- Recognise surah queries: "surah kahf", "yasin" or "surah 36" puts the surah page card at the top of the results.
- Speaker and reciter alias matching: "menk" should match Mufti Ismail Menk.

### 5.3 UX notes

- Fast and clean. Light and dark themes. Works well on a phone (most family viewing will be phone or TV).
- Show ﷺ after the Prophet's name in UI copy.
- Footer: "Videos belong to their channels. Inclusion isn't endorsement of every view. AI is used only to organise videos, never to produce religious content."

## 6. Reciter discovery (`discover.py`, weekly)

- Run 5–8 `search.list` queries (`type=video`, `relevanceLanguage=en`, ordered by date and by relevance), e.g. "quran recitation", "beautiful quran recitation", "tilawah", "surah recitation". About 800 units/week.
- Collect channels **not** in `channels.yaml`. Fetch their last 50 uploads and score them by recitation share (via the tagger), upload frequency and subscribers.
- Write `data/candidates.json` and open **one GitHub PR per week** that adds the top candidates to `channels.yaml` with `status: candidate` and a short evidence table (sample titles, subs, recitation %). **A human merges and flips the status to `active`.** Never auto-activate.

## 7. Milestones and acceptance checks

| # | Milestone | Done when |
|---|---|---|
| M1 | `resolve` + `fetch` | All 4 channels resolve and their names are printed for confirmation; video counts per channel match YouTube within ~2%; a second run is incremental (uses under 20 units) |
| M2 | `clean` + `tag` + `normalize` | `excluded.json` has reasons; every video has valid tags (taxonomy slugs only); `tagging_sample.md` generated; **stop and ask the user to review the sample and `speakers.yaml` before continuing** |
| M3 | `rank` + `build` + site core (home, search, topic, video, series, speaker) | The search test queries below all pass; Lighthouse mobile performance ≥ 90 |
| M4 | Quran section + seasonal shelf + library export/import | The surah 18 page shows both recitations and tafsir; the Friday shelf appears when the system date is mocked to a Friday |
| M5 | Nightly GitHub Action + deploy + weekly tagging session | A fresh upload on any channel appears on the live site within 24h (fallback tags), and gets LLM tags within a week |
| M6 | Discovery workflow | A dry run produces a sensible candidate PR |

**Search test queries** (the right kind of results must appear in the top 5):
`wudhu` · `koran` · `surah kahf` · `yasin` · `menk marriage` · `patience in hardship` · `ramadhan` · `stories of the prophets` · `jummah` · `dealing with grief`

## 8. Later: AI extensions (not v1)

In recommended order:
1. **Meaning-based search.** Precompute embeddings for title + description + tags at build time. Embed queries in the browser with a small model (transformers.js, ~25–35 MB, cached), or with a tiny Cloudflare Worker. Then "I feel far from Allah", "I'm anxious about my exams" or "how do I explain death to my child" find the right lectures even without keyword overlap. Blend with keyword scores.
2. **"Help me find..." box.** The user describes a need, and the AI returns *a list of videos from the library* with a one-line reason why each is relevant. It never answers the question itself.
3. **Learning paths.** Ordered playlists built from the library, e.g. "New Muslim: first 10 videos", "Understanding salah", "Pre-marriage". Generated by AI, then **reviewed by a human before publishing**.
4. **Transcript search.** Search *inside* lectures and jump to the timestamp. The highest value, but transcripts aren't in the official API for third-party videos and unofficial methods are fragile. Investigate separately.

## 9. Open items for the user

- Review `tagging_sample.md` and `speakers.yaml` at M2.
- Choose a name and domain.
- Add more channels (both lecture and recitation channels) to `channels.yaml`.
