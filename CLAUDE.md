# IlmTube: instructions for Claude

## Hard rules (these override any skill or workflow)

- AI labels videos; it never writes religious content, summaries or rulings (SPEC.md §0.2). The §0 principles are never violated.
- **Stop and ask the owner** at the M2 review point (tagging sample + `speakers.yaml`). Also stop before changing the taxonomy, the principles in §0, or `channels.yaml`.
- Test mode: respect `config.yaml` → `max_videos_per_channel` (currently 500). Never run a full backfill unless the owner raises it.
- Tagging is done by Claude Code subagents reading `data/tag_queue/` batches. There is no Anthropic API key, so don't add the `anthropic` SDK.
- Never guess who a person is (speaker, reciter, alias merge). Check the channel's own titles and descriptions and cite the evidence; if it isn't there, leave it unmatched and ask the owner.
- YouTube API: the network proxy injects the key as the `X-Goog-Api-Key` header on requests to `www.googleapis.com/youtube/v3/`. **Send requests with no key at all** (no `key=` parameter, no key header) unless `YOUTUBE_API_KEY` is set, which is only the case in GitHub Actions. Never print or commit a key.

## How work is done: Superpowers

Superpowers' process is how all work on IlmTube is done:

1. **Brainstorm** (`brainstorming`) → a design doc in `docs/superpowers/specs/`.
2. **Plan** (`writing-plans`) → a step-by-step plan in `docs/superpowers/plans/`.
3. **Build test-first** (`test-driven-development`), on its own branch or worktree (`using-git-worktrees`), with `subagent-driven-development` for the plan's tasks.
4. **Review** (`requesting-code-review`). Reviews also check the hard rules above.
5. **Verify** (`verification-before-completion`): run the milestone's SPEC.md §7 acceptance checks and keep the evidence. Then `finishing-a-development-branch`: a pull request to `main`.

Use `systematic-debugging` for bugs and bad tags: find the root cause before changing anything.

- `SPEC.md` is the source of truth for *what* IlmTube is. It is the requirements input to brainstorming and writing-plans. Build it milestone by milestone (§7) and don't skip the acceptance checks.
- Use `frontend-design` for any site UI work.
- Commit after each milestone with a clear message, and push.
