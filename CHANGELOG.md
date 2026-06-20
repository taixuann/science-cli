# Changelog

All notable changes to science-cli will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.22.1] - 2026-06-21

### Fixed
- STP origin line in multi-cycle WGFMU files: NaN breaks at large time gaps (>10× median) prevent diagonal connecting lines through origin between cycles (plot/generic.py)

## [3.22.0] - 2026-06-20

### Added
- Universal filename grammar: `DDMMYY-HHMMSS_device-id_study_remarks_flags_count.csv`
- `core/grammar.py` with `parse_filename()` — right-to-left disambiguation parsing
- `Protocol.device` (top-level) + `ProtocolStep.instrument` (per-step) in protocol.yaml
- `sci add` auto-populates study, remarks, flags, count from parsed filename
- 7 global FZF columns: Step | DateTime | Device-ID | Study | Remarks | Flags | Count
  - Always shown before per-study metadata columns
  - Legacy files fall back to filename display

### Changed
- protocol.yaml: device moved to protocol level, instrument per step
- FZF display: structured columns replace raw filename (when convention is followed)

## [3.21.0] - 2026-06-20

### Added
- **Config-first plot parameters** — `core/plot_config.py:resolve_plot_config(study_name, device_type)` returns flat merged dict (theme → study → device). Per-study `plot:` blocks in `config-studies.yaml` define series colors, markers, sizes, annotations. Device-level `device_overrides.<device>.plot:` overrides per-device.
- **`plot:` blocks in all 13 studies** — pulse-endurance (3 series + 2 annotations), iv, ec, raman, uv-vis, afm. Device overrides for volatile-memristor (#2176AE) and non-volatile-memristor (#D64045/#1B998B).
- **Theme consolidation** — `config-template.yaml` is the single source for all theme definitions (publication-nature, publication-acs, tufte, dark, poster, matcha). `theme/plot-theme/*.yaml` and `theme/plot-templates/*.yaml` removed. `theme/registry.py:theme_to_rcparams()` reads from config.

### Changed
- **All 12 plot functions** now read styling from `resolve_plot_config()` instead of hardcoded values. CLI flags still override. Pattern: `flags.get("color", plot_cfg.get("series.hrs.color", "#CC0000"))`.
- **`data_loader.py`** — auto-resolves `study_name` from `technique` via `resolve_legacy_technique()`. Wires pulse studies through the study-aware metadata pipeline.
- **`config.py:_resolve_device_config()`** — study-level columns win over instrument-registry defaults (fixes WGFMU column remapping for pulse studies).
- **`get_metadata_config_for()`** — fixed to check `instruments.<inst>.metadata` path instead of `metadata_extractors` (Phase 9 scoping fix).
- **`config/config.yaml`** — `default_dpi: 300` → `default_dpi: 600`.
- **`config/config-studies.yaml`** — added WGFMU column maps (`time→Time, voltage→MeasResult1_value, current→MeasResult2_value`) to pulse-stp-decay, pulse-ppf, pulse-endurance, pulse-retention.
- **`config/config_schema.py`** — `validate_template_config()` exempts `plot_labels`/`plot_techniques` from theme-specific required-field checks.

### Removed
- `theme/plot-theme/` (7 yaml files) — consolidated into `config-template.yaml`.
- `theme/plot-templates/` (8 yaml files) — replaced by per-study `plot:` blocks in `config-studies.yaml`.

### Fixed
- `test_load_keysight_stp_column_remap` — columns now correctly remap `MeasResult1_value` → `voltage` for pulse studies.
- `test_generate_template_yaml_is_valid` — schema no longer requires theme fields on non-theme templates.
- `test_keysight_iv_metadata_in_info` — metadata config resolved via `instruments.<inst>.metadata` path.

### Tests
- 572 passed, 4 pre-existing failures (migration script, technique detection, electrochem device type).
- 0 new regressions from config-first plot params merge.

## [3.20.0] - 2026-06-20

### Added
- **Waveform 2D pattern detection** — `detect_waveform_pattern_2d()` returns canonical `[[t, v], ...]` array (subsampled to 200 points). `extract_waveform_metadata()` orchestrator combines 2D pattern + derived scalars. Wired into `data_loader.py:_load_with_device_config()` — when `data_shape.kind == "waveform_2d"`, injects `waveform_pattern` + scalars into `analysis_meta`.
- **fzf subpackage** — `core/fzf/` created with `__init__.py`, `columns.py` (from `core/fzf_columns.py`), `display.py` (from `core/fzf_utils.py`).
- **(study, device) scoping for fzf columns** — `STUDY_COLUMN_REGISTRY` re-keyed to `dict[tuple[str, str | None], list[str]]` with `(study, device_type)` tuple keys. `get_columns_for(study, device_type)` helper with fall-through. `get_step_columns()` and `build_fzf_display()` accept `device_type` parameter.
- **Metadata parser/analyzer subpackages** — `core/metadata/` split into `core/metadata/parsers/` (keysight, keithley, raman, waveform) and `core/metadata/analyzers/` (iv, waveform). `core/metadata/__init__.py` imports from subpackages.
- **(study, instrument) scoping** — `get_metadata_config_for(study, instrument, device)` in `config.py`. `data_loader._load_with_device_config()` uses it for (study, instrument)-aware config resolution.
- **New tests** — 10 waveform 2D tests + 14 (study, device) scoping tests.

### Changed
- **`STUDY_COLUMN_REGISTRY`** re-keyed from `dict[str, list[dict]]` to `dict[tuple[str, str | None], list[str]]` — keys are now `(study, device_type)` tuples with device-specific fall-through.
- **`get_columns_for(study, device_type)`** replaces direct registry lookups; handles missing device entries by falling through to `(study, None)`.
- **`get_step_columns()` and `build_fzf_display()`** accept `device_type` parameter for per-device-type column selection.
- **`data_loader._load_with_device_config()`** uses `get_metadata_config_for()` for (study, instrument)-aware config resolution.
- **STP and endurance studies** now get `waveform_2d` data_shape when waveform 2D pattern is detected.
- Updated 27 importer files for fzf subpackage migration.

### Removed
- `core/metadata/keysight.py`, `core/metadata/keithley.py`, `core/metadata/raman_header.py`, `core/metadata/waveform.py` — split into `parsers/` + `analyzers/` subpackages.
- `core/fzf_columns.py`, `core/fzf_utils.py` — replaced by `core/fzf/` subpackage.

### Tests
- **572 passed** (was 547 in v3.19.0), 4 pre-existing baseline failures.
- 10 new tests for waveform 2D detection + 14 new tests for (study, device) scoping.

## [3.19.0] - 2026-06-19

### Added
- **Per-study fzf columns** — `science_cli.core.fzf_columns.STUDY_COLUMN_REGISTRY` maps each study name to its fzf metadata columns. Pulse studies show pattern-waveform fields (V_set/V_read/set_width/read_width/rise/fall), IV-bipolar shows sweep pattern + compliance + step + delay, EC shows electrochem-specific keys, Raman/UV-Vis show optical keys.
- **`status_badge_for_file(file_key, status_dict)`** — single-char badge (★/✓/✗) for fzf display, replacing the longer `[HIGHLIGHT]` text labels. Honors all status tags (keep/highlight/discard/star) with no-badge for `clear`/missing.
- **`get_step_columns(project_root, step_name, study_name)`** — reads step metadata from `protocol.yaml` and returns only the registry's column keys in registry order.

### Changed
- **`build_fzf_display()`** now accepts `study_name` and `status_badge` kwargs. When `study_name` matches a registry entry, only the registered columns are shown (compact `width_meta=12`). All existing call sites remain backward compatible.
- **`sci plot`** and **`sci analyze`** (default fzf path) now show per-study metadata columns + status badge in their file selection UI.
- **`sci results`**, **`sci pulse list`** — same treatment.

### Removed
- Duplicate `get_step_columns` from `protocol.py` (canonical home is now `fzf_columns.py`).

### Fixed
- 3 status test mocks updated to match the new `show_protocol=False` display format with badge prefixes.

### Tests
- New `tests/test_core/test_fzf_columns.py` — 21 tests covering registry shape (5 studies + 4 EC sub-tests), status badges (6 tag cases), `get_step_columns` (4 cases incl. unknown step, no study filter, registry filter), and `build_fzf_display` study-aware behavior (6 cases incl. backward compat, badge prepend, registry column filter, unregistered study fallback).
- 3 status tests in `test_status.py` updated.
- **547 passed**, 4 pre-existing baseline failures (unrelated: config defaults, migration script, electrochem device-type, library resolution).

## [3.18.0] - 2026-06-19

### Added
- **Status tags** (`results --status <tag>`, `serve` API + dashboard click-to-cycle)
  - Tags: `keep`, `highlight`, `discard`, `star`, `clear` (remove)
  - Stored in `<project>/results/.status.json` (auto-migrates from legacy `.stars.json`)
  - Serve API: `GET /api/status`, `POST /api/status` (body: `{file_key, tag}`)
  - Dashboard: 2-sec polling overlay for badge updates on lazy-loaded gallery items
- **`pulse:pulse-endurance` re-added** with device-type variants
  - Volatile: R_decay vs cycle, log-log
  - Non-volatile: 2-panel R_high + R_low, log-log
  - X-log scale, big markers, cycle-based coloring
- **`pulse list`** — lists pulse steps from `protocol.yaml` with metadata columns
- **`pulse overlay`** — case-study overlay plot
  - Tolerance-based numeric grouping (default ±5% of median)
  - Exact string matching for non-numeric
  - Color per group, legend by variable value
  - Output to file or display
- **Auto-write metadata** to `protocol.yaml` after analysis
  - STP, endurance, IV bipolar, PPF all write waveform + analysis results
  - New `merge_analysis_to_metadata()` helper in `core/analysis_output.py`
  - Atomic write via `_atomic_write_yaml()` (temp file + os.replace)
- **Architecture ref**: device ↔ study relationship documented in `.lavish/artifacts/160626c_device-study-relationship.md`
  - Device types: `volatile-memristor`, `non-volatile-memristor`
  - Studies: `pulse:pulse-stp-decay`, `pulse:pulse-endurance`, `pulse:pulse-ppf`, `iv:iv-bipolar-sweep`

### Changed
- `results.py` refactored: imports from `results_status` module, `--status` flag replaces `--star` (legacy still works)
- `plot/pulse_endurance.py` rewritten with device-type dispatch
- `core/protocol.py` extended with metadata write helpers
- `library/iv/bipolar.py`, `library/pulse/ppf.py` — added `metadata`/`project_root`/`step_name` params

### Tests
- 26 new tests in `tests/test_core/test_status.py`
- 13 new tests in `tests/test_plot/test_pulse_endurance.py`
- 27 new tests in `tests/test_core/test_pulse_overlay.py`
- Tests for IV bipolar + PPF metadata write (Seq 4)

## [3.15.0] - 2026-06-16

### Added
- **STP-decay study wiring** for volatile-memristor on keysight-b1500a:
  - New grammar pattern `rN-cN-stp-decay` for files like `150626_cu-c-pda(q5)-ito_r5-c2_stp-decay_041_important.csv`
  - `analyze_waveform_params` — extracts V_set, V_read, set pulse width, read pulse width, rise/fall time, and repeat pattern via histogram peak detection on voltage-time data
  - `detect_repeat_pattern` — detects single vs repeated sweep patterns
  - `invert_current_sign` — flips Keysight B1500A current sign (convention is negative)
  - `parse_setup_pulses` — best-effort header scanner for explicit pulse parameters
  - New module: `science_cli.core.metadata.waveform`
  - YAML analysis output now includes `waveform` section with pulse parameters
- 20 new tests in `tests/test_metadata/test_waveform.py`

### Changed
- `analyze_stp_decay_to_yaml` accepts `metadata` parameter

## [3.16.0] - 2026-06-17

### Added
- **Device-type-aware plot dispatch**: `StudyPlotter` now supports `device_variants` dict for per-device-type plot behavior
- **`--device-type`/`-dt` flag** on `plot` and `analyze` commands for explicit device-type override
- **`_detect_device_type()` auto-detection**: resolves device type from CLI flag → protocol YAML → reverse study lookup
- **`pulse:pulse-endurance` device-type variants**: volatile and non-volatile stubs registered in plot registry
- **`_DEFAULT_GLOBAL_TECHNIQUES` completed**: added `ec-cv`, `ec-ca`, `ec-eis`, `pulse-endurance`, `pulse-retention` entries

### Changed
- `resolve_study_plotter()` now accepts `device_type` parameter for variant resolution
- `_resolve_device()` in both `plot.py` and `analyze.py` accepts `study_name` for instrument fallback
- `get_default_device()` accepts `study_name` for study-level instrument resolution
- `_resolve_device()` extracted from `plot.py`/`analyze.py` to shared `core/device_resolver.py` — eliminates code duplication across both CLI modules and `plot/eis.py`, `plot/ca.py`, `plot/cv.py`

### Fixed
- **`ec-cv` vs `iv-sweep` pattern collision**: removed CV-pattern overlap from `iv-sweep` technique patterns

### Internal
- Phase 1: Registry data model + detection foundation (code-heavy)
- Phase 2: Config completion + resolve_device enhancement (code-medium)
- Phase 3: Dispatch threading + endurance variants (code-heavy)
- Phase 4: Tests + help text + documentation (code-medium)

## [3.14.0] - 2026-06-16

### Changed
- **plot --help cleaned up**: Removed per-study subflags from GROUP 2 — STUDIES display (except --gradient/--cmap for iv-bipolar-sweep, --describe for stp-decay/ppf)
- **fzf metadata columns**: `build_fzf_display()` now supports optional `metadata: dict` parameter for metadata-enhanced display
- **Interactive plot style form**: Post-fzf prompts replaced with single multi-field form for name, label, markersize, color, linewidth, linestyle, marker, dpi, grid, legend (Enter=default)

### Fixed
- **Removed deleted studies from plot --help**: `pulse:pulse-endurance` and `pulse:pulse-retention` no longer appear in `plot --help` (were removed from config but still listed)

### Internal
- Trimmed STUDY_FLAGS in plot/registry.py — _RAMAN_FLAGS, _UV_VIS_FLAGS, _CV_FLAGS, _EIS_FLAGS, _AFM_FLAGS cleared (study-specific flags moved to analyze context)

## [3.13.0] - 2026-06-16

### Added
- **Plot restructure: study-registered plotter dispatch** (Phases 0-6):
  - `plot/registry.py` — `StudyPlotter` dataclass, `STUDY_PLOTTERS` dict, `resolve_study_plotter()`, `register_study_plotter()`, `list_study_plotters()`, all study flag definitions, `_init_dedicated_plotters()` lazy init
  - `plot/base.py` — `apply_figure_kw()`, `create_figure()`, `parse_figsize()`, `save_figure()`, `plot_line()`, `plot_scatter()`
  - `plot/iv.py`, `plot/stp.py`, `plot/eis.py`, `plot/raman.py`, `plot/uv_vis.py`, `plot/cv.py`, `plot/ca.py`, `plot/ppf.py`, `plot/pulse_endurance.py`, `plot/pulse_retention.py`, `plot/afm.py` — per-study plot/overlay functions
  - `plot/overlays.py` — `plot_overlay()` using base.py helpers (deduplication complete)
- **`cli/commands/plot.py` thinned from 1599→~935 lines** — dispatch routes via `STUDY_PLOTTERS` registry; generic `_do_plot()`, `_do_overlap()` preserved as fallback
- **Per-study overlay layouts** — `single_layout` and `overlay_layout` fields on `StudyPlotter`; STP/PPF use `1x2_panels`, EIS uses `nyquist_bode`, rest use `single_axis`
- **Universal `--describe` support** — `_show_describe()` works for any study/technique via metadata pipeline; `sci plot file.csv -s pulse:stp-decay --describe` or `--describe rise_us,set_width_us`
- **`core/metadata/` subsystem** — `ANALYSIS_REGISTRY` + `run_analysis()` + `extract_metadata()` pipeline; Keysight B1500A parsers (`parse_set_voltage`, `parse_compliance`, `parse_sweep_range`, `parse_repeat_count`) and analyzers (`analyze_waveform_params`, `analyze_iv_compliance`); Keithley 2400 minimal parsers; `raman_header.py` extracted from `data_loader.py`

### Changed
- `StudyPlotter` dataclass now has `single_layout` (default: `"single_axis"`) and `overlay_layout` (default: `"single_axis"`) fields
- `cli/commands/plot.py` — `_resolve_xy_columns()` no longer pre-assigns unused `cols` variable; `plot_handler()` routes `--describe` to `_show_describe()` for any study
- `plot/__init__.py` — removed duplicate function definitions (all re-export from `base.py`); removed unused imports

### Fixed
- `plot/__init__.py` no longer redefines `setup_backend`, `create_figure`, `apply_figure_kw`, `parse_figsize`, `save_figure` (were duplicated from `base.py`)
- `plot/overlays.py` now imports from `base.py` instead of duplicating helpers

### Internal
- **Phase 0+1+2**: Registry + plotters + thin dispatch (tools-code-heavy)
- **Phase 3**: Per-study overlay layouts (tools-code-medium)
- **Phase 4**: `core/metadata/` analysis pipeline (tools-code-medium — parallel track)
- **Phase 5**: CLI flag consolidation, universal `--describe`, dynamic help (tools-code-medium)
- **Phase 6**: Backward compat shims (`-t` still accepted) (tools-code-light)

## [3.12.0] - 2026-06-15

### Added
- **Config split: monolithic `config.yaml` → 4 modular files** (Phases 0-8):
  - `~/.config/science-cli/config-devices.yaml` — studies + device types (merged)
  - `~/.config/science-cli/config-instruments.yaml` — instrument model registry
  - `~/.config/science-cli/config-grammar.yaml` — filename naming grammar
  - `~/.config/science-cli/config-template.yaml` — theme templates
- **`core/config_defaults.py`** — 4 YAML generation functions, one per modular file
- **`core/config_schema.py`** — YAML schema validators for each config file
- **`core/studies.py`** — New study domain model with 18 functions: `Study` dataclass, `detect_study_from_filename()`, `resolve_technique_from_study()`, `resolve_library_from_study()`, `get_study_config()`, `get_studies_for_device_type()`, `list_studies()`, `render_study_table()`, and legacy technique resolution
- **`scripts/migrate-config-to-modular.py`** — One-time migration script: reads old `config.yaml`, generates 4 modular files, creates backup
- **`init` standalone command** — `sci init` generates all 4 modular config files (was `sci config init`)
- **`-s/--study` flag** — New canonical study-aware flag on `plot`, `analyze`, `add`, `edit`. Accepts study IDs like `iv:iv-bipolar-sweep`. Studies resolve to techniques and libraries automatically. Old `-t/--technique` still accepted with deprecation notice.
- **`ls -m study|instrument|device|grammar`** — New list modes replacing `config list *`:
  - `ls -m study [<name>]` — list/filter studies with technique and instrument columns
  - `ls -m instrument [<name>]` — list/filter instruments with type/manufacturer columns
  - `ls -m device [<name>]` — list device types
  - `ls -m grammar` — list filename grammar patterns
- **`edit -m study|instrument|device|grammar`** — New edit modes replacing `config edit *`:
  - `edit -m study <name>` — opens config-devices.yaml in $EDITOR
  - `edit -m instrument <name>` — opens config-instruments.yaml in $EDITOR
  - `edit -m device <name>` — opens config-devices.yaml device section
  - `edit -m grammar` — opens config-grammar.yaml in $EDITOR
- **Config 7-layer resolution** — `load_global_config()` now merges across: hardcoded defaults → old `config.yaml` (backward compat, warns) → 4 modular files → per-project `sci-config.yaml` → per-protocol grammar
- **Study-aware filename detection** — `detect_study_or_technique()` tries study patterns first, falls back to legacy technique patterns
- **Study-aware data loading** — `load_data_file()` accepts `study_name` parameter for study→technique→instrument→config resolution chain
- **48 new tests** in `tests/test_core/test_studies.py` covering study detection, resolution, rendering
- **`instrument register/edit/rm`** — now writes to `config-instruments.yaml` instead of old `config.yaml`'s `devices:` section

### Changed
- **`core/config.py`** — 7-layer config resolution replaces 4-layer monolithic loading. 9 new study-aware accessors added. All 32+ existing public functions kept with full backward compat. `get_device_config()` accepts optional `study_name`.
- **`core/technique.py`** — Added `detect_study_or_technique()`. `_config_patterns()` loads study patterns. `standardize_grammar_fields()` preserves `study` field alongside `technique`.
- **`core/routing.py`** — `resolve_library()` accepts optional `study_name`. New `resolve_study_library()` and `load_device_types_config()`.
- **`core/data_loader.py`** — `load_data_file()` and `_resolve_device_config()` accept `study_name` for study→technique→instrument resolution.
- **`cli/commands/plot.py`** — `-s/--study` flag support throughout dispatch chain. Study detection in `_detect_technique()`.
- **`cli/commands/analyze.py`** — `-s/--study` flag, technique derived from study.
- **`cli/commands/add.py`** — `-s/--study` flag, stores `study` field in step metadata.
- **`cli/commands/edit_cmd.py`** — `-s/--study` flag in protocol/metadata editing.
- **`cli/commands/config.py`** — Deprecation warning for redirected subcommands (still works).
- **`cli/commands/instrument.py`** — Deprecation warning for `sci instrument` command (still works).
- **`cli/help.py`** — Updated with `init`, `-s/--study`, `ls -m` and `edit -m` documentation.
- **`library/instruments/registry.py`** — `register_instrument()`/`remove_instrument()`/`edit_instrument()` write to `config-instruments.yaml`.
- **`library/iv/device_cli.py`** — `--study` flag in CLI argument parser.

### Deprecated
- **Monolithic `~/.config/science-cli/config.yaml`** — Read if exists with migration warning. Use `scripts/migrate-config-to-modular.py` to split.
- **`sci config` subcommands** (`list`, `edit`, `show`, `init`, `devices`, `grammar`, `set`) — Redirect to `ls -m`/`edit -m`/`init` respectively. Removal in v4.0.0.
- **`sci instrument`** — Redirect to `ls -m instrument`/`edit -m instrument`. Removal in v4.0.0.
- **`-t/--technique` flag** — Use `-s/--study` instead. Still accepted with backward compat. Removal in v4.0.0.
- **`core/config.py:_DEFAULT_TECHNIQUE_PATTERNS`** — Use study patterns from `config-devices.yaml`.
- **`core/config.py:_DEFAULT_TECHNIQUE_DEVICES`** — Use study instrument configs from `config-devices.yaml`.
- **`core/config.py:_DEFAULT_GLOBAL_DEVICES`** — Use `config-instruments.yaml`.
- **`core/config.py:_DEFAULT_GLOBAL_TECHNIQUES`** — Use study definitions from `config-devices.yaml`.
- **`core/technique.py:PATTERNS`** — Duplicate of `_DEFAULT_TECHNIQUE_PATTERNS`.
- **`core/technique.py:BUILTIN_TECHNIQUES`** — Use study model from `core/studies.py`.
- **`core/technique.py:HARDCODED_GRAMMAR`** — Use `config-grammar.yaml`.

### Fixed
- **Duplicate hardcoded data eliminated** — `PATTERNS` (technique.py) = `_DEFAULT_TECHNIQUE_PATTERNS` (config.py), `BUILTIN_INSTRUMENTS` (registry.py) ≈ `_DEFAULT_GLOBAL_DEVICES` (config.py), `BUILTIN_TECHNIQUES` (technique.py) ≈ `_DEFAULT_GLOBAL_TECHNIQUES` (config.py). All consolidated into single-source-of-truth in `config_defaults.py` with backward-compat shims.
- **`TECHNIQUE_PLOTTERS` decorative registry** — Now study-aware dispatch chain uses `resolve_library_from_study()` instead of hardcoded if/elif in `_dispatch_technique_plot()`.

### Internal
- **Phase 0**: 4 config files + `init` + migration script (tools-code-heavy)
- **Phase 1**: `core/studies.py` domain model (tools-code-heavy)
- **Phase 2**: `core/config.py` 7-layer resolution refactor (tools-code-heavy)
- **Phase 3**: `core/technique.py` study-aware detection (tools-code-medium)
- **Phase 4**: `core/routing.py` + `core/data_loader.py` study routing (tools-code-medium)
- **Phase 5**: CLI `--study` flag + `ls -m`/`edit -m` modes (tools-code-heavy)
- **Phase 6**: Instrument registry → `config-instruments.yaml` (tools-code-medium)
- **Phase 7**: Library harmonization (tools-code-medium)
- **Phase 8**: `sci-skill/` created — AI-consumable documentation (SKILL.md, COMMANDS.md, CONFIG.md, STUDIES.md, INSTRUMENTS.md, PLOTTING.md, ANALYSIS.md, WORKFLOWS.md)

## [3.11.0] - 2026-06-14

### Added
- **`sci results --move` / `-m`**: FZF multi-select result files across all protocol steps; creates symlinks in `project/results/` with auto-rename on name collision
- **`sci analyze -t`/`--technique` system**: FZF file selection routes to technique-specific analyzers via `TECHNIQUE_ANALYZERS` registry (13 entries). Per-technique flags: `--peaks`, `--baseline` (raman), `--bandgap` (uv-vis), `--vset-only`, `--compliance` (iv-sweep), `--roughness` (afm), `--fit-model` (pulse-stp), `--intervals` (pulse-ppf). Flag validation warns on mismatched technique flags.
- **Plot help layout**: 3-column Rich Table (Command | Description | Flags) with per-technique rows; THEME sections with 10+ flags auto-render in 2-3 Rich Columns

### Changed
- `-d`/`--device` flag renamed to `--ins`/`--instrument` in `sci add -m protocol` and `sci edit -m protocol`. Old `-d`/`--device` still accepted with deprecation warning.
- Per-step YAML field `device:` renamed to `instrument:` with backward-compat fallback
- Auto-technique assignment: `--ins <name>` without `-t` auto-detects technique from instrument registry

### Deprecated
- `sci raman analyze`, `sci uv-vis analyze`, `sci afm analyze` — use `sci analyze --technique <name>` (removal in v4.0.0)
- `-d`/`--device` flag on `sci add -m protocol` and `sci edit -m protocol` — use `--ins`/`--instrument` (removal in v4.0.0)

## [3.10.0] - 2026-06-13

### Added (Technique Restructuring — Phases 0-6)
- **Phase 0: Test infrastructure** — 6 synthetic test projects in `active_projects/test-projects/` covering IV, pulse, PVD, UV-Vis, STP/PPF, and multi-device scenarios. Test fixtures in `tests/conftest.py`. 214 total tests (from 78).
- **Phase 1: Technique restructuring** — `sci memristor` split into `sci iv` (DC sweep analysis) and `sci pulse` (pulse measurements). New commands: `sci iv` (ls, info, plot, analyze, sync, dashboard), `sci pulse` (endurance, retention, switching, STP, PPF), `sci pvd` (deposition records). Deprecated `sci memristor` as a compat shim (prints deprecation warning, auto-dispatches to iv/pulse).
  - `library/iv/` — device_cli.py, plotting.py, switching.py, metrics.py, volatile.py, bipolar.py
  - `library/pulse/` — device_cli.py, endurance.py, retention.py, switching.py, models.py, plot.py, analyze.py, stp.py, ppf.py
  - `library/pvd/` — device_cli.py, models.py, analyze.py, yaml_io.py
  - Technique patterns renamed: `mem-*` → `pulse-*` (with backward-compat aliases)
- **Phase 2: Unified plotting** — `sci plot --technique <name>` / `-t` flag for explicit technique context. Technique-specific flags unlocked via `--technique` (raman: `--laser`, `--accumulation`, etc.; ec: `--scan-rate`, `--cycles`; uv-vis: `--wavelength-range`; afm: `--cross-section`, `--colormap`). Per-technique `plot` subcommands (raman, ec, uv-vis, afm) deprecated.
- **Phase 3: Instrument command + protocol `devices:` field** — `sci instrument` / `sci ins` command group (ls, info, register, edit, rm, assign, protocol). `library/instruments/` backend (registry.py, types.py, models.py). Protocol-level `devices:` field in YAML. `core/routing.py` for device-type-aware library dispatch. CLI flags: `--ins` (per-step instrument) and `--devices` (per-protocol device type).
- **Phase 4: Per-technique YAML schemas** — `core/analysis_output.py` shared writer producing `results/<technique>_analysis.yaml`. `analysis/validators.py` with mode-aware schema validators (volatile vs bipolar IV). `sci analyze --yaml` flag. Schemas for IV sweep, pulse endurance, pulse STP, pulse PPF, Raman, UV-Vis, PVD, AFM.
- **Phase 5: 5-tier config grammar system** — Filename grammar resolves across hardcoded defaults → global config → device-type grammar → per-protocol grammar → per-step grammar. Protocol grammar section read/write in `core/protocol.py`. Device-type grammar registry in `core/config.py`. `sci config grammar test <pattern>` command.
- **Phase 6: Categorized config --help** — `sci config --help` groups subcommands into GLOBAL / THEME / TECHNIQUE / INSTRUMENT / GRAMMAR categories with sub-headers.
- **New CLI commands**: `sci iv`, `sci pulse`, `sci pvd`, `sci instrument` (+ `sci ins` alias)

### Changed
- `sci memristor` deprecated — prints warning and dispatches to `sci iv` or `sci pulse`
- `sci raman plot`, `sci ec plot`, `sci uv-vis plot`, `sci afm plot` deprecated — use `sci plot --technique <name>` instead
- `library/memristor/` is now a compat shim re-exporting from `library/iv/` and `library/pulse/`
- Architecture document updated with 4 new library modules and analysis directory

### Deprecated
- `sci memristor` — use `sci iv` or `sci pulse` (removal in v4.0.0)
- `library/memristor.*` imports — use `library.iv` or `library.pulse` (removal in v4.0.0)
- `sci {raman,ec,uv-vis,afm} plot` — use `sci plot --technique {name}` (removal in v4.0.0)

### Added
- **Neurophase IV plot: V_set/V_reset detection markers** — Red (V_set) and blue (V_reset) triangle markers on IV curve traces, showing exactly where switching was detected. Only V_set shown for volatile devices (no V_reset). Filename shown in sidebar.
- **`afm open`** — Interactive AFM analysis: open .ibw files in Gwyddion, record thickness, roughness (Sa/Sq), and material; skips if empty input, saves to afm_analysis.yaml in the step directory

## [3.2.0] - 2026-06-02

### Added
- **Memristor Plotting Flags & Prompts**: Integrated custom Matplotlib styling parameter forwarding (`color`, `linestyle`, `linewidth`, `marker`, `markersize`, `zoom`, `grid`, `legend`) and theme overrides into `sci memristor plot`. Implemented interactive prompts for "Style / analysis options" and "Figure options" in FZF mode.
- **Protocol-Aware FZF Filtering**: Programmed FZF file selection to parse technique configurations from active protocol YAMLs for `raman`, `uv-vis`, and `ec` commands. The displayed list dynamically narrows to active protocol files mapping to matching techniques (`raman`, `uv-vis`, or starting with `ec-`), falling back to all raw files if no active protocol matches.
- **Automated Testing Coverage**: Added a comprehensive test suite `tests/test_core/test_fzf_technique_filtering.py` verifying protocol-aware FZF technique filtering under active protocol scopes.

### Changed
- **Plotting Fixes & Background Automation**: Resolved undefined `rprint` error in `raman.py`, enabled automatic FZF selection bypass when `--all` or `--overlay` is supplied in CLI args, and configured automated plotting modes to automatically save figures (`raman_<file_stem>.pdf` or `raman_overlay.pdf`) to results, avoiding GUI popup freezes.
- **Reverted Explicit --fzf Flag**: Reverted the redundant `--fzf` plot subcommand argument in `device_cli.py` while preserving interactive prompts and FZF file selection when positional arguments are omitted.

## [3.1.0] - 2026-06-02

### Added
- **Symmetric Characterization Plotting**: Fully aligned specialized plotting namespaces (`sci ec plot`, `sci uv-vis plot`, and `sci raman plot`) with the global `sci plot` capabilities. Added support for `--all` and `--overlay` flags in each namespace.
- **Robust FZF Protocol Filtering & Fallback**: Designed and implemented a smart intersection between technique-specific files and active protocol mapping. If technique files exist in the active protocol, FZF displays only those files; if none are assigned, it gracefully falls back to showing all raw files of that technique.
- **Technique Boundaries Check**: Symmetrical, strict validation gates in all specialized plot handlers (`ec`, `uv-vis`, and `raman`) preventing cross-technique file processing.
- **Safe Pandas Coercion in Raman Plotting**: Implemented robust numeric casting using `pd.to_numeric(..., errors='coerce')` in `raman.py` to prevent numpy `isnan` TypeErrors when loading custom textual file layouts with headers.

### Changed
- **Aligned Raman Plot Handler**: Restructured `_raman_plot` to match the clean, unified `(args: list) -> None` CLI handler signature, removing the complex `"--fzf"` internal flag and aligning it perfectly with `_ec_plot` and `_uv_plot`.
- **Simplified File Stripping**: Replaced regex column stripping with a clean, bulletproof `.split()[-1]` last-token extraction method to resolve filenames from FZF selections, regardless of column formatting.

## [3.0.0] - 2026-05-31

### Added
- **Premium React/Vite Frontend (`sci serve`)**: Full AI Studio-generated frontend with dynamic project switching, integrated Plotly dashboard, protocol/step navigation, gallery with PDF/PNG/SVG rendering, and lightbox viewer
- **Live Dashboard View on `sci serve`**: Crossbar heatmap with per-cell KPI overlay (Vset/Vreset/ON-OFF ratio), click-to-load IV curves, device-type classification display, histograms for Vset/Vreset/Ratio distributions
- **Multi-Cycle Highlight Plotting**: `generate_iv_highlighted_svg()` — highlight specific sweep cycles in color with grey background traces, Vset/Vreset annotations in legend, publication-Nature themed
- **Raw Current Plotting Support**: `raw_current` flag on `generate_iv_svg()` and `generate_iv_overlay_svg()` to disable automatic log-scale detection, preserving raw linear-scale current visualization
- **Device Classification & Materials DB**: SQLite materials table with `classify_and_populate_materials()` — automated device-type classification (volatile/short/non-volatile) based on Vset/Vreset/ratio heuristics
- **Device CLI (`memristor device`)**: Per-cell device-type override commands (`set-device-type`, `set-device-errors`) and matrix display with device-type coloring
- **Subcommand Grouped Help Menu**: `memristor` subcommands grouped by category with cleaner AI Studio-friendly output
- **Numpy Import Fix**: Robust numpy import handling in classification module
- **Manual Device Overrides**: CLI flags for overriding detected device classification per cell
- **`ls_cmd.py` Sorting/Search**: Improved step file listing with configurable sort and search
- **New Documentation Artifacts**: 9 planning and walkthrough documents for serve frontend, multi-cycle plot, device CLI, and raw plotting

### Changed
- **`sci serve` API Refactored**: Switched from `get_protocol_files()` to comprehensive `get_dashboard_data()` endpoint with SQLite-first, cache-fallback strategy — serves heatmap, histograms, device type breakdown, and KPI aggregates in a single call
- **Frontend Assets**: Replaced single-page gallery frontend with premium React/Vite bundled frontend (`index-DvsT4CeK.js`, `index-rv64M7Al.css`)
- **PDF Rendering**: PDF iframes now append `#toolbar=0` to hide native browser toolbars; PDFs/SVGs/PNGs natively scale to 100% canvas width and height
- **Gallery Layout**: Split gallery thumbnails into "Overlays & Summaries" (warm gold) and "Individual Sweeps" (indigo) categories with distinct styling
- **MIME Type Handling**: Custom `guess_type()` override in server guarantees correct JS/CSS MIME types for frontend assets
- **CLI Flags Cleanup**: Consolidated and cleaned up `memristor` CLI flags for consistency
- **`edit_cmd.py`**: Protocol edition path resolution improvements

### Fixed
- **Frontend Blank Page on React**: Resolved premium frontend blank page and file loading bugs
- **System Directory Filtering**: `__pycache__` and system directories filtered out from projects workspace list in serve API
- **PDF Thumbnail Magnifier Overflows**: Replaced PDF iframe thumbnails with custom SVG document icons in sidebar
- **Duplicate `_api_protocol_files` handler**: Missing handler for protocol file listing API endpoint restored
- **Test Suite**: Added `TestDbMaterialsAndClassification` tests for materials CRUD and device-type heuristics

## [2.0.0] - 2026-05-13

### Breaking Changes
- Removed `project` command. Use `ls -m project`, `open -m project`, `add -m project`, `status -m project` instead
- Removed `project migrate` subcommand. Nested protocol layout is now the default
- Session state format changed to support 3-level memory (step, protocol, project)
- Removed `memristor` alias. Use `memristor <subcommand>` directly
- Removed `extensions` top-level command. Use `ext list` instead
- Removed all `--filter` CLI flags. Use `--fzf` for interactive selection
- `config` command now uses `set technique` instead of inline technique config
- Version reset from 7.0.0 to 2.0.0 reflecting actual feature maturity

### Added
- **Textual TUI**: Interactive terminal UI with SCI banner, matcha green theme, command echo with timestamps, slash commands (/help, /clear, /history, /version)
- **Plotly Interactive Dashboard**: Self-contained `dashboard.html` with zoom, pan, hover tooltips, click-to-expand cells, filter by material/sweep/cycle, PNG export — no server required
- **Cross-Protocol Dashboard**: `memristor dashboard --all` aggregates IV data from ALL protocols with per-protocol stacked heatmaps, material filter, toggleable Vset/Vreset markers
- **Analysis Cache**: `analysis_data.json` with mtime tracking for incremental re-analysis
- **Extension Integration**: science-memristor merged into core (`src/science_cli/memristor/`), science-iv recovered from .pyc (`src/science_cli/iv/`), science-electrochem recovered from .pyc (`src/science_cli/electrochem/`)
- **CSV/TXT Format Support**: Reader for Keithley 2400 tab-separated format and Clarius+ CSV
- **Vset/Vreset Extraction**: Derivative-based IV parameter extraction with abrupt and gradual switching detection
- **ON/OFF Ratio Computation**: Per-sweep resistance ratio with configurable V_read
- **File Management**: `close -m project|protocol|step` with auto-save, `open -m step <id>` for step-level context
- **Config Expansion**:
  - Per-technique YAML config files at `~/.config/science-cli/techniques/<technique>.yaml`
  - Per-project device overrides at `<project_root>/devices.yaml`
  - `config set technique <name> <device>` — set default device for technique
  - `config edit <technique>` — open technique config in $EDITOR
  - `config list techniques` — list all configured techniques
  - `config list devices <technique>` — list devices for a technique
- **Parquet Support**: Processed features stored as `.parquet` files
- `CHANGELOG.md` — initial changelog following Keep a Changelog

### Changed
- `ls -m project` replaces `project list`
- `open -m project` replaces `project open`
- `add -m project` replaces `project create`
- `status -m project` replaces `project status`
- Commands reorganized into 4 groups: File Management, Context Navigation, Data Analysis, Extensions & Techniques
- `ext` is now the unified extension interface (replaces standalone `memristor`, `extensions`)
- Help menu now shows commands organized by group with descriptions
- TUI REPL prompt simplified to `sci>`
- TUI output now shows `> <command>` with right-aligned timestamp on single line
- `config` command updated with technique management subcommands
- All plots default to interactive Plotly (SVG generation removed)

### Removed
- `project` command and all subcommands
- `project migrate` subcommand
- `memristor` alias removed (use `memristor` directly)
- `extensions` top-level command (use `ext list`)
- All `--filter` CLI flags across all commands
- Dead code: `image.py`, `general.py`, `functions/` directory
- SVG-based dashboard generation (replaced by Plotly)
- `project.py` orphan handler

### Fixed
- TUI output format: command echo and timestamp now on one line
- Help table column alignment for grouped display
- Session state now persists across close/open cycles
- Extension entry points with non-callable handlers silently skipped

### Security
- No authentication or network features — all operations are local filesystem

## [2.1.0] - 2026-05-14

### Added
- **Sprint 4: UX Enhancements** — context-aware `ls`, FZF sorted `add -m data`, Rich table output, `results --fzf`, grouped display
- **Sprint 5: Techniques → Config Integration** — `config set techniques`, enhanced `config list techniques` with per-cell device config, `techniques` command deprecated as thin wrapper
- **Sprint 6: SQLite Query Cache** — `memristor/db.py` (4 tables, WAL mode, schema migration), dual-write on `sync`, SQLite read path in dashboard
- **Sprint 7: Config-Driven Technique Registry** — template-based filename naming grammar in `sci-config.yaml`, config-driven technique patterns, grammar-aware filename parsing
- **Project Health**:
  - MIT LICENSE file
  - CI/CD pipeline (`.github/workflows/ci.yml`)
  - `requirements.txt` from pyproject.toml
  - Ruff linting configuration (`ruff.toml`)
  - Mypy type checking config in `pyproject.toml`
  - pytest test suite (`tests/`) with fixtures, core/memristor/session/CLI tests
  - `CONTRIBUTING.md` developer guide
  - `MIGRATION.md` (1.x → 2.0.0)
  - TUI module README (`src/science_cli/tui/README.md`)

### Changed
- Commands reorganized to 4 groups (File Management, Context Navigation, Data Analysis, Extensions & Techniques)
- `ext` command removed — `memristor` is now a direct command
- `config list techniques` shows 4-column Rich table with per-cell device config
- Filename parsing is now config-driven via `file_naming` in `sci-config.yaml`
- All PLAN documentation statuses updated (Sprints 1-7 completed)

### Fixed
- Banner truncated by generic `Horizontal { height: 1 }` — now shows full SCI ASCII art
- Input row gap restored with `#input-row { height: 1 }`
- TUI separators restored and dimmed

## [2.1.1] - 2026-05-17

### Added
- **`-d`/`--device` flag for step metadata** — first-class `device` property on protocol steps, matching `-t`/`--technique`:
  - `add -m protocol`: comma-separated `-d`/`--device` per step
  - `add -m metadata`: set device for existing or new steps (technique no longer required)
  - `edit -m protocol`: set device on steps; `-d` without `--step` modifies existing steps
  - `edit -m metadata`: update device by step name
  - `ls -m protocol --step`: shows Device column in the Rich table
- **`memristor init --matrix` shorthand**: `--matrix r6-c6` as alternative to `--rows 6 --cols 6`
- **`memristor init --label` optional**: auto-generates `"NxM crossbar"` from dimensions when omitted
- **Consolidate devices.yaml into protocol YAML** (`core/protocol.py`):
  - New `device:` section in protocol YAML replaces legacy `devices.yaml`
  - `read_devices()` dispatches to protocol YAML first, falls back to `devices.yaml`
  - `memristor init --matrix` writes device geometry directly to protocol YAML
  - `write_devices()` deprecated with `DeprecationWarning`
  - SQLite schema v4: `sweep_order`, `sweep_type`, `sweep_segments`, `temperature` columns
- **`memristor sync --reconcile`**: 3-phase sync — populate SQLite → sync sweep metadata to YAML → prune stale files
- **Memristor-only technique filter**: DB skips EC techniques (CV, CA, EIS) and fabrication steps (PVD, AFM)
- **Grammar regex fix**: `(?P<technique>...)` named capture groups added to `cv-deposition` and `ca-doping` patterns
- **Matrix display**: R/C labels (R1→R6 top→bottom, C1→C6 left→right), column headers on top, file counts per cell from SQLite

### Changed
- **fzf TUI dispatch**: `tui/app.py` now uses `subprocess.run()` with stop/start application mode instead of `_TeeWriter` capture — avoids asyncio nesting issues
- **fzf execution**: `fzf_utils.py` uses `subprocess.Popen` with `/dev/tty` stderr instead of `pty.spawn()` — cleaner, cross-platform, no ANSI stripping needed
- **Repo restructured**: `git mv science-cli/* .` — repo root IS science-cli content, no more nested `science-cli/` prefix
- **`extensions/` removed from git tracking** (integrated as built-in modules)
- **`theme-previews/` removed from git tracking** (generated artifacts, gitignored)
- `.gitignore` switched to allowlist-based (`/*` + exceptions)
- `memristor/plotting.py`: removed start/end scatter markers (lime/red dots) from time-colored IV plots

### Fixed
- Config merge bug: `get_global_device_config()` and `get_device_config()` returned early from hardcoded defaults, ignoring user's `config.yaml` settings (e.g. `header_lines: 21` was silently overridden by hardcoded `23`)
- `ls_cmd.py`: handle enriched file entries (dicts with `file` key) in matrix display
- Matrix grid rendering: inverted axes, missing column headers

## [2.7.0] - 2026-05-28

### Added
- **Publication-Nature as Global Default Theme**: Full Nature journal compliance — Helvetica 5-7pt, ticks in, open axes (top/right spines off), 300/600 DPI, `pdf.fonttype=42` for editable vector output, Wong colorblind-friendly palette (black-first)
- **`sci serve` Interactive Dashboard Server**: Zero-dependency stdlib HTTP server with REST API endpoints (`/api/project`, `/api/protocol/{name}/summary`, `/api/protocol/{name}/heatmap`, `/api/protocol/{name}/device/{cell}/iv`, `/api/protocol/{name}/histograms`, `/api/gallery`) — serves Plotly.js-powered per-project protocol/step navigation
- **AI Studio Frontend Template**: Complete dashboard frontend (`documentation/frontend 2/`) with React + TypeScript + Vite, gallery page, Plotly.js integration
- **Per-Technique Plot Template Overrides**: `theme/plot-templates/` YAMLs now configure per-technique visual overrides (linewidth, markers, axis labels) on top of global theme

### Changed
- **Global Default Theme**: Changed from `publication-acs` to `publication-nature` across all 17 Python files — every plot command now defaults to Nature style
- **Theme Directory Rename**: `theme/themes/` → `theme/plot-theme/`, `theme/templates/` → `theme/plot-templates/` for clarity
- **fzf as Default Selection Mode**: All file/step/protocol selection uses fzf by default with manual fallback
- **Help Restructured**: Merged GROUP 4 into GROUP 3 as technique-specific subsection for cleaner DX
- **TUI Updated**: `_is_fzf_command` logic updated for fzf-as-default mode
- **Removed Migration Guide**: `documentation/README-1.0.0.md` deleted — `CHANGELOG.md` serves the same purpose
- **All 4 Active Plans Completed**: `refactor`, `ai_integration`, `dashboard`, `themes` — marked done

### Fixed
- **Plot Theme Compliance**: Overlay and single-plot commands (`_do_plot`, `_do_overlap`, `_do_eis_plot`) now read `rcParams` for figsize, linewidth, markersize, and DPI instead of hardcoded `(10,7)`, `1.5`, `6`, `150`
- **fzf Fallback**: Graceful fallback when active protocol has no files
- **Duplicate Step Names**: `add-metadata` and `edit-rm-step` now handle duplicate step names correctly

## [2.2.0] - 2026-05-28

### Added
- **Consolidated Library Namespace**: Added `src/science_cli/library/` package with `__init__.py` to organize technique-specific backends symmetrically.
- **Local AI Subagent**: Localized `plotting-guy` agent profile to the repository root under `.opencode/agents/plotting-guy.md` for project-contained plotting/visualization task orchestration.
- **New Active Workspace Plans**: Established four comprehensive date-prefixed active planning documents under `documentation/artifacts/` covering `refactor`, `ai_integration`, `dashboard`, and `themes`.
- **Strict Checklist Enforcement Rule**: Updated developer instructions in `RULES.md` and codebase documentation in `SCHEMA.md` to mandate real-time checklist checkbox updates (`[x]`) for active plans.

### Changed
- **Symmetric Technique Reorganization**: Consolidated and relocated standalone technique modules (`memristor/`, `electrochem/`, `iv/`) from the source root to `src/science_cli/library/`.
- **Refactored CLI Commands**: Reorganized technique imports in CLI modules (`memristor.py`, `analyze.py`, `eis.py`, `plot.py`) under `src/science_cli/cli/commands/` to map 1:1 to the consolidated library paths.
- **Comprehensive Import Migration**: Automatically executed package-wide python glob script refactoring all internal relative and absolute module references to nested `library/` paths.
- **Test Suite Realignment**: Updated entire unit test suite (`tests/`), including `tests/test_memristor/test_db.py` and `tests/test_guardrails.py`, to correctly reference consolidated namespaces.
- **Artifact Reorganization & Archiving**: Moved 23 historical legacy plans and reports from `documentation/artifacts/` to `documentation/artifacts/archive/` to keep the active planning workspace clean.

### Fixed
- **CLI Command Verification Tests**: Fixed expected command list validations in `tests/test_cli.py` to accurately verify all 16 registered CLI commands.
- **Recursive Import Resolver Error**: Resolved a `ValueError` in relative path calculation when scanning and compiling deeply nested submodules.

## [3.3.0] - 2026-06-06

### Added
- **AFM/SPM Image Analysis Module**: New `src/science_cli/library/afm/` backend wrapping AFMReader to load and analyze AFM/SPM images. Supports `.gwy` (Gwyddion), `.spm` (Bruker), `.ibw` (Igor/Asylum), `.jpk` (JPK), `.stp`/`.top` (WSxM) formats. Depends on `AFMReader>=0.0.7`.
- **AFM CLI Commands**: `sci afm ls|info|plot|analyze|export` registered under `src/science_cli/cli/commands/afm.py` for listing, inspecting, visualizing, analyzing, and exporting AFM data.
- **AFM Plotting Module**: Dedicated `src/science_cli/plot/afm.py` for publication-quality AFM image rendering with Nature-compliant colormaps, scale bars, and cross-section overlays.

## [3.8.0] - 2026-06-09

### Added
- **`sci serve` gallery technique-specific metadata**: Gallery metadata row now auto-detects the measurement technique from step names and shows relevant parameters:
  - **ec-cv**: Number of Cycles, Scan rate, Potential range
  - **ec-ca**: Potential applied, Time
  - **raman**: ND filter, Spectral range (cm⁻¹), Accumulation · Acquisition time
  - **Other techniques**: Fallback to generic metadata (file size, dimensions, quality scale)
- **`api.py` technique detection**: `_detect_technique()` and `_extract_technique_params()` parse step names for CV/CA/Raman measurement parameters from naming conventions

## [3.7.0] - 2026-06-09

### Added
- **`sci serve` gallery improvements**: Auto-fit figures to viewing area (viewport-relative sizing), prev/next navigation buttons for browsing figures, and copy filename button (with "Copied!" indicator)
- **`scripts/patch-gallery-bundle.py`**: Repeatable patch script for gallery bundle modifications

## [3.6.0] - Unreleased

### Added
- **Categorized `--help` Flag Output**: Restructured `COMMAND_HELP` dicts from flat lists to categorized dicts (THEME / ANALYSIS / OUTPUT / OPERATION groups) for raman, uv-vis, ec, afm, plot, analyze, add, edit, delete commands. Updated `show_command_help()` to render category sub-headers.
- **Spectral Range in Raman fzf Pickers**: `sci raman ls`, `raman plot`, `raman info`, and `raman analyze` now display a `Range` column showing the spectral range (first-to-last Raman shift) computed from actual data via `_raman_spectral_range()`.

### Fixed
- **Robust Horiba Header Parsing**: Added `_load_raman_data()` which drops data rows where the first column starts with `#`, handling Horiba `.txt` files with variable header line counts (46 instead of 45) where `#AxisUnit[1]=1/cm` was incorrectly read as a data row.

## [3.5.0] - 2026-06-06

### Added
- **`raman analyze --overlay`**: When processing multiple files, renders all corrected spectra overlaid on a single figure with auto-generated title and color cycling.
- **`raman analyze --all`**: When processing multiple files, renders a subplot grid with each corrected spectrum in its own panel, including baseline (dashed) and peak markers.
- **`raman analyze --no-legend`**: Hides the legend on overlay and regular plots.
- **Multi-file `--ai` mode**: `sci raman analyze --ai` now supports multiple file selection via fzf, with agent recommendations applied across all chosen files.

## [3.4.0] - 2026-06-06

### Added
- **RamanSPy Preprocessing Pipeline (`sci raman analyze`)**: Full RamanSPy-powered pipeline with four-stage processing: denoising (Savitzky-Golay / Whittaker), baseline correction (ASLS, AIRPLS, ARPLS, Poly, ModPoly), normalization (Vector, MinMax, MaxIntensity, AUC), and peak detection with configurable prominence/distance/height/width thresholds.
- **Enhanced Analysis Plot**: Dedicated matplotlib figure showing raw data (gray), baseline curve (orange dashed), corrected/normalized spectrum (black), and annotated peaks (red scatter + text labels with wavenumber annotations).
- **Automatic Text Report**: `{prefix}_report.txt` written alongside CSV exports, containing file metadata (laser, ND filter, acq time, accumulations), full pipeline description, detected peaks table (shift, intensity, prominence, FWHM), and summary statistics.
- **`--ai` Interactive Wizard**: New `sci raman analyze --ai` mode that delegates flag recommendations to the `sci-raman` opencode agent (mimo-v2.5-pro). Picks files via fzf, extracts spectral metadata, sends a structured JSON payload to the agent, parses the returned JSON recommendations (flags with reasoning), and applies the normalized flags automatically. Includes flag name normalization with aliases (e.g. `savgol:7:3`, `area` → `auc`).
- **`sci-raman` Agent**: Created agent definition at `tools/science-cli/.opencode/agents/sci-raman.md` with domain expertise in Raman spectroscopy preprocessing and band assignment.
- **`sci-raman` Skill**: Created skill at `tools/science-cli/.opencode/skills/sci-raman/SKILL.md` providing Raman peak table references and preprocessing guidance for the agent.
- **Updated Help Text**: Enhanced `raman analyze` help description covering pipeline, enhanced plot, text report, `--ai` mode, and all CLI flags.

### Changed
- **Raman Analyze Interactive Prompt**: Replaced static flag defaults with a guided step-by-step interactive pipeline builder for denoising, baseline, normalization, peak finding, and plot generation.
- **RamanSPy Integration**: Under-the-hood migration from manual scipy processing to RamanSPy's preprocessing modules (`rp.preprocessing.denoise`, `rp.preprocessing.baseline`, `rp.preprocessing.normalise`) with standardized spectrometer object handling.

