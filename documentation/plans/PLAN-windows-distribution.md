# PLAN: Windows Distribution, Install Scripts & fzf Bundling

## Classification
infrastructure / distribution

## Related Plans
- Existing PLAN files in `documentation/plans/` (unrelated)
- No currently blocking plans

## Status
- **Created**: 2026-06-09
- **Status**: draft
- **Branch**: main

## Objective

Make science-cli easy for Windows users to download, install, and use, by:

1. Creating the missing `install.sh` and `install.ps1` scripts (already referenced in README, both 404)
2. Making fzf work out-of-the-box on Windows (either bundled, auto-downloaded, or replaced with pure-Python)
3. Defining a sustainable Windows distribution strategy
4. Updating all documentation to reflect the new installation paths

---

## Context Summary

### Current State

| Concern | Status |
|---------|--------|
| README install section | References `scripts/install.sh` and `scripts/install.ps1` at `raw.githubusercontent.com` URLs — both return 404 |
| `scripts/` directory | Single file: `generate_nature_previews.py` — no install scripts exist |
| fzf dependency | Required, not bundled. `fzf_utils.py` (276 lines) calls `subprocess.run(["fzf", ...])`. Fallback is a primitive numbered-list prompt (`_fallback_select`) |
| fzf usage | 39 call sites across the codebase — deeply integrated as the default file selection mode |
| `pyproject.toml` deps | Heavy: numpy, scipy, matplotlib, lmfit, plotly, textual — makes standalone .exe bundling difficult |
| Windows docs | `documentation/library/installation.md` — one-line: "Works under WSL or native Python" |
| Existing install docs missing fzf | Neither README nor `installation.md` mentions installing fzf |

### fzf Integration Architecture

```
fzf_utils.py:
  fzf_select(items, prompt, multi, preview, ...)
    ├── shutil.which("fzf") ? → _run_fzf() [subprocess.Popen to fzf binary]
    └── fzf not found → _fallback_select() [numbered list, input()]
```

- `fzf_select()` is imported lazily (inside function bodies) in 39 call sites across 9 files
- The `_fallback_select()` is a basic numbered prompt — adequate but not fuzzy
- `/dev/tty` approach: opens real terminal via `os.open("/dev/tty")`, routes fzf stderr there — this is Unix-only and will fail on Windows

### fzf Binary Distribution

fzf (junegunn/fzf) provides pre-built binaries for all platforms via GitHub Releases:
- Windows: `fzf-<version>-windows_amd64.zip` (~3 MB), `windows_arm64.zip`
- macOS: `darwin_amd64` / `darwin_arm64` (~2 MB)
- Linux: `linux_amd64` / `linux_arm64` / `linux_armv5/6/7` (~2 MB)

Latest: v0.73.1 (2026-05-25).

### Pure-Python Fuzzy Finder Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **minifzf** (PyPI) | Pure-Python fuzzy finder, lightweight | No external dep, pip-installable | New dependency, different UX from fzf, no preview window |
| **prompt_toolkit** fuzzy completion | Already a dep — used in REPL. Can build fuzzy file picker | Zero new deps, tight integration | Custom build needed, no preview, significant dev effort to match fzf's UX |
| **questionary** autocomplete | Already a dep — has `autocomplete` path selector | Zero new deps | No multi-select, no preview, not really fuzzy |
| **Custom built-in** | Write a minimal fuzzy filter + navigable list in `fzf_utils.py` | No external dep, full control | Needs vim-like keybindings, significant dev effort |

---

## Phase 1: Install Scripts (Create What's Already Documented)

### 1.1 `scripts/install.sh` — macOS/Linux

**Files to create:**
- `scripts/install.sh` (new)

**Implementation approach:**

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Check Python 3.9+
# 2. Install fzf:
#    - macOS: `brew install fzf` (or download from GitHub releases)
#    - Linux: download static binary from GitHub releases to ~/.local/bin/fzf
# 3. Install science-cli:
#    - Prefer pipx: `pipx install science-cli`
#    - Fallback: `python3 -m venv ~/.science-cli-venv && ...`
# 4. Run `sci config init`
# 5. Print success + next steps
```

**Key behaviors:**
- Idempotent (skip if already installed)
- Non-destructive (uses pipx or isolated venv)
- Respects `$PREFIX` / `$HOME` conventions
- Offers to add `~/.local/bin` to PATH if needed
- Detects and warns about old Python versions

**Edge cases:**
- No `brew` on Linux → download fzf binary directly
- No `pipx` → `pip3 install pipx` then retry, or use venv
- `~/.local/bin` not on PATH → print warning with fix command
- Already installed → `pipx upgrade science-cli` or print version info

### 1.2 `scripts/install.ps1` — Windows

**Files to create:**
- `scripts/install.ps1` (new)

**Implementation approach:**

```powershell
#Requires -Version 5.1

