# Evening Lamp Redesign + Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle every page of the IlmTube site in the approved dark-only "Evening lamp" look and add a Library page (Watch later + History).

**Architecture:** Restyle in place: a new token-based `site/src/styles.css`, small markup changes in the existing Preact components and pages, two new pure modules (`resume.ts`, history-list functions in `store.ts`) with unit tests, and a new `library.tsx` page. Fonts are bundled via `@fontsource`.

**Tech Stack:** Vite 5 + Preact 10 + TypeScript 5 (existing), Vitest 2.1 (new, dev), `@fontsource/literata`, `@fontsource/figtree`, `@fontsource/amiri`.

**Spec:** `docs/superpowers/specs/2026-11-12-evening-lamp-redesign-design.md` (approved). Mockup: https://claude.ai/artifact/MV1n5M2nnxFnthSYThWbvN (version 5, "Deepest navy").

## Global Constraints

- Dark only. No light theme, no theme toggle, no `data-theme` handling, no `prefers-color-scheme` light block.
- Colours (exact): midnight `#060a1b` (page), dusk `#0f1531` (panels), lines `#1f274d`, lamplight `#f2b45a` (primary action/progress/selected), ember `#e07a4f` (secondary, sparingly), moon cream `#f4ead8` (text), mist `#a3a9c8` (secondary text). Text on lamplight: `#2a1c08`.
- Type: Literata weight 500 for headings (modest sizes), Figtree 400/500/600 for text and UI, Amiri 700 for Arabic. Bundled via `@fontsource` with Latin subsets for Literata/Figtree and the Arabic subset for Amiri only. No Google Fonts requests.
- The lamp glow (`radial-gradient` of lamplight at ~0.32 alpha over dusk) appears only on the Home lamp panel and behind the Watch page player.
- Video cards: no box, border or shadow. Dusk panels only for grouping elements (lamp panel, search box, surah card, filter bar). Radius: lamp panel 18px, panels 12–14px, thumbnails 10px, chips 999px.
- No motion on page load; respect `prefers-reduced-motion`. Visible 2px lamplight focus outline on every interactive element.
- UI copy: plain, sentence case, no AI-written religious content (§0.2). Footer text unchanged.
- Stored data key stays `ilmtube:v1`; old stored data must keep working.
- Stack unchanged (no CSS framework). `npm run build` must pass (it runs `tsc --noEmit`).
- Hard rules in CLAUDE.md apply. UI work follows the `frontend-design` skill in full.

## Review Focus

1. **Old or broken stored data.** A visitor whose `localStorage` has `ilmtube:v1` without the new `hidden` field, or unparseable JSON, or storage blocked entirely, must get a working site: everything visible, empty states shown, no crash. Tested in Task 1.
2. **A hidden video watched again** must reappear in History (its `at` is newer than when it was hidden). Tested in Task 1.
3. **Saved ids that are no longer in the library** (removed from `videos.json`, or a Short) in Watch later or History must be skipped, not crash the Library or the lamp panel. Lamp panel: unit test in Task 2. Library: Task 7's seeded storage includes a stale id `zzzzzzzzzzz` in both lists and the script asserts the page renders with no console errors.
4. **The lamp panel when the latest watched video is finished and has no next episode** (last episode, or not in a series) must fall back to the most recent unfinished video, then to the no-history state. Tested in Task 2.
5. **Long titles at phone width (400px)** in the lamp panel, cards and Library must wrap or clamp without horizontal page scroll. Checked in Task 7's screenshot script (asserts no horizontal overflow).

---

### Task 1: Test setup and history-list store functions

**Files:**
- Modify: `site/package.json` (devDependency `vitest@2.1.9`, script `"test": "vitest run"`)
- Modify: `site/src/lib/store.ts`
- Create: `site/src/lib/store.test.ts`

**Interfaces:**
- Produces (in `store.ts`):
  - `interface State { history: Record<string, Progress>; later: string[]; liked: string[]; hidden: Record<string, number> }` (`hidden[id]` = time it was hidden, ms)
  - `historyList(): [string, Progress][]` — entries not hidden (or hidden earlier than their `at`), newest `at` first
  - `hideFromHistory(id: string): void`
  - `clearHistoryList(): void` — hides every current entry
  - `removeLater(id: string): void`
  - existing exports unchanged (`getHistory`, `getProgress`, `savePosition`, `fraction`, `isDone`, `getLater`, `toggleLater`, `getLiked`, `toggleLiked`)

- [ ] **Step 1: Install Vitest and add the test script**

