# CLAUDE.md

## Project overview

`gardener-attribution-audit` is a **Claude Code skill**, not an application and not a dev loop. It retroactively aligns GitHub content that gardener's `tend` dispatches already posted (PR descriptions, issue bodies, PR/issue comments) with gardener's current passive-voice and Gardener-attribution requirement. It is tiered and non-destructive: recon first, edits only after the scope is confirmed, and every edit is an append of the disclosure line plus a minimal passive-voice conversion.

The repo holds one file, `gardener-attribution-audit.md`. It is installed by symlink as `~/.claude/commands/gardener-attribution-audit.md`, and the installed copy lives at `/root/local-skills/gardener-attribution-audit`. Edits on `main` reach the installed skill when that clone is pulled.

## Technology stack

- A single Markdown skill file (Claude Code slash command). No code, no build, no tests, no CI.
- At run time the skill uses the `gh` CLI, `jq`, Python's `sqlite3` module (gardener's local state db), and gardener's source (`gardener/dev_loop.py`).

## Build and test

There is nothing to build or run here. A change to the skill is checked by its own **Self-audit** section: confirm that gardener's `dev_loop.py` still defines `ATTRIBUTION_REQUIREMENT` and `ORPHAN_MARKER` with the wording the skill assumes, that the local sqlite `runs` table still has the columns the skill queries, and that the `gh search prs` / `gh api` PATCH commands still behave as described.

## Repository layout

```
gardener-attribution-audit.md   The skill: scope, steps 1-4 (preflight, recon, execute, report), self-audit
```

## Conventions

- Steps are numbered `### N — Title` sections; commands sit in fenced `bash` blocks that can be run as written.
- The skill's copies of gardener's wording are snapshots; the skill always tells the reader to re-read them live from gardener's source. Keep that rule when editing.
- Findings from real runs (false positives, edge cases) are baked into the relevant step with what was observed.

## Do / Don't

**Do:**
- Keep every editing rule non-destructive: idempotent check first, append never replace, minimal diffs, log every edit.
- Write issues and PRs on this repo in passive voice with the Claude attribution sign-off.

**Don't:**
- **This repo is public.** Don't name private repositories or private conventions documents, or mention the owner's personal matters, in this file, commits, issues or PRs. Before naming any repo, check `gh api repos/<owner>/<repo> -q .private`.
- Don't hardcode the org list; the skill derives it live from gardener's state db.
- Don't widen scope to commit messages; they are out of scope by design.