# 1. Check Python 3.9+
#    - Try `python --version`
#    - If missing: offer to install via winget (`winget install Python.Python.3.11`)
# 2. Install fzf:
#    - Download fzf-<version>-windows_amd64.zip from GitHub releases
#    - Extract to $env:LOCALAPPDATA\science-cli\bin\fzf.exe
#    - Add to PATH (user-level)
# 3. Install science-cli:
#    - `pip install science-cli` (user-level with --user, or in a venv)
#    - Or: `pipx install science-cli` (if pipx is available)
# 4. Run `sci config init`
# 5. Print success + next steps
```

**Key behaviors:**
- Uses `winget` for Python if missing (built into Windows 11 / available on Windows 10)
- Downloads fzf from canonical GitHub releases URL (not a custom mirror)
- Verifies SHA256 checksum of fzf download
- Persistently adds fzf to PATH via `[Environment]::SetEnvironmentVariable`
- Detects running in PowerShell 5.1+ vs PowerShell Core vs Windows PowerShell

**Edge cases:**
- No `winget` (Windows < 1809 or LTSC) → point user to python.org download
- PowerShell execution policy restricted → `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
- Antivirus blocking fzf binary download → document as known issue
- Corporate proxy → respect `$env:HTTP_PROXY` / `$env:HTTPS_PROXY`
- Path already has fzf → skip download
- Extract zip without `Expand-Archive` → use `System.IO.Compression.ZipFile` as fallback
- User has spaces in `$env:LOCALAPPDATA` → quote all paths properly

### 1.3 README Installation Section Update

**Files to modify:** `README.md`

**Changes:**
- Replace installation section (lines 14-37) with working commands
- Add a **Prerequisites** callout: "Requires Python 3.9+ and fzf (installed automatically by the scripts)"
- Keep `pip install science-cli` and `uv tool install science-cli` as manual options
- Add note about fzf being installed automatically
- Change example `curl ... | bash` / `irm ... | iex` to point to correct raw URLs

**Risk/effort:** Low. Straightforward script writing, ~2-3 hours for both scripts plus README updates.

**Testing strategy:**
- Test `install.sh` on: macOS (Intel + Apple Silicon), Ubuntu 22.04/24.04 (clean environment)
- Test `install.ps1` on: Windows 11 (clean VM), Windows 10 22H2
- Test idempotency: run twice, verify no duplicate installations
- Test failure modes: no Python, no internet, existing installation
- All tests can be run in CI via GitHub Actions (matrix: ubuntu-latest, macos-latest, windows-latest)

**GitHub Actions matrix for testing:**

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, macos-latest, windows-latest]
    python-version: ["3.9", "3.10", "3.11", "3.12"]
```

---

## Phase 2: fzf Bundling / Replacement

### 2.1 Analysis of Options

#### Option A: Download fzf Binary in Install Scripts (Short-term Fix)

**Approach:** The install scripts (Phase 1) already handle downloading fzf. Windows gets `fzf.exe` placed in PATH.

**Pros:**
- Users get the real fzf with preview windows, multi-select, theming
- Zero code changes to `fzf_utils.py`
- Works immediately for all 39 call sites

**Cons:**
- Still an external binary dependency
- fzf binary needs updates over time
- `/dev/tty` approach in `fzf_utils.py` doesn't work on Windows — fzf needs `CONIN$` / `CONOUT$` or a proper console handle
- Users who `pip install` without the install script still need to install fzf manually

**Windows `/dev/tty` problem in `fzf_utils.py`:**

The current code at `fzf_utils.py:116` does:
```python
tty_fd = os.open("/dev/tty", os.O_RDWR)
```

This will raise `FileNotFoundError` on Windows. The fallback `_fallback_select()` will be invoked. To make fzf work on Windows, the fzf execution path needs to handle Windows console differently — either use `CONIN$`/`CONOUT$` or simply let fzf inherit the console directly (use `subprocess.Popen` without explicit stderr routing).

**Fix for Windows fzf execution:**

```python
import platform