Run: `cd site && npm install -D vitest@2.1.9` and add `"test": "vitest run"` to `scripts`.
Expected: `npx vitest --version` prints `2.1.9`.

- [ ] **Step 2: Write the failing tests**

`store.test.ts` stubs `globalThis.localStorage` with a Map-backed object before each test and re-imports the module with `vi.resetModules()` (the store caches state per module). Tests:

```ts
test("old stored data without hidden still lists history", async () => {
  ls.setItem("ilmtube:v1", JSON.stringify({ history: { a: { t: 10, d: 100, at: 1 } }, later: [], liked: [] }));
  const s = await load();
  expect(s.historyList().map(([id]) => id)).toEqual(["a"]);
});
test("unparseable stored data falls back to empty", async () => {
  ls.setItem("ilmtube:v1", "{not json");
  const s = await load();
  expect(s.historyList()).toEqual([]);
});
test("blocked storage (getItem throws) does not crash", async () => {
  ls.getItem = () => { throw new Error("blocked"); };
  const s = await load();
  expect(s.historyList()).toEqual([]);
});
test("historyList is newest first", ...)            // at: 1, 3, 2 -> ids ordered 3,2,1
test("hideFromHistory removes it from the list but keeps progress", ...)
  // after hide: historyList() lacks id; getProgress(id) still { t, d }
test("a hidden video watched again reappears", ...)
  // hide at Date.now()=1000 (vi.setSystemTime), then savePosition at 2000 -> listed again
test("clearHistoryList hides everything but keeps resume points", ...)
test("removeLater removes only that id", ...)        // later ["a","b","c"] -> remove "b" -> ["a","c"]
test("hidden state persists to localStorage", ...)   // hide, re-import module, still hidden
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd site && npm test`
Expected: FAIL (`historyList is not a function`, etc.).

- [ ] **Step 4: Implement the functions in `store.ts`**

Add `hidden: {}` to the default state; `load()` must merge defaults so a missing `hidden` is `{}`. Visibility rule: an entry is listed when `!(id in hidden) || hidden[id] < history[id].at`. `hideFromHistory` sets `hidden[id] = Date.now()` and saves.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd site && npm test`
Expected: all store tests PASS.

- [ ] **Step 6: Commit**

```bash
git add site/package.json site/package-lock.json site/src/lib/store.ts site/src/lib/store.test.ts
git commit -m "site: history list hide/clear and removeLater in store, with Vitest tests"
```

### Task 2: Resume picker for the lamp panel

**Files:**
- Create: `site/src/lib/resume.ts`
- Create: `site/src/lib/resume.test.ts`

**Interfaces:**
- Consumes: `Progress`, `isDone` from `store.ts`; `Video`, `Series` from `data.ts`
- Produces:
  ```ts
  export type ResumePick =
    | { kind: "resume"; v: Video; t: number }            // continue this video at t seconds
    | { kind: "next"; v: Video; series: number; ep: number }; // start episode ep (1-based) of series index
  export function pickResume(hist: Record<string, Progress>, byId: Map<string, Video>, series: Series[]): ResumePick | null
  ```

- [ ] **Step 1: Write the failing tests** (`resume.test.ts`, plain objects, no storage)

```ts
test("no history -> null")
test("latest started & unfinished video -> resume at its t")          // t > 5 and fraction < 0.92
test("ignores entries with t <= 5")
test("latest is a finished series episode with a next one -> next")   // series.v = [a,b,c]; a done, latest -> {kind:"next", v:b, ep:2}
test("latest is the finished last episode -> falls back to most recent unfinished video")
test("latest finished, not in a series, nothing unfinished -> null")
test("ids missing from byId are skipped")                             // latest id not in byId -> uses next most recent
```

- [ ] **Step 2: Run to verify failure** — `cd site && npm test` → FAIL (module not found).

- [ ] **Step 3: Implement `pickResume` in `resume.ts`**

Consider entries newest `at` first, skipping ids not in `byId`. If the newest is done and `v.se?.[0]` gives a series whose next episode (by `series[i].v` order) exists in `byId` and is not done, return `next`. Otherwise return the newest entry with `t > 5 && !isDone`, else `null`.

- [ ] **Step 4: Run to verify pass** — `cd site && npm test` → all PASS.

- [ ] **Step 5: Commit** — `git commit -m "site: pickResume for the Home lamp panel, with tests"`

### Task 3: Design tokens, bundled fonts, global styles and site chrome

**Files:**
- Modify: `site/package.json` (dependencies `@fontsource/literata`, `@fontsource/figtree`, `@fontsource/amiri`)
- Modify: `site/src/main.tsx` (font CSS imports)
- Rewrite: `site/src/styles.css` (tokens + base + header/footer/cards/chips/shelves/grid/tabs/filters; page-specific blocks are added by later tasks)
- Modify: `site/src/components.tsx` (`Header`, `Footer`, `VideoCard`, `Chip`)
- Modify: `site/index.html` (`theme-color` `#060a1b`; favicon: midnight square, lamplight play triangle)

