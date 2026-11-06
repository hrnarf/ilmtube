# IlmTube: instructions for Claude

- `SPEC.md` is the source of truth. Build it milestone by milestone (§7) and don't skip the acceptance checks.
- **Stop and ask the owner** at the M2 review point (tagging sample + `speakers.yaml`). Also stop before changing the taxonomy, the principles in §0, or `channels.yaml`.
- Test mode: respect `config.yaml` → `max_videos_per_channel` (currently 500). Never run a full backfill unless the owner raises it.
- Tagging is done by Claude Code subagents reading `data/tag_queue/` batches. There is no Anthropic API key, so don't add the `anthropic` SDK.
- YouTube API: the network proxy injects the key as `X-Goog-Api-Key` for `www.googleapis.com`. The code reads `YOUTUBE_API_KEY` if it's set, otherwise it sends a placeholder header value. Never print or commit a key.
- Commit after each milestone with a clear message, and push.
- AI labels videos; it never writes religious content, summaries or rulings (§0.2).
