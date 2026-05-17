"""Protocol YAML read/write helpers for device section and enriched file entries.

The protocol YAML format lives at ``protocol/<name>/<name>.yaml`` and can
optionally include a ``device:`` section and enriched ``files:`` entries
per step with sweep metadata.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml


# ── Device section ───────────────────────────────────────────────────


def read_device_section(yaml_path: Path) -> dict | None:
    """Read the optional ``device:`` section from protocol YAML.

    Args:
        yaml_path: Path to protocol YAML file.

    Returns:
        dict with keys: ``rows``, ``cols``, ``label``, ``cell_area_um2``,
        ``id``, ``description``, ``row_labels``, ``col_labels``.
        Returns ``None`` if no device section exists or file not found.
    """
    path = Path(yaml_path)
    if not path.exists():
        return None

    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return None

    return data.get("device") if isinstance(data, dict) else None


def write_device_section(yaml_path: Path, geometry: dict) -> bool:
    """Write/update the ``device:`` section in protocol YAML.

    Preserves all other YAML content (name, description, steps, etc.).

    Args:
        yaml_path: Path to protocol YAML file.
        geometry: dict with keys: ``rows``, ``cols``, ``label``,
            ``cell_area_um2``, ``id``, ``description``, ``row_labels``,
            ``col_labels``.

    Returns:
        ``True`` on success.
    """
    path = Path(yaml_path)

    try:
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                data = {}
        else:
            data = {}
    except Exception:
        data = {}

    # Build device section from provided keys
    device: dict = {}
    for key in ("rows", "cols", "label", "cell_area_um2", "id",
                "description", "row_labels", "col_labels"):
        if key in geometry and geometry[key] is not None:
            device[key] = geometry[key]

    data["device"] = device

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True, indent=2)
    return True


def has_device_section(yaml_path: Path) -> bool:
    """Check if protocol YAML has a ``device:`` section.

    Args:
        yaml_path: Path to protocol YAML file.

    Returns:
        ``True`` if ``device:`` section exists and is a dict.
    """
    path = Path(yaml_path)
    if not path.exists():
        return False

    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return False

    if not isinstance(data, dict):
        return False

    device = data.get("device")
    return isinstance(device, dict) and len(device) > 0


# ── Enriched file entries ───────────────────────────────────────────


def _normalize_files(step_files: list) -> list[dict]:
    """Normalize files list: every entry is a dict with a ``file`` key."""
    normalized: list[dict] = []
    for entry in step_files:
        if isinstance(entry, str):
            normalized.append({"file": entry})
        elif isinstance(entry, dict) and "file" in entry:
            normalized.append(entry)
        # skip broken entries silently
    return normalized


def _denormalize_files(entries: list[dict]) -> list:
    """Write back files list: plain string if no extra keys, dict otherwise."""
    result: list = []
    ENRICHED_KEYS = {"sweep_order", "sweep_type", "sweep", "temperature"}

    for entry in entries:
        if not isinstance(entry, dict):
            result.append(entry)
            continue

        # Check if entry has any non-"file" keys worth preserving
        extra_keys = set(entry.keys()) - {"file"}
        has_extra = bool(extra_keys & ENRICHED_KEYS) or len(extra_keys) > 0

        if has_extra:
            result.append(entry)
        else:
            # Plain string entry
            result.append(entry.get("file", ""))
    return result


def read_step_enriched_files(yaml_path: Path, step_name: str) -> list[dict]:
    """Read enriched file entries for a specific step.

    Handles both plain-string files (backward compat) and dict entries
    with ``file`` key. All returned entries are normalized to dicts.

    Args:
        yaml_path: Path to protocol YAML file.
        step_name: Name of the step to read files from.

    Returns:
        List of dicts with keys: ``file``, ``sweep_order``, ``sweep_type``,
        ``temperature``, ``sweep``. Returns empty list if step not found
        or has no files.
    """
    path = Path(yaml_path)
    if not path.exists():
        return []

    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return []

    if not isinstance(data, dict):
        return []

    for step in data.get("steps", []) or []:
        if not isinstance(step, dict):
            continue
        if step.get("name") != step_name:
            continue
        return _normalize_files(step.get("files", []) or [])

    return []


def write_step_enriched_files(
    yaml_path: Path, step_name: str, file_entries: list[dict]
) -> bool:
    """Update file entries for a specific step with sweep metadata.

    Preserves any other existing file entries and any extra YAML keys
    on file entries that aren't in the standard enriched set.

    Args:
        yaml_path: Path to protocol YAML file.
        step_name: Name of the step to update.
        file_entries: List of dicts, each with ``file`` (required) and
            optional ``sweep_order``, ``sweep_type``, ``temperature``,
            ``sweep``.

    Returns:
        ``True`` on success.
    """
    path = Path(yaml_path)
    if not path.exists():
        return False

    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return False

    if not isinstance(data, dict) or "steps" not in data:
        return False

    for step in data["steps"]:
        if not isinstance(step, dict):
            continue
        if step.get("name") != step_name:
            continue

        step["files"] = _denormalize_files(file_entries)
        break
    else:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True, indent=2)
    return True


# ── Migration from legacy devices.yaml ──────────────────────────────


def migrate_from_devices_yaml(
    devices_yaml_path: Path, protocol_yaml_path: Path
) -> dict:
    """One-time migration from legacy ``devices.yaml`` to protocol YAML.

    - Copies ``device:`` geometry from devices.yaml
    - Copies step mapping from devices.yaml ``steps:`` into protocol YAML
    - For each per-cell ``FileEntry`` with sweep metadata, adds enriched
      file entries to the appropriate step in protocol YAML
    - Adds ``_meta.migrated_from`` and ``_meta.migrated_at``

    Args:
        devices_yaml_path: Path to the legacy devices.yaml file.
        protocol_yaml_path: Path to the target protocol YAML file.

    Returns:
        Report dict: ``{migrated: bool, device_copied: bool,
        files_migrated: int, errors: list[str]}``.
    """
    result: dict = {
        "migrated": False,
        "device_copied": False,
        "files_migrated": 0,
        "errors": [],
    }

    devices_path = Path(devices_yaml_path)
    proto_path = Path(protocol_yaml_path)

    if not devices_path.exists():
        result["errors"].append(
            f"devices.yaml not found: {devices_path}"
        )
        return result

    # Read devices.yaml
    try:
        with open(devices_path) as f:
            dev_data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        result["errors"].append(f"YAML parse error in devices.yaml: {e}")
        return result
    except Exception as e:
        result["errors"].append(f"Failed to read devices.yaml: {e}")
        return result

    # Read or create protocol YAML
    if proto_path.exists():
        try:
            with open(proto_path) as f:
                proto_data = yaml.safe_load(f) or {}
        except Exception as e:
            result["errors"].append(f"Failed to read protocol YAML: {e}")
            return result
    else:
        proto_data = {}

    if not isinstance(proto_data, dict):
        proto_data = {}

    # ── Step 1: Copy device geometry ──
    dev_geometry = dev_data.get("device", {}) if isinstance(dev_data, dict) else {}
    if dev_geometry:
        proto_data["device"] = dict(dev_geometry)
        result["device_copied"] = True

    # ── Step 2: Copy step mapping ──
    # devices.yaml has steps: {technique: step_name}
    # Protocol YAML stores steps as list of dicts with name/technique
    legacy_steps = dev_data.get("steps", {}) if isinstance(dev_data, dict) else {}
    if legacy_steps:
        # Build a step name → technique reverse map from existing protocol steps
        existing_by_technique: dict[str, str] = {}
        for s in proto_data.get("steps", []) or []:
            if isinstance(s, dict) and s.get("technique") and s.get("name"):
                existing_by_technique[s["technique"]] = s["name"]

        # Add legacy steps not already in protocol YAML
        proto_steps: list[dict] = list(proto_data.get("steps", []) or [])
        for technique, step_name in legacy_steps.items():
            if technique not in existing_by_technique:
                proto_steps.append({"name": step_name, "technique": technique})

        if proto_steps:
            proto_data["steps"] = proto_steps

    # ── Step 3: Copy per-cell files with sweep metadata ──
    points = dev_data.get("points", []) if isinstance(dev_data, dict) else []
    for pt_data in points:
        if not isinstance(pt_data, dict):
            continue
        techniques = pt_data.get("techniques", {})
        for tech_name, file_list in (techniques or {}).items():
            # Find the matching step name for this technique
            step_name = legacy_steps.get(tech_name, "")
            if not step_name:
                continue

            # Find the step in proto_data
            matching_step = None
            for s in proto_data.get("steps", []) or []:
                if isinstance(s, dict) and s.get("name") == step_name:
                    matching_step = s
                    break

            if matching_step is None:
                continue

            existing_files = _build_file_index(
                _normalize_files(matching_step.get("files", []) or [])
            )

            for fd in file_list:
                if not isinstance(fd, dict):
                    continue
                filename = fd.get("file", "")
                if not filename:
                    continue

                # Build enriched entry
                entry: dict = {"file": filename}
                if fd.get("sweep_order") is not None:
                    entry["sweep_order"] = fd["sweep_order"]
                if fd.get("sweep_type"):
                    entry["sweep_type"] = fd["sweep_type"]
                if fd.get("sweep"):
                    entry["sweep"] = fd["sweep"]
                if fd.get("temperature") is not None:
                    entry["temperature"] = fd["temperature"]

                # Preserve extra keys
                STANDARD = {"file", "sweep_order", "sweep_type", "sweep",
                            "temperature"}
                for k, v in fd.items():
                    if k not in STANDARD and k != "file":
                        entry[k] = v

                # Update or append
                if filename in existing_files:
                    idx = existing_files[filename]
                    matching_step_files = _normalize_files(
                        matching_step.get("files", []) or []
                    )
                    matching_step_files[idx] = entry
                    matching_step["files"] = _denormalize_files(matching_step_files)
                else:
                    matching_step_files = _normalize_files(
                        matching_step.get("files", []) or []
                    )
                    matching_step_files.append(entry)
                    matching_step["files"] = _denormalize_files(matching_step_files)

                result["files_migrated"] += 1

    # ── Step 4: Add migration metadata ──
    proto_data.setdefault("_meta", {})
    proto_data["_meta"]["migrated_from"] = "devices.yaml"
    proto_data["_meta"]["migrated_at"] = datetime.now(timezone.utc).isoformat()

    # ── Step 5: Write protocol YAML ──
    try:
        proto_path.parent.mkdir(parents=True, exist_ok=True)
        with open(proto_path, "w") as f:
            yaml.dump(proto_data, f, default_flow_style=False,
                      sort_keys=False, allow_unicode=True, indent=2)
        result["migrated"] = True
    except Exception as e:
        result["errors"].append(f"Failed to write protocol YAML: {e}")

    return result


def _build_file_index(normalized_entries: list[dict]) -> dict[str, int]:
    """Build a filename → list-index mapping from normalized file entries."""
    idx: dict[str, int] = {}
    for i, entry in enumerate(normalized_entries):
        fname = entry.get("file", "")
        if fname:
            idx[fname] = i
    return idx
