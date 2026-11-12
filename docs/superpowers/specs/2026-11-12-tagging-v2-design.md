# Tagging v2 — design

**Status:** approved by the owner in chat, 2026-11-12. Input: SPEC.md §3.4, the owner's M2 review of
`reports/tagging_sample.md` and `speakers.yaml`.

## Problems found in v1 (Sonnet subagents, prompt v1)
- 821 / 1,995 tags had confidence < 0.6; the §3.4 second pass never ran.
- News and politics clips (mostly the Omar Suleiman Personal channel) had no fitting type or topic.
- Politicians who are the *subject* of a clip were listed as speakers (Netanyahu, Lindsey Graham, ...).
- `single_speaker_hint` made Omar Suleiman the speaker of reposted news footage.
- Short clips (e.g. 64 s) typed as `lecture`.
- Tag files did not record which model produced them.

## Decisions (owner)
- New content type **`news`**.
- New topic **`contemporary.politics`** (taxonomy change approved by the owner; `palestine`,
  `islamophobia`, `social-justice` were offered and not chosen).
- Record the model in every tag file.
- Re-tag **all 1,995** videos with **Opus 5.5, medium thinking**, so all labels come from one model
  and one prompt.

## Design
- `pipeline/prompts/tag_v2.md`: v1 rules plus: speakers = people speaking; hint never applies to
  `news`; definition of `news` vs a reminder about events; under 5 min is never lecture/khutbah;
  read the description, not just the title.
- `tag.py`: `PROMPT_VERSION = "v2"` (so every v1 tag counts as stale); `news` in `ContentType`;
  `validate [model]` writes `model` (default `claude-opus-5-5`); outputs kept per version in
  `data/tag_out/<version>/` so old outputs are never re-stamped; `playlist_titles()` tolerates a
  missing `data/raw/`.
- After tagging: `validate`, `normalize`, `report`, then a speakers.yaml tidy-up (merge duplicates,
  add missing scholars, no politicians) **for the owner to review** before `rank`/`build`.

## Out of scope
Site display of `news` (e.g. a "Current events" tab) is a later frontend-design task.
