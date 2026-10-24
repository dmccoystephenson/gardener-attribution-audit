# gardener-attribution-audit

Retroactively aligns GitHub content gardener has already posted (PR descriptions, issue bodies, PR/issue review comments) with its current passive-voice + Gardener-attribution requirement, for content that predates that requirement or a later change to its wording.

---

## The hard truth this skill is built around

gardener (the CLI at `/root/gardener`) dispatches Claude Code against a fleet of repos under `tend`. Every `tend` dispatch is told, via `dev_loop.ATTRIBUTION_REQUIREMENT` in `/root/gardener/gardener/dev_loop.py`, to write PR descriptions, issue bodies, and PR/issue comments in passive voice with a disclosure line linking gardener's own repo. That requirement only binds *future* dispatches — it says nothing about content gardener already wrote before the requirement existed, or before its wording last changed. This skill's job is to bring that backlog into line.

**Always re-read `dev_loop.ATTRIBUTION_REQUIREMENT` and `dev_loop.ORPHAN_MARKER` live from `/root/gardener/gardener/dev_loop.py` before running** — this skill's copies below are a snapshot from when it was written, not the source of truth. If the wording has changed, use the current wording, not this file's.

Unlike generic Claude-authored content (see the sibling skill `~/local-skills/claude-attribution-audit/claude-attribution-audit.md`, which this skill borrows its tiered/non-destructive discipline from), gardener's PRs carry a **reliable machine marker** — `<!-- gardener-tend-dispatch -->` (`dev_loop.ORPHAN_MARKER`) — embedded in every PR body it opens. That makes PR detection precise rather than heuristic. Issues and comments have no such marker and stay best-effort.

**gardener may run from more than one device** (e.g. a second machine tending the same fleet). A device's local sqlite state db (`~/.local/state/gardener/gardener.sqlite3`, table `runs`) only records runs *that device* dispatched — it is not shared or synced across devices. PR detection below is device-agnostic (it searches GitHub itself, not the local db) and stays complete regardless of which device tended a given repo. Issue detection is NOT device-agnostic — it leans on the local db's `gap_summary` text, so it will silently miss issues filed by a `tend` run dispatched from a different device. Treat this as a **known, disclosed coverage gap** in every report this skill produces — never imply issue coverage is complete when it can only be as complete as the current device's own history.

## Scope

Only `tend`-dispatched content. Confirm this live each run — query the local sqlite db for historical `align --implement` / `align --file-issue` runs:

```bash
python3.11 -c "
import sqlite3
conn = sqlite3.connect('$HOME/.local/state/gardener/gardener.sqlite3')
print(conn.execute(\"select mode, count(*) from runs group by mode\").fetchall())
"
```
(the `sqlite3` CLI binary is often not installed on these boxes — use python3.11's `sqlite3` module, and confirm which `python3.x` on the box actually has a modern-enough stdlib if this fails)

If `implement`/`file-issue` runs ever show up, this skill's PR/issue-finding methodology below (built around `tend`'s marker and `gap_summary` shape) needs extending before it can cover them — don't assume they're covered as-is.

In scope: PR descriptions, issue bodies, PR/issue comments. **Out of scope: commit messages** — those follow `COMMIT_PR_CONVENTIONS.md`'s own convention (`Co-Authored-By` trailer), a separate concern gardener's `CLAUDE.md` already governs.

---

## Steps

### 1 — Preflight

```bash
gh auth status
gh api user --jq '.login'
```

Re-read `dev_loop.ATTRIBUTION_REQUIREMENT` and `dev_loop.ORPHAN_MARKER` from `/root/gardener/gardener/dev_loop.py` (or wherever gardener actually lives on this box — confirm the path) to get the *current* exact wording and marker string. Derive the canonical disclosure line to append from `ATTRIBUTION_REQUIREMENT`'s own worked example rather than hardcoding this skill's copy below.

**Canonical disclosure line shape** (re-derive from the live `ATTRIBUTION_REQUIREMENT`, this is the shape as of this skill's authoring):

```markdown

---

_This <PR description|issue body|comment> was drafted during a Gardener session ([Stephenson-Software/gardener](https://github.com/Stephenson-Software/gardener))._
```

Substitute "PR description" / "issue body" / "comment" for the noun. Append after a `---` separator, italicized. Never prepend, never replace existing content.

### 2 — Recon (read-only — no edits yet)

Fork a read-only recon pass (or run it inline if the scope looks small). It must NOT edit anything — this step only sizes the surface.

**Finding gardener's PRs (high precision, but verify — see caveat below):**

```bash
gh search prs --owner <org> --match body "gardener-tend-dispatch" --limit 1000 \
  --json number,url,title,state,repository
```

Run once per org the fleet actually spans — derive the org list live from the local db (`select distinct repo from runs where mode='tend'`, then take the part before `/`) rather than hardcoding a list; this ecosystem's known orgs (as of this skill's authoring) are `dmccoystephenson`, `Dans-Plugins`, `Preponderous-Software`, `Stephenson-Software`, but that set can grow.

