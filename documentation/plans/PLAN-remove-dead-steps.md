# PLAN: Document/Remove Dead `--steps` Flag on `memristor init`

## Classification
docs / cleanup

## Related Plans
- [[PLAN-dashboard-redesign]] — related (both touch `memristor init` behavior)

## Status
- **Created**: 2026-05-17
- **Status**: draft
- **Branch**: (none)

## Objective
Document the `--steps` flag on `memristor init` as informational-only, with a future option to remove or properly implement it.

## Context

### The Problem
The `memristor init` command accepts a `--steps` flag (defined in `device_cli.py` line 2133, parsed in `cmd_init()` at line 382). The flag is used to build a `steps` dict at lines 383-406, but this dict is **only printed to console** at line 412 — it is **never persisted** to the protocol YAML.

```python
# device_cli.py, cmd_init()
steps = {}
# ... build steps mapping from --steps argument ...
print(f"  Steps: {steps}")    # ← only output — never written to YAML
```

### Why It Exists
The `--steps` flag was originally intended to let users specify which step subdirectories correspond to which techniques when initializing a device matrix. The step→technique mapping is already auto-resolved from the protocol YAML's `steps[].technique` field, making the explicit `--steps` flag redundant.

### Impact
- Users who specify `--steps 4_iv` get confirmation output but no actual effect
- The flag creates a misleading user experience — the flag appears to configure something but doesn't
- No tests depend on the persisted `--steps` behavior (since it was never persisted)

## Specification

### Option A: Document as Informational (Minimal)
Add a note to `memristor/README.md` and the CLI help text stating that `--steps` is currently informational only and the step→technique mapping is auto-resolved from the protocol YAML.

### Option B: Remove the Flag (Cleanup)
- Remove `--steps` from the `memristor init` argument parser
- Remove the `steps` dict building and console print in `cmd_init()`
- Update help text and documentation

### Option C: Implement Properly (Feature)
- Persist the `--steps` mapping to the protocol YAML as a `step_mapping:` section
- This would allow explicit override of the auto-resolved step→technique mapping

## Recommendation
**Option A** is recommended for now — the flag is harmless and removing it would be a (minor) breaking change for anyone using it in scripts. The documentation has been updated to note the informational-only status.

## Files to Modify (if implementing)
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/memristor/device_cli.py` | Modify | Remove `--steps` parser arg and dead code |
| `src/science_cli/memristor/README.md` | Modify | Update `--steps` documentation ✅ (already done) |

## Progress
- [x] Flag identified as dead code (confirmed: parsed but never persisted)
- [x] memristor/README.md updated with informational-only note
- [ ] CLI help text updated (deferred — minor issue)
- [ ] Flag removed or properly implemented (deferred — needs user decision)
