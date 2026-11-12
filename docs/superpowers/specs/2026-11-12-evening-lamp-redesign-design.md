# Evening lamp redesign + Library page: design

**Status:** draft for owner approval, 2026-11-12. Requirements input: SPEC.md §5 (site), the owner's
choices in chat, and the approved mockups at https://claude.ai/artifact/MV1n5M2nnxFnthSYThWbvN
(version 5, option "Deepest navy").

## Intent
IlmTube is a place for families and individuals to learn and watch videos about Islam. The owner wants
it to feel **warm and inviting**. The current site uses system fonts, a generic green and one rounded card
style everywhere (`site/src/styles.css`), so it reads as a template. This work gives every page one
deliberate look, "Evening lamp": the family room after Maghrib, the lamp on, someone puts on a talk.
It also adds the **Library** page so saved and watched videos can actually be found. The site already
stores them (`site/src/lib/store.ts`) but has nowhere to show them.

## Goals
- Every existing page uses the Evening lamp look: Home, Search, Topics, Topic, Speaker, Series, Watch,
  and the Shorts feed (restyled within its existing full-screen layout).
- A Library page at `#/library` with **Watch later** and **History**, linked from the top menu.
- The look is set up as reusable tokens and component styles, so the M4 Quran section uses it later
  without new design work.

## Non-goals
- No light theme (owner decision: dark only). The theme toggle in the header is removed.
- No "Liked" videos in the UI. `store.ts` keeps its `liked` data, but no button or list.
- No export/import of history (owner decision: removed). SPEC §5.1 is updated to match.
- No Quran section, seasonal shelf or About page in this work (later milestones).
- No changes to the pipeline, the data files or search behaviour.

## Anti-goals (a failure even if it works)
- It looks like a generic dark template: near-black with one neon accent, or identical rounded cards
  with the same shadow everywhere.
- Mosque silhouettes, crescent icons or other clichés stand in for meaning.
- Lighthouse mobile performance drops below 90 (SPEC §7 M3 check), e.g. from heavy fonts or images.
- Any AI-written religious text appears in UI copy (§0.2). UI copy is plain interface wording only.

## Constraints
- Stack stays Vite + Preact + TypeScript (SPEC §1). No CSS framework.
- Static site on GitHub Pages; no backend; per-device state in `localStorage` only (SPEC §0.3).
- Fonts are **bundled with the site** (self-hosted, Latin + Arabic subsets only), not loaded from
  Google Fonts, so visitors' browsers never contact Google and pages load faster.
- Hard rules in CLAUDE.md apply; UI work follows the `frontend-design` skill in full (plan, review
  against generic defaults, build, screenshot critique).

## Approaches considered
1. **Restyle the existing site in place** (chosen by the owner). Replace `styles.css` with the new token
   system and component styles, adjust markup in `components.tsx` / `pages.tsx` / `shorts.tsx` where
   the design needs it, add a Library page. Least risk: search, history, resume and player code stay.
2. Adopt Tailwind. Rewrites every page's markup for the same result. Rejected: churn without benefit.
3. Rebuild components from scratch. Cleanest, but risks working features (resume, search) for no
   visible gain. Rejected.

## Design decisions (owner)
- **Direction:** Evening lamp, dark only.
- **Colour:** background "midnight" `#060a1b`; panels "dusk" `#0f1531`; lines `#1f274d`;
  lamplight `#f2b45a` (primary action, progress, highlights); ember `#e07a4f` (secondary accent,
  sparingly); moon cream `#f4ead8` (main text); mist `#a3a9c8` (secondary text).
- **Type:** Literata for headings (weight 500, modest sizes: the "quieter serif" of option B), Figtree
  for text and UI, Amiri for Arabic (surah names; set slightly larger and bold so it balances).
- **The one bold element:** the lamp glow, a soft amber radial light, used only behind what the viewer
  is about to watch: the Home "Carry on with…" panel, and behind the player on the Watch page.
  Nowhere else.

## Design decisions (builder's calls, proposed; owner may correct)
- **Home:** the first block is the lamp panel. If there is something to resume, it says
  "Carry on with "<title>"", names the series/episode or speaker, and has "Resume at mm:ss". With no
  history yet, the panel holds the search box and the line "Search lectures, speakers and surahs"
  instead. Shelves follow as today (Continue series, For you, New & noteworthy, Browse topics).
- **Header:** logo "Ilm" in moon cream + "Tube" in lamplight (Literata); menu: Topics, Shorts, Library;
  the search field stays in the header on every page except Home's first panel.
- **Cards:** thumbnail with rounded corners and duration badge, then title and speaker as plain text
  on the page background, no card box, border or shadow. Panels (dusk) are reserved for things that
  group content: the lamp panel, the search box, the surah row, filter bars.
- **Radius hierarchy:** lamp panel 18px, panels 12–14px, thumbnails 10px, chips fully round.
- **Progress:** a thin lamplight bar along the bottom of a thumbnail, as now.
- **Chips:** outlined (lines colour), selected chip filled with lamplight and dark text.
- **Focus:** a visible 2px lamplight outline on every interactive element.
- **Motion:** none on load. Only responses to the viewer's actions (e.g. a chip toggling). Respect
  `prefers-reduced-motion`.
- **Shorts:** keeps its black full-screen stage (video needs black), but its top bar, chips, info panel
  and badges use the new fonts and colours; the selected chip uses lamplight.
- **Browser chrome:** `theme-color` meta and favicon use midnight and lamplight.

## Library page (`#/library`)
- **Two sections on one page, Watch later first, then History.** Both use the standard video
  cards in a grid.
- **Watch later:** newest saved first. Each card has a "Remove" control. The Watch page's existing
  "Watch later" button stays (restyled) and is how items are added.
- **History:** most recently watched first, using `Progress.at`. Each card shows the progress bar and
  "Watched <ago>". Each card has a "Remove" control; the section has "Clear history", which asks for
  confirmation inside the page (two-step button, no browser dialog) before deleting.
- **Finished videos** (≥ 92%, `isDone`) stay in History and show "Watched" instead of a resume point.
- **Shorts** do not appear in History (they are not saved there today) or Watch later.
- **Empty states:** Watch later empty: "Save videos to watch later from any video page." History empty:
  "Videos you watch will appear here." Each links to Topics.
- **Privacy line** under the heading: "Saved on this device only. Nothing to sign in to."
- `store.ts` needs: `removeFromHistory(id)`, `clearHistory()`, and `removeLater(id)` (or reuse
  `toggleLater`). Tests cover these.

## Testing and verification
- Unit tests (Vitest, added as a dev dependency) for the new `store.ts` functions and the Library's
  ordering/finished logic, written first.
- `npm run build` (includes `tsc --noEmit`) passes; `npm run test:search` still passes.
- Screenshots of every page at phone (400px) and desktop widths, critiqued against this design and the
  skill's generic-default list, with one fix pass.
- Lighthouse mobile performance ≥ 90 on Home and Watch, recorded as evidence.
- Keyboard: every control reachable with a visible focus ring.

## SPEC.md changes (part of this work)
- §5.1 Library: remove "Export/import JSON"; Library = Watch later + History.
- §5.3 UX notes: "Light and dark themes" becomes "Dark only (Evening lamp)".

## Left to the builder
Exact type scale and spacing values; how to subset and bundle the fonts (e.g. `@fontsource` packages);
icon glyphs for Remove/Resume; the exact wording of small UI labels within the voice above (plain,
sentence case).
