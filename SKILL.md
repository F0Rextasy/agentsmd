---
name: agentsmd
description: Compile and lint AGENTS.md agent-instruction hierarchies -- run `python scripts/agentsmd lint --root <dir>` for rule findings (no-title, unclosed-fence, missing-path, over-budget, duplicated-section), `effective <path>` for the child-wins compiled chain with per-section provenance, `discover` for the file list. Use when a repo has AGENTS.md files, when agent instructions may be stale/duplicated/bloated, or before trusting inherited rules.
---

# agentsmd

## When to run

- Repo (or PR) touches `AGENTS.md` files.
- Instructions seem stale: rules referencing paths, commands or docs that moved.
- Before onboarding an agent to a nested package: check what that package actually inherits.

## How to run

```bash
python scripts/agentsmd lint --root . --format json     # findings, exit 0/1
python scripts/agentsmd effective <path> --root .       # compiled chain for a path
python scripts/agentsmd discover --root .               # which files exist
```

Flags: `--max-bytes N` (default 24000), `--format text|json`.

## Report back

1. Summary line: `N file(s), M finding(s)` and the exit code.
2. One row per finding: `file:line: rule: message` — all five rules by name.
3. For effective: the `sources` chain and which file won each contested section.
4. Never auto-fix: propose the edit, let the owner decide.
