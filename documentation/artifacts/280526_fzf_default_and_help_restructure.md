# PLAN: FZF-as-Default & CLI Help Restructure

## Classification
config / cleanup

## Related Plans
- [[280526_documentation_reorg]] — related (help text references)
- [[280526_refactor]] — related (command structure patterns)
- [[280526_themes]] — affects (per-technique plot templates)

## Status
- **Created**: 2026-05-28
- **Status**: completed
- **Branch**: dev

## Objective
1. **`--fzf` becomes the implicit default** — users never type `--fzf`; interactive fzf selection is triggered automatically when appropriate.
2. **CLI help restructure** — regroup commands into semantic categories and add GROUP 3/4 distinction for generic vs technique-specific plotting.

---

## Context

### Problem 1: `--fzf` is noisy
Currently 7+ commands require the user to type `--fzf` explicitly to enter interactive mode. This is cumbersome since fzf selection is almost always what users want. The pattern:
- `plot` with no args already defaults to fzf (good) — but `plot --overlay` without `--fzf` fails.
- `add -m data` **requires** `--fzf` or it errors out.
- `results` silently skips fzf if `--fzf` omitted.
- `raman info/plot/analyze` requires `--fzf` for interactive mode.
- `memristor add --fzf` and `memristor plot --fzf` are argparse flags.
- `delete -m data` references `--fzf` in help text.

### Problem 2: Help menu grouping is stale
Current groups don't reflect actual usage patterns:
- `config`, `status`, `results`, `info`, `chat` are dumped in GROUP 3 "DATA ANALYSIS" — they're contextual/informational, not analytical.
- No distinction between generic `plot`/`analyze` and technique-specific `memristor plot`/`raman plot`.
- Future technique commands (`ec`, `uv-vis`, `iv`) need a home.

---

## Specification

### Constraints (from user feedback)
1. **TUI is EXCLUDED** — `tui/app.py` is NOT modified. TUI will be updated separately if needed.
2. **`-f` flag is REMOVED** from `plot` and `analyze` — they become pure fzf-based. No more `-f file.txt`.
3. **Technique commands** (`memristor`, `raman`) get `--overlay`/`--all` support with their own styling, scoped to their protocol/step context.

---

### Part A: Default FZF + Remove `-f` flag

**Principle**: All file selection is done via fzf. The `-f` flag (direct file path) is removed from `plot` and `analyze`. Technique commands default to fzf when no explicit selection args are given.

#### Changes per command:

| Command | Current behavior | New behavior |
|---------|-----------------|--------------|
| `plot` | `plot` → interactive; `plot -f file.txt` → direct; `plot --overlay` → error | ALWAYS fzf. `plot` = fzf single-select (interactive style prompts). `plot --overlay` = fzf multi-select → overlay. `plot --all` = fzf multi-select → each file exported individually. |
| `analyze` | `analyze -f file.txt` → direct; no-fzf → error | ALWAYS fzf. `analyze --peaks` = fzf select → analyze with peaks. No `-f`. |
| `add -m data` | **Requires** `--fzf`; errors out without it | `add -m data` or `add -m data --all` → fzf auto-triggers. |
| `delete -m data` | **Requires** `--fzf`; errors without it | `delete -m data` → fzf auto-triggers. |
| `results` | `results` → list only; `results --fzf` → fzf open | `results` → fzf always for opening files. (`results` without fzf use-case removed) |
| `raman info` | `raman info <file>` → direct; `raman info --fzf` → fzf | `raman info` → fzf. `raman info <file>` → direct (still works). |
| `raman plot` | `raman plot <file>` → direct; `raman plot --fzf` → fzf | `raman plot` or `raman plot --grid` → fzf. `raman plot <file>` → direct. |
| `raman analyze` | `raman analyze --fzf` → fzf; without file → error | `raman analyze` or `raman analyze --baseline` → fzf. `raman analyze <file>` → direct. |
| `memristor add` | `memristor add --fzf` → fzf; `--file` → direct | `memristor add` (no `--file`) → fzf. `--file <path>` → direct. `--fzf` removed. |
| `memristor plot` | `memristor plot --fzf` → fzf | `memristor plot` (no filter flags) → fzf. `--overlay --all` passed to fzf context. `--fzf` removed. |
| `edit -m data` | Already uses fzf implicitly (no `--fzf` flag) | No change needed. |
| `config` | `config init` mentions `add -m data --fzf` | Update example to not show `--fzf`. |

#### TUI — EXCLUDED
- No changes to `tui/app.py`. The TUI remains as-is. Future PLAN may address TUI dispatch for default-fzf.

#### Help text updates:
- All `--fzf` flag entries removed from help docs.
- `-f` flag entries removed from `plot` and `analyze` help.
- Examples updated to not show `--fzf` or `-f`.
- `add -m data` examples simplified.

---

### Part B: CLI Help Restructure

#### New GROUP definitions in `help.py`:

```
GROUP 1: FILE MANAGEMENT        add, delete, edit, ls
GROUP 2: CONTEXT & INFORMATION  open, close, config, status, results, info, chat
GROUP 3: LIBRARY PLOTTING       plot, analyze
GROUP 4: TECHNIQUE COMMANDS     memristor, raman
ADDITIONAL                      help, version, clear, history
```

**GROUP 2 "CONTEXT & INFORMATION"**: `config` manages project/global settings, `status` shows context tree, `results` lists saved figures, `info` dumps project manifest, `chat` talks about current context. They all answer "what's my current state / how do I configure it".