**`gh search --match body` tokenizes — it is NOT exact-substring matching.** Confirmed on this skill's first real run: 15 of 112 candidates on one repo were false positives — ordinary, non-`tend` PRs that merely contained the words "gardener"/"tend"/"dispatch" as separate tokens somewhere in the body (e.g. a PR describing a change to gardener's own attribution feature). **Never treat a search hit as gardener's own PR on faith** — after fetching each candidate's body (`gh api repos/OWNER/REPO/pulls/NUM --jq .body`), grep it for the literal marker string before editing or counting it. This matters most on `gardener`'s own repo, where ordinary development PRs are far more likely to mention those words in prose.

**Finding gardener's issues (best-effort, no marker):**

Cross-reference each repo's `gap_summary` text (free-form, e.g. "1 issue closed (#46)", "2 issues filed (#62 on project repo, #4 on skill repo)") against that repo's real issue list. Verify each candidate individually (timestamp proximity to the run, does the body read like an automated gap-report vs. something a human filed) before treating it as gardener's own. **When in doubt, exclude it** — a missed issue is fine, a human's genuine issue misattributed and rewritten is not.

**Finding gardener's PR/issue comments (heuristic, highest rewrite risk):**

```bash
gh api repos/OWNER/REPO/issues/NUM/comments --jq '.[] | {id, created_at, body}'
```

Identify gardener's `gh pr comment` self-reviews by timestamp proximity to a known `tend` run and by structured/checklist-like review content. These are the likeliest place to find real first-person narration ("I re-verified...", "I confirmed...") — `build_tend_prompt`'s self-review instruction has historically produced exactly that voice, so budget real conversion effort here, not just an appended line.

**Also check for repos with real gardener-tagged PRs but no local db record at all** (a device-coverage gap, or a repo transferred between orgs whose old owner name now just redirects) — verify each such repo is genuinely gardener's own work (real `gardener-tend-dispatch` PRs, owned by the operator or one of their orgs) before including it, and use its *current* canonical owner name, not a stale redirect.

**Produce a compact recon report** before touching anything: per-org/per-repo counts (PRs found, candidate issues, candidate comments), a rough tier split (how many look append-only vs. need real passive-voice conversion, based on a small sample), any borderline/low-confidence items flagged explicitly, and a rough total `gh api` call estimate (so the user can gauge scale). **Stop here and get the user's direction** — this touches public, shared GitHub state across potentially dozens of repos; never proceed to editing without an explicit go-ahead, even though the marker-matching itself is mechanical. Ask specifically: rollout approach (pilot one group first vs. full-scale vs. narrower scope like PR-bodies-only first), and how to handle any borderline items recon surfaced.

### 3 — Execute (only once the user has confirmed scope and approach)

For fleets of any real size, parallelize as one fork per GitHub org bucket (derived live from Step 2, not hardcoded) — each fork does recon-confirmation + edits for its own bucket only, and must not touch another bucket's repos (avoids duplicate/conflicting edits when forks run concurrently, and keeps report-back scoped and legible). Each fork should end with a compact table: `repo | PRs edited | issues edited | comments edited | items skipped`, a list of anything it wasn't confident enough to touch, and confirmation it stayed inside its assigned org.

**Non-negotiable rules for every edit:**