**Interfaces:**
- Produces CSS custom properties on `:root`: `--midnight --dusk --line --lamp --ember --moon --mist --on-lamp --head --text --arabic --glow` (`--glow` = the lamp radial-gradient). Later tasks use only these.
- `Header({ q, home }: { q: string; home?: boolean })` — `home` hides the header search field.

- [ ] **Step 1: Install fonts** — `cd site && npm install @fontsource/literata @fontsource/figtree @fontsource/amiri`

- [ ] **Step 2: Import only the needed files in `main.tsx`**

`@fontsource/literata/latin-500.css`, `@fontsource/figtree/latin-400.css`, `latin-500.css`, `latin-600.css`, `@fontsource/amiri/arabic-700.css`. Verify each path exists in `node_modules` before importing.

- [ ] **Step 3: Write the design plan as the top of `styles.css`** (frontend-design step 1): token block with the Global Constraints values, plus a comment on layout and the one bold element. Then review it against the skill's generic-default list and note the review in the comment.

- [ ] **Step 4: Rewrite base and shared component styles** using only the tokens. Remove all `data-theme` and light-scheme rules; `color-scheme: dark` on `:root`. Cards: no box; thumbnail radius 10px; title 2-line clamp; meta in mist.

- [ ] **Step 5: Update components**

`Header`: remove the theme state, toggle button and `ilmtube:theme` storage; logo `Ilm` + `<span>Tube</span>` (no ▶ mark); nav: Topics, Shorts, Library (`#/library`); omit the search form when `home`. `VideoCard`: line 1 = speaker names, or the channel name if none; line 2 = `{views(v.v)}`, then `{ago(v.p)}` in its own `<span>` separated by spacing (CSS gap), not a `·` character. `Chip`: unchanged API.

- [ ] **Step 6: Verify** — `cd site && npm run build` → succeeds; `npm test` → PASS; `npm run test:search` → runs.

- [ ] **Step 7: Commit** — `git commit -m "site: Evening lamp tokens, bundled fonts, header/footer/cards"`

### Task 4: Home lamp panel

**Files:**
- Modify: `site/src/pages.tsx` (`Home`)
- Modify: `site/src/app.tsx` (pass `home` to `Header` on `/`)
- Modify: `site/src/styles.css` (`.lamp` block)

**Interfaces:**
- Consumes: `pickResume`, `ResumePick` (Task 2); `getHistory`, `dur` (existing)

- [ ] **Step 1: Replace the hero with the lamp panel**

`const pick = pickResume(getHistory(), d.byId, d.series)`.
- `pick.kind === "resume"`: `<h1>Carry on with “{v.t}”</h1>`, a line with the series name and episode if `v.se` else the speaker names, and a lamplight button `Resume at {dur(t)}` linking to `#/watch/{id}`. A dusk search form follows directly under the panel.
- `pick.kind === "next"`: `<h1>Start episode {ep} of “{series.t}”</h1>`, line with `v.t`, button `Start episode {ep}`.
- `null`: panel holds `<h1>Search lectures, speakers and surahs</h1>` and the search form (placeholder `Try “wudhu” or “surah kahf”`).
- Continue watching shelf excludes `pick.v.id`. All other shelves unchanged in order.

- [ ] **Step 2: Style `.lamp`** — dusk background + `--glow`, radius 18px, padding 16–24px; title Literata 500; no load animation.

- [ ] **Step 3: Verify** — `npm run build` → succeeds; run `npm run dev`, open `#/` with `localStorage` empty and with a seeded history (one unfinished; one finished episode with a next one) and check the three panel states render.

- [ ] **Step 4: Commit** — `git commit -m "site: Home lamp panel (resume / next episode / search)"`

### Task 5: Library page

**Files:**
- Create: `site/src/library.tsx` (`export function Library()`)
- Modify: `site/src/app.tsx` (route `library`)
- Modify: `site/src/styles.css` (`.library` block)

**Interfaces:**
- Consumes: `historyList`, `hideFromHistory`, `clearHistoryList`, `getLater`, `removeLater`, `fraction`, `isDone` (Task 1); `VideoCard` (Task 3)

