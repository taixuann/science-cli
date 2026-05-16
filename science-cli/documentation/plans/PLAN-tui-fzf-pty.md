# PLAN: TUI fzf PTY Fix

## Classification
feature / fix

## Related Plans
- None directly. This fixes a known limitation in the TUI suspend mode.

## Status
- **Created**: 2026-05-15
- **Completed**: 2026-05-15
- **Status**: completed
- **Branch**: refactor/2.1.0

## Objective
Make real fzf work inside Textual TUI suspend mode by giving fzf a true PTY via `script -q` on macOS, replacing the numbered-list fallback.

## Context
- `fzf_select()` in `fzf_utils.py` uses `subprocess.run(['fzf', ...], capture_output=True, ...)` which pipes stdout — fzf refuses to run interactively when stdout is a pipe (it needs a real TTY).
- A temporary workaround (commit `1e90a5f`) sets `SCI_TUI_ACTIVE=1` during TUI sessions and routes to `_fallback_select()` (numbered list) when this env var is detected.
- The user wants **real fzf**, not the numeric fallback. Their exact words: "open fzf means go outsides, finish choosing, get back to TUI."
- macOS has `script -q /tmp/out.txt <cmd>` which creates a PTY for the child process and writes all terminal output to the specified file.
- The approach: when inside TUI suspend mode (or always for safety), run fzf via `script -q` on macOS — fzf gets a real PTY, user can interact normally, and the selection is extracted from the output file after fzf exits.
- On Linux, `script -q` also exists but has subtly different semantics. We'll also consider `script` or `unbuffer` (from expect) as a cross-platform fallback.

## Specification

### Changes to `fzf_utils.py`

1. **Remove the `SCI_TUI_ACTIVE` guard** — lines 88-91 that check `os.environ.get("SCI_TUI_ACTIVE")` and return `_fallback_select()`.

2. **Add a `_run_fzf_via_script()` helper** that:
   - Creates a temp file path (e.g., via `tempfile.mkstemp()`)
   - Runs `script -q /tmp/sci-fzf-out.txt fzf <args>` on macOS
   - Reads the output file after fzf exits
   - Parses the selection from the output file
   - Cleans up the temp file
   - Falls back to `_fallback_select()` if `script` is not available

3. **Modify `fzf_select()`** to:
   - Detect macOS (`sys.platform == 'darwin'`) and use the `script`-based approach
   - On Linux, try `script` first, then fall back to `unbuffer` (from `expect` package), then fall back to `_fallback_select()`
   - Keep the `shutil.which('fzf')` guard unchanged

4. **Key implementation details for `script -q`**:
   - macOS `script -q /tmp/out.txt cmd` creates a typescript file with all terminal output including escape sequences
   - After fzf exits, the output file contains terminal escape sequences mixed with selected text
   - We need to strip ANSI escape sequences and extract the final selection(s)
   - The last non-empty, non-escape line(s) in the output file are typically the fzf selection(s)
   - Use `re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)` to strip ANSI escapes, then take the last non-empty stripped line(s)

### Changes to `app.py`

5. **Remove `SCI_TUI_ACTIVE` env var setting** in:
   - `on_mount()` — remove `os.environ["SCI_TUI_ACTIVE"] = "1"`
   - `on_unmount()` — remove `os.environ.pop("SCI_TUI_ACTIVE", None)`

### Edge Cases
- **Multiple selections (multi=True)**: fzf with `--multi` outputs one item per line. Parse all non-empty lines from the output.
- **No selection (ESC/Ctrl+C)**: fzf exits with code 1, no output. Detect via exit code or empty parsing.
- **Preview window**: Preview commands that write to stdout could interfere. The `script` output captures all terminal writes. We need to be careful to identify user selection vs preview output.
- **Linux compatibility**: `script -q` on Linux works differently (it takes `-c` for command). We'll handle both platforms.
- **Temp file cleanup**: Always clean up temp files, even on error (use `try/finally`).

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/core/fzf_utils.py` | Modify | Remove SCI_TUI_ACTIVE guard, add script-based PTY fzf execution |
| `src/science_cli/tui/app.py` | Modify | Remove SCI_TUI_ACTIVE env var setting in on_mount/on_unmount |

## Dependencies
- macOS with `script` command (always available on macOS)
- `fzf` binary installed (already checked via `shutil.which`)
- `tempfile` (stdlib) for temp file creation
- Optional: `unbuffer` from `expect` package on Linux

## Test Strategy
1. **Unit test**: Mock `subprocess.run` and temp file operations to verify output parsing
2. **Manual TUI test**: Launch `sci`, run a `--fzf` command (e.g., `plot --fzf`), verify fzf appears in a real TTY overlay, make a selection, verify it returns to TUI with the selection
3. **Regression**: Run `sci add -m data --fzf` outside TUI (from bash) — should still work as before
4. **Edge case**: Press ESC/Ctrl+C during fzf — should return empty selection gracefully

## Progress
- [x] Current state understood (fzf_utils.py, app.py inspected)
- [x] PLAN created
- [x] User approved
- [x] IMPLEMENT done
- [x] TEST passed
- [x] DOCS updated
- [x] COMMIT done

## Results

**Commit**: `145a1b3` — fix(tui): replace SCI_TUI_ACTIVE fallback with script-based PTY for real fzf

**Summary**: The `_run_fzf_via_script()` function is the core of the fix. It uses `script -q` to create a PTY because fzf needs stdout to be a real TTY:
- On macOS: `script -q <outfile> fzf <args>`
- On Linux: `script -q <outfile> -c "fzf <args>"`
- Items are fed via a temp file redirected to stdin
- fzf opens `/dev/tty` inside the PTY for interactive keystrokes
- The output file is parsed with ANSI stripping (CSI + OSC + standalone escape sequences); last non-empty lines = selection(s)
- Falls back to `_fallback_select()` if fzf or `script` is unavailable
- `SCI_TUI_ACTIVE` env var is completely removed — no more env-var gating

**Files changed**:
| File | Change |
|------|--------|
| `src/science_cli/core/fzf_utils.py` | Removed `SCI_TUI_ACTIVE` guard; added `_run_fzf_via_script()`; updated `fzf_select()` to use PTY approach |
| `src/science_cli/tui/app.py` | Removed `SCI_TUI_ACTIVE` env var set/unset in `on_mount()` / `on_unmount()` |

**Tests**: 75 existing tests pass (no regressions; 3 pre-existing config failures unrelated). Green traffic light from qa-tester. Full test report at `documentation/test-reports/TEST-REPORT-fzf-pty-2026-05-15.md`.

**Edge cases handled**:
- Multi-select: fzf with `--multi` outputs one item per line; all non-empty stripped lines captured
- No selection (ESC/Ctrl+C): fzf exits with code 1; empty list returned
- Temp file cleanup: both item and output temp files cleaned in `try/finally`
- Cross-platform: macOS and Linux `script -q` flag differences handled
- Missing dependencies: graceful fallback to `_fallback_select()`
