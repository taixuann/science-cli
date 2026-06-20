---
layer: [4]
type: plan
status: done
tags: [results, status, serve]
assignee: code
---

# Implementation Plan: Results Stars + Migration Warning + Serve Gallery Fixes

**Date**: 16/06/2026
**Status**: 🟡 Planning
## Context Summary

Three remaining tasks after the config/study cleanup and plot help/fzf redesign:
1. **Migration warning** still appears when running any command (noisy)
2. **Results star/highlight** — user wants to mark important results files to easily identify them when using `results --move`
3. **Serve gallery PDF viewing** — PDFs need to auto-scale large, gallery container needs vertical scroll

The serve gallery is a React SPA (compiled/minified). CSS overrides via `index.html` is the viable approach. The JS bundle `index-B7LEr9BI.js` is minified and not editable.

## Objectives

1. Remove migration warning (`_warn_migrate_once` in `core/config.py`)
2. Add star system for results:
   - `.stars.json` store in `project/results/`
   - `sci results star` or `sci results --star` subcommand to toggle stars
   - ⭐ indicator in fzf display for `results --move`
3. Fix serve gallery PDF viewing:
   - Auto-scale PDFs to fill available space
   - Vertical scroll inside gallery container instead of full page scroll
   - Inline CSS overrides in `index.html`

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `core/config.py` | Remove `_warn_migrate_once()` call (line 282), remove function + global var | Low |
| `cli/commands/results.py` | Add star toggle command, star display in fzf, star state management | Med |
| `core/fzf_utils.py` | Check if star needs to be passed to display format (likely no change needed) | Low |
| `serve/frontend/index.html` | Add inline `<style>` block for PDF auto-scaling + gallery vertical scroll | Low |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Implementation | code-medium | Main feature work |
| QA & Review | review-light | Smoke test + verify CLI + serve |
| Documentation | docs-light | Update README, artifact-review |
| Calendar Sync | calendar | N/A |

## Tasks

| ID | Description | Est. Duration | Assigned To | Calendar Event |
|----|-------------|---------------|-------------|----------------|
| task-001 | Remove migration warning from config.py | 10m | code | no |
| task-002 | Add results star system: .stars.json store, toggle command, ⭐ in fzf | 45m | code | no |
| task-003 | Fix serve gallery PDF viewing: inline CSS for scaling + scroll | 20m | code | no |
| task-004 | QA: test results star, verify serve gallery, run tests | 20m | review | no |
| task-005 | Docs: update CHANGELOG, mark artifact done | 10m | docs | no |

## Dependency Order

1. task-001 (Migration warning — trivial)
2. task-002 + task-003 (Stars + serve fixes — parallel)
3. task-004 (QA)
4. task-005 (Docs)

## Walkthrough

### task-001: Remove migration warning

In `core/config.py`:
- Line 282: Remove `_warn_migrate_once()` call
- Lines 230-238: Remove `_warn_migrate_once()` function definition  
- Line ~157: Remove `_session_emitted_deprecation = False` global var
- Update docstring of `load_global_config()` to remove mention of migration warning

Result: The "Monolithic config.yaml detected" warning will stop appearing.

### task-002: Results star system

**Star store** (`results.py`):
```python
import json

def _stars_path(proj: Path) -> Path:
    return proj / "results" / ".stars.json"

def _load_stars(proj: Path) -> dict[str, bool]:
    sp = _stars_path(proj)
    if sp.exists():
        try:
            return json.loads(sp.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}

def _save_stars(proj: Path, stars: dict[str, bool]) -> None:
    sp = _stars_path(proj)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(stars, indent=2))
```

**Star toggle handler**:
- Parse `results_handler()` for `--star` or `star` subcommand
- Show fzf list of result files (with current ⭐ status)
- User selects → toggle star → save

**Modified `_results_move()`**:
- Load stars and prepend `⭐ ` to display line for starred files
- On selection: create symlinks as before (star is just a visual indicator)
- Make `fzf_select` searchable on `⭐` so user can filter by star

### task-003: Serve gallery PDF viewing

In `serve/frontend/index.html`, add a `<style>` block before `</head>`:

```css
/* Gallery PDF auto-scale */
#root iframe[src*=".pdf"],
#root object[type="application/pdf"],
#root embed[src*=".pdf"] {
    width: 100% !important;
    height: 85vh !important;
    max-height: 85vh !important;
}

/* Gallery container vertical scroll */
#root > div {
    max-height: 100vh !important;
    overflow-y: auto !important;
}

/* Individual gallery item container */
.gallery-item, [class*="gallery"] {
    max-height: 90vh !important;
    overflow-y: auto !important;
}
```

The key issue is that the React app's CSS is Tailwind-generated, so we don't have control there. Inline CSS in `index.html` will override these styles.

### task-004: QA
- Run `pytest tests/ -q` — expect 414 pass, 1 pre-existing fail
- Manually verify:
  - Migration warning is gone: `python -m science_cli.cli.main ls -m instrument 2>&1 | grep -i "migrate\|config.yaml"` → no output
  - Results star: `python -m science_cli.cli.main results --star` → fzf with ⭐
  - Results move: `python -m science_cli.cli.main results --move` → ⭐ visible in fzf
  - Serve gallery: start serve, open browser, check PDF scaling + scroll

### task-005: Docs
- Update CHANGELOG.md with v3.15.0 entry
- Update artifact status to 🟢 Done
- Update .lavish/ artifact dashboard