- [ ] **Step 1: Build the page**

Heading `Library`; under it `Saved on this device only. Nothing to sign in to.`
Section `Watch later`: `getLater()` ids present in `d.byId`, in stored order (newest first); each card with a `Remove` button (`removeLater`). Empty: `Save videos to watch later from any video page.` + link `Browse topics` → `#/topics`.
Section `History`: `historyList()` ids present in `d.byId`; under each card `Watched {ago(new Date(at))}` or, if `isDone`, `Watched`; `Remove` (`hideFromHistory`). Section action `Clear history`: first click turns it into `Yes, clear the list` + `Cancel` with the text `Clear your watch history list? Where you stopped in each video is kept.`; confirm calls `clearHistoryList()`. Empty: `Videos you watch will appear here.` + `Browse topics`.
Re-render after each action (local `useState` counter).

- [ ] **Step 2: Style** — grid of cards; Remove as a small text button in mist with focus ring; confirm row in a dusk panel.

- [ ] **Step 3: Verify** — `npm run build`; dev server with seeded storage: remove, clear+cancel, clear+confirm, then watch a hidden video's position change (via `savePosition` in console) and see it reappear.

- [ ] **Step 4: Commit** — `git commit -m "site: Library page (watch later, history with hide/clear)"`

### Task 6: Watch, Search, Topics, Topic, Speaker, Series, Shorts

**Files:**
- Modify: `site/src/pages.tsx` (`Watch`, `Search`, `Topics`, `Topic`, `Speaker`, `SeriesPage` markup only where the design needs it)
- Modify: `site/src/shorts.tsx` (class names only if needed)
- Modify: `site/src/styles.css` (page blocks)

- [ ] **Step 1: Watch** — `--glow` behind the player block; meta line without `·` chains (channel, then views and date on separate spans); Watch later button: lamplight outline, `Watch later` / `Saved to watch later`; remove the 🎙 emoji from speaker chips.
- [ ] **Step 2: Search** — filter bar as a dusk panel; selected filters/chips lamplight; surah card in dusk with the Arabic name in Amiri 700 lamplight.
- [ ] **Step 3: Topics / Topic / Speaker / Series** — tiles as dusk panels (grouping), tabs with lamplight underline, series progress bar lamplight; `Resume episode N` copy unchanged.
- [ ] **Step 4: Shorts** — keep the black stage; top bar, chips, info and badges in Figtree; selected chip lamplight with `--on-lamp` text.
- [ ] **Step 5: Verify** — `npm run build`; `npm test`; `npm run test:search`.
- [ ] **Step 6: Commit** — `git commit -m "site: Evening lamp across watch, search, topics, speaker, series, shorts"`

### Task 7: Screenshot critique, Lighthouse, SPEC update

**Files:**
- Create: `site/scripts/screens.mjs`
- Modify: `SPEC.md` (§5.1 Library, §5.3 themes, §7 M4 row)
- Modify: this plan (evidence section)

- [ ] **Step 1: Screenshot script** — Playwright (preinstalled), against `npx vite preview`; for each route `#/`, `#/search?q=wudhu`, `#/topics`, a topic, a speaker, a series, a watch page, `#/library` (empty, and seeded with history incl. one finished and one hidden entry, watch later, and the stale id `zzzzzzzzzzz` in both lists), `#/shorts`, at 400px and 1280px, `deviceScaleFactor: 1`. Assert `document.documentElement.scrollWidth <= innerWidth` and no `console.error`/`pageerror` on every page; exit non-zero otherwise. Save PNGs to `/tmp` (not committed).
- [ ] **Step 2: Critique** — review every screenshot against the spec and the frontend-design generic-default list; one fix pass; re-run the script.
- [ ] **Step 3: Lighthouse** — `npx lighthouse <preview url>/#/ --only-categories=performance --form-factor=mobile --chrome-flags="--headless --no-sandbox"` with `CHROME_PATH=/opt/pw-browsers/chromium`, for `#/` and a watch page. Expected: performance ≥ 90 on both.
- [ ] **Step 4: Keyboard** — tab through Home, Watch and Library in the screenshot script; assert each focused element has a non-`none` outline.
- [ ] **Step 5: SPEC.md** — §5.1 Library: "Watch later and history, saved on this device (localStorage). No accounts, no export/import." §5.3: "Dark only (Evening lamp)." §7 M4: remove "library export/import".
- [ ] **Step 6: Record evidence** in this plan (scores, overflow result, test counts), then commit — `git commit -m "site: screenshot checks, Lighthouse evidence, SPEC updated for dark-only and Library"`
