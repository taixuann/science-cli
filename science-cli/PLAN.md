# Plan: Central Path Config + Nested Protocol YAML

## Objective
Create `science_cli/core/paths.py` as the single source of truth for all file path logic in science-cli, and update protocol YAML location to nested `protocol/<name>/<name>.yaml` with backward compatibility.

## Specification
1. **New module**: `science_cli/core/paths.py` with `ProjectPaths` class + `get_project_paths()` factory
2. **New YAML location**: `protocol/<name>/<name>.yaml` (inside protocol-named subdirectory alongside step dirs)
3. **Step dirs**: remain `protocol/<name>/<step>/`
4. **Backward compatibility**: `protocol_yaml()` checks new location first, falls back to old `protocol/<name>.yaml`
5. **Create command**: writes to new nested location
6. **All other commands**: read via fallback-aware `protocol_yaml()`
7. **Glob operations**: `list_protocol_yamls()` returns YAMLs from both locations (new first, no duplicates)
8. **Don't break existing tests or existing project layouts**

## Critical Analysis
- **Predicted output**: All protocol YAML reads transparently resolve from either old or new location. New protocols are created in nested format. Commands that list/glob protocols find both formats.
- **Consequences**: Existing projects with `protocol/<name>.yaml` continue working. Migration is opt-in (user moves the YAML). New projects use nested layout automatically.
- **Risks**: Circular imports (paths.py ↔ project.py) — mitigated by lazy import in factory function. `device_cli.py` has `_resolve_step_context` that hardcodes `f"{name}.yaml"` — needs updating.
- **Skepticism**: The `get_project_paths()` factory adds a dependency on `project.py` inside `paths.py`. This is fine because it's a lazy import (function body), not module-level.

## Approach
Centralize all path constructions. Keep changes minimal — replace path string construction with method calls, don't refactor unrelated code.

## Files to Modify (14 files)

### CREATE: `science_cli/core/paths.py`
- `ProjectPaths` class with: `protocol_dir`, `protocol_yaml()`, `protocol_yaml_new()`, `devices_yaml()`, `step_dir()`, `step_results_dir()`, `data_raw_dir()`, `results_dir()`, `list_protocol_yamls()`
- `get_project_paths()` factory

### MODIFY: `science_cli/core/project.py`
- Line 48: `project_status()` — count using `list_protocol_yamls()` equivalent (inline to avoid circular import)

### MODIFY: `science_cli/cli/commands/protocol.py`
- List: use `list_protocol_yamls()`
- Run: use `protocol_yaml()`
- Create: use `protocol_yaml_new()`, step dirs under `protocol/<name>/<step>/`
- Edit: use `protocol_yaml()`

### MODIFY: `science_cli/cli/commands/open_cmd.py`
- Line 58: use `protocol_yaml()`

### MODIFY: `science_cli/cli/commands/ls_cmd.py`
- `_ls_default`/`_ls_protocol`: use `list_protocol_yamls()`
- Step dir: already uses `py.stem` — compatible with both formats

### MODIFY: `science_cli/cli/commands/plot.py`
- `_get_results_dir`: use `protocol_yaml()`
- `_plot_interactive`: use `protocol_yaml()`
- `_plot_results`: use `list_protocol_yamls()` for glob replacement

### MODIFY: `science_cli/cli/commands/add.py`
- Use `protocol_yaml_new()` for writes, `protocol_yaml()` for reads, `list_protocol_yamls()` for globs
- Step dirs via `step_dir()`

### MODIFY: `science_cli/cli/commands/delete_cmd.py`
- Use `protocol_yaml()` for reads, `list_protocol_yamls()` for globs

### MODIFY: `science_cli/cli/commands/edit_cmd.py`
- Use `protocol_yaml()` for reads, `protocol_yaml_new()` for renames, `list_protocol_yamls()` for globs
- Step dirs via `step_dir()`

### MODIFY: `science_cli/cli/commands/analyze.py`
- `_get_results_dir`: use `protocol_yaml()`
- Sweep metadata: use `protocol_yaml()`

### MODIFY: `science_cli/cli/commands/results.py`
- Use `list_protocol_yamls()`

### MODIFY: `science_cli/cli/commands/project.py`
- `_project_migrate`: use `list_protocol_yamls()`

### MODIFY: `science_cli/core/file_utils.py`
- `get_results_dir`: use `protocol_yaml()`

### MODIFY: `tools/extensions/science-memristor/src/science_memristor/device_cli.py`
- `_resolve_step_context`: use `protocol_yaml()` for finding the parent protocol YAML
- `_resolve_protocol_dir`: use `protocol_dir` property or inline

## Dependencies
None — pure stdlib `pathlib`.

## Test Strategy
- Existing tests should pass (backward compatibility)
- Manual verification: create protocol with old CLI, verify new CLI finds it; create new protocol, verify nested structure
- No new test framework — project uses manual verification

## Branching
- [ ] No new branch needed (feature work, not breaking)

## Progress
- [x] PLAN created
- [x] User approved
- [x] IMPLEMENT done (14 files: 1 created, 13 modified)
- [x] TEST passed (15 tests covering both new/legacy formats, duplicate resolution, all path properties)
- [x] DOCS updated (README.md: added "Central Path Config" section with full API docs)
- [ ] COMMIT done