- **Idempotent — check first.** If the item already carries the disclosure (or an equivalent one), skip it. Don't double-append.
- **Passive voice is mandatory, separately from the appended line.** A disclosure line bolted onto a body that still says "I fixed the bug" is not compliant. Scan for genuine first-person authorial narration describing gardener's own actions/reasoning — "I fixed/found/decided/re-verified...", "my analysis", "I've/I'd..." — and convert to passive/third-person ("The bug was fixed...", "Testing found...", "The review re-verified..."). **Do NOT touch:** quoted text/blockquotes, code fences, test/variable names, file/repo names that merely contain a pronoun, technical tokens like "I/O", or genuine domain content that isn't gardener narrating itself (e.g. a simulated agent's own first-person text inside a project like an artificial-consciousness simulator — that's the subject's voice, not the author's). A naive `\bI\b`-style regex also false-positives on words like "Investigation", "Independent", or "CI does" — verify every candidate sentence by eye, not by regex hit count alone.
- **Not every PR marker-matched to a gardener repo was actually authored by gardener.** Confirmed on the first real run: a PR gardener merely merged (e.g. one originally opened by GitHub Copilot's coding agent, or by a human) is not gardener's content even if it lives in a repo gardener tends — check the PR's actual author/origin, not just which repo it's in, before rewriting its body.
- **Minimal, surgical diffs.** Only the passive-voice conversion where needed, plus the appended disclosure line. Never restructure, never add claims, never touch anything else in the body.
- **Merged/closed items are still fair game.** GitHub allows editing PR/issue bodies and comments regardless of state.
- **Log every edit**: repo, item type, number, URL, and whether passive-voice conversion was needed or just the line was appended.
- **Rate limits.** Parallel workers share one `gh` auth token — back off with increasing delay on a 403/rate-limit response and retry rather than hammering it or giving up silently.

**Editing mechanics** (robust against bodies with special characters):

```bash
# read
gh api repos/OWNER/REPO/pulls/NUM   --jq .body
gh api repos/OWNER/REPO/issues/NUM  --jq .body
gh api repos/OWNER/REPO/issues/comments/CID --jq .body

# write — build the new body in a fresh per-item file first, then PATCH
BODY=$(mktemp)   # one per item, never a shared fixed path
jq -n --rawfile body "$BODY" '{body:$body}' | gh api -X PATCH "repos/OWNER/REPO/pulls/NUM"  --input -
jq -n --rawfile body "$BODY" '{body:$body}' | gh api -X PATCH "repos/OWNER/REPO/issues/NUM" --input -
jq -n --rawfile body "$BODY" '{body:$body}' | gh api -X PATCH "repos/OWNER/REPO/issues/comments/CID" --input -
```

**Never share a scratch path between edits.** Step 3's per-org forks run concurrently, so a fixed path such as `/tmp/newbody.md` lets one fork overwrite another's body between write and PATCH — the PATCH then silently replaces an item's content with a different item's body, in another org's bucket. Use a fresh `mktemp` file per item, and after each PATCH read the body back (same read command as above) and confirm it is the original body plus only this item's intended passive-voice changes and the appended disclosure line; if it is not, stop that fork and report the item together with its original body (kept from the read) so it can be restored, rather than continuing.

### 4 — Report

Roll up every worker's table into one summary: total items edited (by type), total skipped, every low-confidence/borderline item surfaced for the user's own judgment (never silently resolved either way), and an explicit restatement of the issue-detection coverage gap (only as complete as the devices whose local state db was actually queried).

---

## Self-audit

Run this section when the skill may have drifted from reality — e.g. after gardener's dispatch code changed, `gh` flags changed, or results are consistently wrong.

1. Read this skill file from top to bottom.
2. For each command, path, or assumption, verify it is still correct:
   - `/root/gardener/gardener/dev_loop.py` still defines `ATTRIBUTION_REQUIREMENT` and `ORPHAN_MARKER` with the marker string and disclosure wording this skill assumes — if either changed, this skill's canonical disclosure line and marker search are stale and must be updated to match, not the other way around
   - The local sqlite db's path, `runs` table schema (`repo`, `mode`, `gap_summary`, `timestamp`, `outcome`), and the `mode` values actually present (still only `tend`, or has `implement`/`file-issue` started appearing?) still hold
   - `gh search prs`, `gh api .../issues/.../comments`, and the PATCH endpoints/flags used above still exist and behave as described
   - The org list this skill's examples reference still reflects the fleet's actual orgs (re-derive live, don't trust a stale list)
3. For each problem found, open a GitHub issue. This repo is public: write the body in passive voice, name no private repository, and end it with the disclosure line (re-derived from the live `ATTRIBUTION_REQUIREMENT`, as in Step 1) and the Claude sign-off. Write the body to a fresh per-issue file and pass it with `--body-file`, so the body never passes through shell quoting:
   ```bash
   ISSUE_BODY=$(mktemp)   # write the body below into this file, then:
   gh issue create --repo dmccoystephenson/gardener-attribution-audit \
     --title "<problem summary>" \
     --body-file "$ISSUE_BODY"
   ```
   ```markdown
   **Section:** <which step or section is wrong>
   **Problem:** <what is incorrect>
   **Expected behavior:** <what it should do instead>

   ---

   _This issue body was drafted during a Gardener session ([Stephenson-Software/gardener](https://github.com/Stephenson-Software/gardener))._

   _drafted by Claude on behalf of Daniel Stephenson_
   ```
4. Report a summary: how many issues were filed, or confirm the skill is up to date.