def _run_fzf(...):
    if platform.system() == "Windows":
        # Windows: let fzf inherit console directly
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,  # inherit parent console
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
        )
    else:
        # Unix: route stderr to /dev/tty
        tty_fd = os.open("/dev/tty", os.O_RDWR)
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=tty_fd,
        )
        os.close(tty_fd)
```

#### Option B: Pure-Python Fuzzy Finder Replacement (Recommended Long-term)

**Approach:** Replace the fzf subprocess call with a built-in Python fuzzy finder. This eliminates the external dependency entirely.

**Implementation strategy:**

1. **Add a minimal fuzzy filter + navigable list selector to `fzf_utils.py`**
2. **Use `prompt_toolkit` (already a dependency)** for rendering — it handles cross-platform terminal I/O natively

**New PythonFileSelector class (in `fzf_utils.py`):**

```python
class PythonFileSelector:
    """Pure-Python fuzzy file selector using prompt_toolkit.

    Provides: fuzzy search, multi-select, preview window emulation,
    keyboard navigation (up/down/enter/esc/tab), vim-style keybindings.
    """

    def __init__(
        self,
        items: list[str],
        prompt: str = "Select:",
        multi: bool = False,
        preview: str | None = None,
        query: str = "",
    ):
        ...

    def run(self) -> list[str]:
        """Show the interactive selector. Returns selected items."""
        ...

    def _filter_items(self, query: str) -> list[tuple[str, int]]:
        """Fuzzy-filter items by query. Returns (item, score) pairs."""
        ...
```

**Fuzzy matching algorithm:** Implement a simple substring + levenshtein scorer, or re-implement fzf's scoring (character match positions + contiguous bonus + boundary bonus + exact match bonus). See `junegunn/fzf/src/pattern.go` for reference — the algorithm is well-documented and portable.

**Preview window emulation:**
- Accept a preview command template string
- Execute preview command when selection changes (debounced)
- Display result in a right/bottom panel using `prompt_toolkit` split layout

**Proposed `fzf_select` refactoring:**

```python
def fzf_select(
    items: list[str],
    prompt: str = "Select:",
    multi: bool = False,
    preview: str | None = None,
    preview_window: str | None = None,
    query: str = "",
) -> list[str]:
    if not items:
        return []

    # Strategy selection based on environment
    use_fzf_binary = shutil.which("fzf") and platform.system() != "Windows"
    # Windows: prefer Python selector (fzf binary has console issues)
    # Can be overridden by env var SCIENCE_CLI_USE_FZF=1

    if use_fzf_binary:
        try:
            input_text = "\n".join(items)
            args = _build_fzf_args(prompt, multi, preview, preview_window, query)
            return _run_fzf(args, input_text, items, prompt, multi)
        except (FileNotFoundError, OSError):
            pass

    return _python_fuzzy_select(items, prompt, multi, preview, query)