**GROUP 3 "LIBRARY PLOTTING"**: Generic, technique-agnostic `plot` and `analyze`. These search globally across all files in the project's `data/raw/`. Technique detection is auto-inferred from filenames. Both are now **pure fzf** — no `-f` flag.

**GROUP 4 "TECHNIQUE COMMANDS"**: Technique-specific compound commands (`memristor`, `raman`). Each has its own `plot`/`analyze`/`ls` subcommands scoped to their protocol/step context, with pre-configured themes/templates/styles. `--overlay` and `--all` flags style output according to the technique.

#### Description updates in `help.py` and `__init__.py`:
| Entry | Old group | New group |
|-------|-----------|-----------|
| `config` | 3 (DATA ANALYSIS) | 2 (CONTEXT & INFORMATION) |
| `status` | 3 | 2 |
| `results` | 3 | 2 |
| `info` | 3 | 2 |
| `chat` | 3 | 2 |
| `plot` | 3 | 3 (now "LIBRARY PLOTTING") |
| `analyze` | 3 | 3 |
| `memristor` | 4 | 4 (now "TECHNIQUE COMMANDS") |
| `raman` | 4 | 4 |

---

### Part C: Future Technique Commands (Not Implemented Now)

The restructure opens a home for future technique-specific top-level commands:

```
GROUP 4: TECHNIQUE COMMANDS     memristor, raman, ec, uv-vis, iv
```

Each would follow the pattern:
- `ec plot --overlay` — electrochemistry overlay with EC templates
- `uv-vis plot` — UV-Vis with uv-vis-specific axes labels and themes
- `iv plot --all` — IV curves, each exported with IV-specific styling

These are **not** part of this plan.

---

### Part C: Future Technique Commands (Not Implemented Now)

The restructure opens a home for future technique-specific top-level commands:

```
GROUP 4: TECHNIQUE COMMANDS     memristor, raman, ec, uv-vis, iv
```

Each would follow the pattern:
- `ec plot` — electrochemistry plotting (cv, ca, eis) with ec-specific themes/templates
- `ec analyze` — ec-specific analysis (peaks, charge, fitting)
- `uv-vis plot` — UV-Vis plotting with uv-vis themes
- `iv plot` — IV curve plotting with dedicated IV styling

These are **not** part of this plan — only the group naming is set up to accommodate them.

---

## Files to Modify

| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/cli/help.py` | Edit | Restructure HELP_SECTIONS, update COMMAND_DESCRIPTIONS, update COMMAND_HELP desc/usage, remove `--fzf` & `-f` from flag docs & examples |
| `src/science_cli/cli/commands/__init__.py` | Edit | Update group numbers in COMMAND_TREE desc strings |
| `src/science_cli/cli/commands/plot.py` | Edit | Remove `--fzf` special-case; remove `-f` flag path; any non-keyword args → fzf interactive with flags |
| `src/science_cli/cli/commands/analyze.py` | Edit | Remove `-f` flag; default to fzf file selection then analyze |
| `src/science_cli/cli/commands/add.py` | Edit | Remove `--fzf` requirement in `_add_data()`; default to fzf |
| `src/science_cli/cli/commands/results.py` | Edit | Default `use_fzf = True` (always fzf) |
| `src/science_cli/cli/commands/raman.py` | Edit | Make fzf default for info/plot/analyze when no positional arg; remove `--fzf` check |
| `src/science_cli/library/memristor/device_cli.py` | Edit | Remove `--fzf` arg from `add` and `plot` subparsers; make fzf default |
| `src/science_cli/cli/commands/delete_cmd.py` | Edit | Remove `--fzf` requirement, default to fzf |
| `src/science_cli/SCHEMA.md` | Edit | Update line 117: "All subcommands should support --fzf" → "All subcommands default to fzf" |

### NOT modified (excluded):
- `tui/app.py` — TUI excluded from this PLAN
- `edit_cmd.py` — already uses fzf implicitly, no change needed

---

## Dependencies

None. This is self-contained within `src/science_cli/`.

## Cross-PLAN Impact

- Future technique commands (`ec`, `uv-vis`, `iv`) will slot into GROUP 4 naturally after this restructure.
- Any future PLAN that touches `help.py` or `COMMAND_TREE` should reference this PLAN for group assignments.

## Test Strategy

1. **Manual smoke test each command**:
   - `plot`, `plot --overlay`, `plot --all`, `plot --grid --legend` — all should trigger fzf
   - `analyze --peaks`, `analyze --charge` — should trigger fzf
   - `add -m data`, `add -m data --all` — should trigger fzf
   - `delete -m data` — should trigger fzf
   - `results` — should trigger fzf interactive open
   - `raman info`, `raman plot --grid`, `raman analyze --baseline` — should trigger fzf
   - `memristor add`, `memristor plot`, `memristor plot --overlay` — should trigger fzf
2. **Verify old `-f` flag is removed** — `plot -f file.txt` should no longer work (goes to fzf instead).
3. **Verify direct file arg still works** — `raman info file.txt`, `raman plot file.txt` should bypass fzf.
4. **Verify help menu** shows new grouping structure.
5. **Verify old `--fzf` flag**: silently accepted (backward compat) or triggers fzf (benign).
6. **Check `test_guardrails.py`** still passes — structural tests.

## Progress
- [x] PLAN created
- [x] User approved
- [x] IMPLEMENT — Part A: Default FZF
- [x] IMPLEMENT — Part B: Help Restructure
- [x] IMPLEMENT — Part C: TUI dispatch update (EXCLUDED — future PLAN)
- [x] TEST passed
- [x] DOCS updated (SCHEMA.md)
- [x] COMMIT done