```

**Config option to choose selector (in `session.py`):**

```python
session["fzf_opts"]["selector"] = "auto"  # "auto" | "fzf" | "python"
```

- `auto`: Use fzf binary if available and on Unix; use Python selector on Windows and as fallback
- `fzf`: Always use fzf binary (current behavior)
- `python`: Always use Python selector (useful for testing / environments without fzf)

#### Option C: Bundle fzf Binary via Package Data

**Approach:** Include the fzf binary (for the current platform) as package data in the pip package.

**Pros:**
- Zero install steps beyond `pip install science-cli`
- Everyone gets fzf regardless of platform

**Cons:**
- Must include binaries for all supported platforms (or detect at install time)
- Building platform-specific wheels is complex
- fzf is ~2 MB compressed per platform — multiplies package size
- Go binary may flag antivirus software
- License and update maintenance burden

**Verdict:** Not recommended. The package-data approach has significant maintenance overhead for a Go binary that's large and subject to platform-specific issues. Option B (pure-Python) is cleaner and more sustainable.

### 2.2 Recommended Phase 2 Approach

**Two-stage rollout:**

| Stage | Timing | Action |
|-------|--------|--------|
| **Stage 1** | Phase 1 timeframe | Fix Windows fzf binary download in install scripts + fix `/dev/tty` issue for Windows |
| **Stage 2** | Next major version (v4.0) | Replace with pure-Python fuzzy finder, make fzf binary fully optional |

**Stage 1 deliverables (minimal code changes):**

1. **`fzf_utils.py`**: Add platform detection for Windows fzf execution (bypass `/dev/tty`)
2. **`session.py`**: Add `selector: "auto"` config option
3. **`fzf_utils.py`**: Upgrade `_fallback_select` to use `prompt_toolkit` (already a dep) for a better no-fzf experience — fuzzy filtering, arrow key navigation, styled display

**Stage 2 deliverables (full pure-Python selector):**

1. Implement `_python_fuzzy_select()` in `fzf_utils.py` using `prompt_toolkit`
2. Implement fuzzy matching algorithm (substring + scoring)
3. Implement basic preview window (execute shell command, show output in panel)
4. Add comprehensive tests
5. Document the Python selector as the primary path, fzf binary as a power-user enhancement
6. Mark `_fallback_select` as deprecated

**Effort:**
- Stage 1: ~2 hours (platform check, `_fallback_select` upgrade, Windows console fix)
- Stage 2: ~2-3 weeks (full prompt_toolkit-based selector with preview, tests, integration)

### 2.3 Upgraded `_fallback_select` (Stage 1, Quick Win)

Replace the current numbered-list `_fallback_select` with a `prompt_toolkit`-based interactive selector:

```python
def _fallback_select(
    items: list[str], prompt: str, multi: bool
) -> list[str]:
    """Interactive selection using prompt_toolkit.

    Provides: fuzzy filtering via text input, arrow key navigation,
    multi-select with tab, styled display with Rich.
    """
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import FuzzyCompleter, WordCompleter
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.formatted_text import HTML

    # ... implementation using prompt_toolkit's built-in fuzzy completion
    # This builds on prompt_toolkit's existing capabilities without
    # needing a separate selector UI
```

This provides immediate value for Windows users and anyone without fzf installed — fuzzy filtering via `prompt_toolkit`'s built-in `FuzzyCompleter` is already available (it's what the REPL uses).

---

## Phase 3: Windows-Native Distribution

### 3.1 Distribution Strategy Comparison

| Approach | File Size | Python Not Required | Works with all deps | Maintenance |
|----------|-----------|-------------------|---------------------|-------------|
| **Pip install** (current) | ~50 MB deps | No | Yes | Zero |
| **pipx install** (recommended) | ~50 MB deps | No | Yes | Zero |
| **PyInstaller .exe** | ~200-400 MB | Yes | Challenging (numpy/scipy/matplotlib) | High |
| **Nuitka .exe** | ~100-200 MB | Yes | Challenging | Very high |
| **conda install** | ~200 MB with conda | No (needs conda) | Yes | Moderate |

### 3.2 Recommended Path: pipx + Install Script

The install script (`install.ps1`) handles:

1. **Python installation** (via winget or download link)
2. **pipx setup** (`python -m pip install pipx`)
3. **science-cli installation** (`pipx install science-cli`)
4. **fzf installation** (binary download to `~/.science-cli/bin/`)
5. **PATH management** (add both pipx and fzf bin dirs)
6. **Verification** (`sci --version`, `sci --help`)

### 3.3 Why NOT PyInstaller

The short answer: numpy, scipy, matplotlib, lmfit, and plotly are extremely difficult to bundle with PyInstaller:

- **numpy/scipy**: Compiled C/Fortran extensions with complex shared library loading. Must pin exact versions. Hidden imports must be manually declared.
- **matplotlib**: Must include backend DLLs, font files, and often a specific backend (Agg for headless). 30-50 MB just for matplotlib.
- **lmfit**: Depends on scipy's optimize module — more hidden imports.
- **plotly**: No compilation issues (pure JS), but the `orca` dependency for static export adds complexity.
- **Total bundle size**: Conservatively 200-400 MB for a single .exe.
- **Build time**: 15-30 minutes on CI.
- **Windows Defender**: Will flag the bundled .exe as suspicious.

**Verdict**: PyInstaller is not worth the effort for this project. The user persona (materials science researchers) can install Python without difficulty.

### 3.4 Alternative: "Portable" Mode via install.ps1

Offer a `-Portable` flag in `install.ps1`:

```powershell
.\install.ps1 -Portable
```

This creates a self-contained directory `%USERPROFILE%\science-cli-portable\` containing:
- A Python venv (`.\venv\`)
- science-cli installed in the venv
- fzf.exe in `.\bin\`
- A `sci.bat` launcher that activates the venv and runs `sci %*`

Users can move this directory anywhere, including a USB stick.

**Implementation:** ~4 hours. The `-Portable` flag is a straightforward extension of the install script.

### 3.5 Future Consideration: conda-forge Package

For Windows users who use conda (common in scientific computing), a conda-forge recipe would be ideal long-term. This is a separate effort but worth noting.

**Effort:** ~2 hours for initial install script, ~4 hours for portable mode.

---

## Phase 4: Documentation Updates

### 4.1 Files to Modify

| File | Changes |
|------|---------|
| `README.md` | Rewrite installation section, add fzf dependency note, update curl/irm examples |
| `documentation/library/installation.md` | Full rewrite with platform-specific instructions |
| `src/science_cli/core/README.md` | Update fzf integration section to note Windows support + Python selector |

### 4.2 README Installation Section (New)

```
## Quick Install

### macOS / Linux (Recommended)
```bash
curl -fsSL https://raw.githubusercontent.com/taixuann/science-cli/main/scripts/install.sh | bash
```

### Windows (Recommended)
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
irm https://raw.githubusercontent.com/taixuann/science-cli/main/scripts/install.ps1 | iex
```

### Manual Installation (all platforms)
```bash
pipx install science-cli     # recommended
# or
pip install science-cli
```

### Using uv (fast, cross-platform)
```bash
uv tool install science-cli
```

### fzf Dependency
science-cli uses **fzf** for interactive file selection. The install scripts above
will install fzf automatically. If you install manually, you need fzf separately:

- **macOS**: `brew install fzf`
- **Linux**: Download from https://github.com/junegunn/fzf/releases
- **Windows**: Download from https://github.com/junegunn/fzf/releases or use `winget install fzf`
```

### 4.3 Installation Guide (`documentation/library/installation.md`)

Rewrite with sections:

1. **Prerequisites** (Python 3.9+, pip/pipx)
2. **Quick Start** (one-liner for each platform)
3. **Manual Installation** (pip, pipx, uv)
4. **fzf Installation** (per-platform)
5. **Post-Install** (config init, verification)
6. **Platform Notes** (expanded per-platform table)
7. **Troubleshooting** (common issues)

### 4.4 Troubleshooting Section

Common Windows issues to document:

| Issue | Solution |
|-------|----------|
| `python` not found | Install Python from python.org or `winget install Python.Python.3.11` |
| Execution policy blocked | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| fzf not found | Run the install script, or download fzf.exe manually from GitHub releases |
| TUI won't launch | Use `sci --repl` or `sci <command>` instead of bare `sci`. TUI needs Windows Terminal or a compatible terminal |
| `/dev/tty` errors | These are harmless — science-cli falls back to built-in selection |
| `sci` command not recognized | Add `%USERPROFILE%\.local\bin` and `%LOCALAPPDATA%\science-cli\bin` to PATH |
| Plot windows don't open | `matplotlib` needs a backend. Set `MPLBACKEND=TkAgg` or use `sci plot --save` |

---

## Implementation Order & Dependencies

```
Phase 1: Install Scripts
  ├── 1.1 scripts/install.sh         ← No dependencies
  ├── 1.2 scripts/install.ps1        ← No dependencies
  └── 1.3 README.md update           ← Depends on 1.1, 1.2

Phase 2: fzf Improvements
  ├── 2.1 Windows console fix        ← Strongly recommended before Phase 1 release
  │     (fzf_utils.py platform check)
  ├── 2.2 Upgrade _fallback_select   ← Can be done independently
  │     (use prompt_toolkit)
  └── 2.3 Pure-Python selector        ← Long-term, v4.0 milestone

Phase 3: Windows Distribution
  ├── 3.1 install.ps1 refinement     ← After Phase 1
  └── 3.2 Portable mode               ← Optional, after Phase 1

Phase 4: Documentation
  ├── 4.1 installation.md rewrite    ← After Phase 1
  ├── 4.2 README.md update            ← After Phase 1
  └── 4.3 core/README.md update      ← After Phase 2
```

### Recommended Sprint Order

| Sprint | Focus | Contents | Est. Duration |
|--------|-------|----------|---------------|
| **Sprint A** | Fix Windows + create scripts | install.sh, install.ps1, Windows console fix, README update | 4-6 hours |
| **Sprint B** | Upgrade fallback selector | prompt_toolkit-based `_fallback_select`, installation.md rewrite | 3-5 hours |
| **Sprint C** | Documentation + polish | Full doc rewrite, portable mode, troubleshooting, CI testing | 3-4 hours |
| **Sprint D** (v4.0) | Pure-Python selector | Full `_python_fuzzy_select` implementation, remove fzf hard dependency | 2-3 weeks |

---

## Files to Create/Modify

| File | Phase | Action | Risk |
|------|-------|--------|------|
| `scripts/install.sh` | Phase 1 | **Create** | Low |
| `scripts/install.ps1` | Phase 1 | **Create** | Low |
| `README.md` | Phase 1, 4 | Modify (install section) | Low |
| `src/science_cli/core/fzf_utils.py` | Phase 2 | Modify (platform check, Windows fzf exec, upgraded fallback) | Medium |
| `src/science_cli/core/session.py` | Phase 2 | Modify (add `selector` config option) | Low |
| `documentation/library/installation.md` | Phase 4 | Rewrite | Low |
| `src/science_cli/core/README.md` | Phase 4 | Modify (fzf section update) | Low |
| `.github/workflows/ci.yml` | Optional | Add install-script test matrix | Low |

---

## Testing Strategy

### Per-Platform Matrix

| Test | macOS | Linux | Windows |
|------|-------|-------|---------|
| `install.sh` fresh install | ✅ | ✅ | N/A |
| `install.ps1` fresh install | N/A | N/A | ✅ |
| Manual `pip install` + fzf | ✅ | ✅ | ✅ |
| Python selector (no fzf) | ✅ | ✅ | ✅ |
| fzf binary selection | ✅ | ✅ | ✅ (after console fix) |
| TUI launch (`sci --tui`) | ✅ | ✅ | ⚠️ needs Windows Terminal |
| REPL launch (`sci --repl`) | ✅ | ✅ | ✅ |
| CLI commands (`sci plot`, etc.) | ✅ | ✅ | ✅ |
| Path not in PATH | ✅ | ✅ | ✅ |

### CI Configuration (GitHub Actions)

```yaml
# .github/workflows/test-install.yml
on: [push, pull_request]
jobs:
  test-install-scripts:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    steps:
      - uses: actions/checkout@v4
      - name: Run install script
        run: |
          if [[ "${{ runner.os }}" == "Windows" ]]; then
            powershell -File scripts/install.ps1
          else
            bash scripts/install.sh
          fi
      - name: Verify science-cli
        run: sci --version
```

### Unit Tests for fzf_utils.py

| Test | Description |
|------|-------------|
| `test_fzf_select_no_fzf` | `fzf_select()` without fzf binary → uses Python selector |
| `test_fzf_select_fallback` | `_run_fzf` failure → falls back gracefully |
| `test_fallback_select_single` | Single item selection via prompt_toolkit fallback |
| `test_fallback_select_multi` | Multi-select via prompt_toolkit fallback |
| `test_fallback_select_cancel` | User cancels → empty list |
| `test_platform_detection` | Windows vs Unix console routing |
| `test_selector_config` | `auto` / `fzf` / `python` config options respected |
| `test_build_fzf_args` | Args construction with various options |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Windows fzf console doesn't work with subprocess.PIPE | Medium | Test on Windows VM early. Fall back to Python selector immediately if fzf exec fails |
| prompt_toolkit-based selector has worse UX than fzf | Medium | Invest in keyboard navigation (vim keybindings, tab multi-select). Make fzf binary an opt-in power-user mode |
| `install.ps1` blocked by corporate security policies | Low | Document manual install steps clearly. Offer portable/offline mode |
| Windows Defender flags downloaded fzf.exe as suspicious | Low | Document how to add exclusion. Use official GitHub release URLs with SHA256 verification |
| PyInstaller bundling attempted prematurely | High (time waste) | **Recommended path explicitly avoids PyInstaller.** Document why in the plan |
| Existing users on Unix systems broken by platform check changes | Low | Test thoroughly on all 3 platforms. The `platform.system()` branch only affects Windows |
| Python 3.9 compatibility for prompt_toolkit features | Low | prompt_toolkit supports Python 3.9+. Verify before release |

---

## Walkthrough Notes

*(To be filled during/after implementation)*
