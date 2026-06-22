"""Protocol YAML read/write helpers for device section and enriched file entries.

The protocol YAML format lives at ``protocol/<name>/<name>.yaml`` and can
optionally include a ``device:`` section and enriched ``files:`` entries
per step with sweep metadata.

The schema supports a hierarchical structure:

.. code-block:: yaml

    device: volatile-memristor             # top-level device type (str)
    name: my-protocol
    steps:
      - name: pulse-endurance-1
        instrument: keysight-b1500a        # per-step instrument (str)
        files:
          - "data_file.csv"

Backward compatible: old files where ``device:`` is a dict (geometry section)
still load with ``Protocol.device = None``.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# ── Known device types ────────────────────────────────────────────────

KNOWN_DEVICE_TYPES: list[str] = [
    "memristor",
    "junction",
    "deposition",
    "pvd",
    "electrochem",
    "general",
]


def validate_device_type(devices: str) -> bool:
    """Validate that a device type string is a known type or 'general'."""
    return devices in KNOWN_DEVICE_TYPES


# ── Dataclasses ──────────────────────────────────────────────────────


@dataclass
class ProtocolStep:
    """A single measurement step within a protocol.

    Parameters
    ----------
    name:
        Unique step name within the protocol.
    technique:
        Measurement technique identifier (e.g. ``"iv-sweep"``, ``"mem-endurance"``).
    instrument:
        Instrument used for this step (e.g. ``"keysight-b1500a"``).
        Added per-step in the new hierarchical schema.
    files:
        List of data filenames attached to this step.
    study:
        Optional study/analysis class identifier.
    metadata:
        Arbitrary key-value metadata for analysis results.
    """

    name: str = ""
    technique: str = ""
    instrument: str | None = None
    files: list[str | dict] = field(default_factory=list)
    study: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "ProtocolStep":
        """Create a ProtocolStep from a raw YAML dict (backward-compatible)."""
        return cls(
            name=d.get("name", ""),
            technique=d.get("technique", ""),
            instrument=d.get("instrument"),
            files=list(d.get("files", []) or []),
            study=d.get("study", ""),
            metadata=dict(d.get("metadata", {}) or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize back to a plain dict, omitting None defaults."""
        d: dict[str, Any] = {}
        if self.name:
            d["name"] = self.name
        if self.technique:
            d["technique"] = self.technique
        if self.instrument is not None:
            d["instrument"] = self.instrument
        if self.files:
            d["files"] = list(self.files)
        if self.study:
            d["study"] = self.study
        if self.metadata:
            d["metadata"] = dict(self.metadata)
        return d


@dataclass
class Protocol:
    """Top-level protocol container.

    Parameters
    ----------
    name:
        Protocol name.
    description:
        Optional human-readable description.
    device:
        Device type string e.g. ``"volatile-memristor"`` at the protocol level.
        In the new hierarchical schema this is a top-level string, replacing the
        older ``devices:`` field and coexisting with the ``device:`` geometry dict.
    steps:
        Ordered list of measurement steps.
    """

    name: str = ""
    description: str = ""
    device: str | None = None
    steps: list[ProtocolStep] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Protocol":
        """Create a Protocol from a raw YAML dict (backward-compatible).

        Handles two shapes for the ``device`` key:

        * **String** (new schema): ``device: volatile-memristor``
          → stored as ``Protocol.device``.
        * **Dict** (legacy geometry section): ``device: {rows: 6, cols: 6}``
          → ``Protocol.device`` stays ``None``.
        """
        device_val: str | None = None
        raw_device = d.get("device")
        # String device type — new hierarchical schema
        if isinstance(raw_device, str):
            device_val = raw_device
        # Also accept the plural ``devices:`` field as a fallback
        if device_val is None:
            raw_devices = d.get("devices")
            if isinstance(raw_devices, str):
                device_val = raw_devices

        steps = [
            ProtocolStep.from_dict(s)
            for s in (d.get("steps", []) or [])
            if isinstance(s, dict)
        ]

        return cls(
            name=d.get("name", ""),
            description=d.get("description", ""),
            device=device_val,
            steps=steps,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize back to a plain dict, omitting empty parts."""
        d: dict[str, Any] = {}
        if self.name:
            d["name"] = self.name
        if self.description:
            d["description"] = self.description
        if self.device is not None:
            d["device"] = self.device
        if self.steps:
            d["steps"] = [s.to_dict() for s in self.steps]
        return d


# ── New: load/save protocol ──────────────────────────────────────────


def load_protocol(yaml_path: Path) -> Protocol:
    """Load a protocol YAML file and return a :class:`Protocol` instance.

    Args:
        yaml_path: Path to the protocol YAML file.

    Returns:
        A :class:`Protocol` instance, or an empty one if the file
        doesn't exist or cannot be parsed.
    """
    path = Path(yaml_path)
    if not path.exists():
        return Protocol()

    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return Protocol()

    if not isinstance(data, dict):
        return Protocol()

    return Protocol.from_dict(data)


def save_protocol(yaml_path: Path, protocol: Protocol) -> bool:
    """Write a :class:`Protocol` instance to a YAML file.

    Args:
        yaml_path: Path to write the protocol YAML file.
        protocol: The :class:`Protocol` to serialize.

    Returns:
        ``True`` on success.
    """
    path = Path(yaml_path)
    data = protocol.to_dict()

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True, indent=2)
    return True


# ── Devices field ────────────────────────────────────────────────────


def read_devices_field(yaml_path: Path) -> str:
    """Read the optional ``devices:`` field from protocol YAML.

    Args:
        yaml_path: Path to protocol YAML file.

    Returns:
        Device type string, or ``"general"`` if not set.
    """
    path = Path(yaml_path)
    if not path.exists():
        return "general"

    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return "general"

    return str(data.get("devices", "general")) if isinstance(data, dict) else "general"


def write_devices_field(yaml_path: Path, devices: str) -> bool:
    """Write/update the ``devices:`` field in protocol YAML.

    Preserves all other YAML content. Validates the device type.

    Args:
        yaml_path: Path to protocol YAML file.
        devices: Device type string (e.g. 'memristor', 'junction', 'general').

    Returns:
        ``True`` on success.
    """
    path = Path(yaml_path)
    if not validate_device_type(devices):
        known = ", ".join(KNOWN_DEVICE_TYPES)
        raise ValueError(f"Unknown device type '{devices}'. Must be one of: {known}")

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

    data["devices"] = devices

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True, indent=2)
    return True


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


# ── Grammar section ────────────────────────────────────────────────


def read_protocol_grammar(yaml_path: Path) -> list[dict]:
    """Read the optional ``grammar:`` section from protocol YAML.

    The grammar section contains per-protocol filename pattern overrides.

    Args:
        yaml_path: Path to protocol YAML file.

    Returns:
        List of grammar pattern dicts, or empty list if not set.
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

    grammar = data.get("grammar")
    if not isinstance(grammar, dict):
        return []

    patterns = grammar.get("patterns", [])
    return list(patterns) if isinstance(patterns, list) else []


def write_protocol_grammar(yaml_path: Path, patterns: list[dict]) -> bool:
    """Write/update the ``grammar:`` section in protocol YAML.

    Preserves all other YAML content.

    Args:
        yaml_path: Path to protocol YAML file.
        patterns: List of grammar pattern dicts.

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

    data["grammar"] = {"patterns": patterns}

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True, indent=2)
    return True


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


# ── Step metadata ──────────────────────────────────────────────────


def _atomic_write_yaml(path: Path, data: dict) -> None:
    """Write YAML atomically: write to temp file, then rename."""
    import os
    import tempfile

    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=path.parent, suffix=".yaml.tmp", prefix=".tmp_"
    )
    try:
        with os.fdopen(tmp_fd, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False,
                      allow_unicode=True, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def update_step_metadata(
    project_root: Path, step_name: str, metadata: dict
) -> bool:
    """Update the ``metadata`` field of a step in ``protocol.yaml``.

    Reads ``protocol.yaml`` from *project_root*, finds the step by name,
    merges *metadata* into the step's ``metadata:`` dict (creating it if
    absent), and writes the file back atomically.

    Parameters
    ----------
    project_root:
        Path to the project directory containing ``protocol.yaml``.
    step_name:
        Name of the step to update (matched by ``step["name"]``).
    metadata:
        Dict of key-value pairs to merge into the step's metadata.

    Returns
    -------
    bool
        ``True`` if the step was found and updated, ``False`` otherwise.
    """
    protocol_path = project_root / "protocol.yaml"
    if not protocol_path.exists():
        return False

    try:
        data = yaml.safe_load(protocol_path.read_text()) or {}
    except Exception:
        return False

    if not isinstance(data, dict):
        return False

    steps = data.get("steps", [])
    if not isinstance(steps, list):
        return False

    for step in steps:
        if not isinstance(step, dict):
            continue
        if step.get("name") == step_name:
            step.setdefault("metadata", {}).update(metadata)
            _atomic_write_yaml(protocol_path, data)
            return True

    return False


def read_step_metadata(project_root: Path, step_name: str) -> dict:
    """Read the ``metadata`` field of a step from ``protocol.yaml``.

    Parameters
    ----------
    project_root:
        Path to the project directory containing ``protocol.yaml``.
    step_name:
        Name of the step to read.

    Returns
    -------
    dict
        The step's metadata dict, or empty dict if not found.
    """
    protocol_path = project_root / "protocol.yaml"
    if not protocol_path.exists():
        return {}

    try:
        data = yaml.safe_load(protocol_path.read_text()) or {}
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    for step in data.get("steps", []) or []:
        if not isinstance(step, dict):
            continue
        if step.get("name") == step_name:
            return step.get("metadata", {})

    return {}


def write_file_metadata(
    protocol_path: Path, step_name: str, filename: str, metadata_dict: dict
) -> bool:
    """Add or update the ``metadata`` dict for a file entry within a step.

    Loads the protocol YAML, finds the step matching *step_name*, locates the
    file entry matching *filename* within that step's ``files`` list, and
    merges *metadata_dict* into the file entry's ``metadata`` sub-dict
    (creating it if absent).

    If the file entry is currently a plain string (e.g. ``"data.csv"``), it
    is promoted to a dict with a ``file`` key and the given metadata is
    attached.

    Writes the file back atomically using :func:`_atomic_write_yaml` to
    prevent corruption on partial writes.

    Parameters
    ----------
    protocol_path:
        Path to the protocol YAML file.
    step_name:
        Name of the step containing the file entry.
    filename:
        Filename to match (matched against the ``file`` key or the raw
        string in the files list).
    metadata_dict:
        Dict of key-value pairs to merge into the file entry's ``metadata``
        sub-dict. Existing keys with the same name are overwritten.

    Returns
    -------
    bool
        ``True`` if the step and file entry were found and updated,
        ``False`` otherwise (step not found, file not found, or I/O error).
    """
    path = Path(protocol_path)
    if not path.exists():
        return False

    try:
        data = yaml.safe_load(path.read_text()) or {}
    except Exception:
        return False

    if not isinstance(data, dict):
        return False

    steps = data.get("steps", [])
    if not isinstance(steps, list):
        return False

    for step in steps:
        if not isinstance(step, dict):
            continue
        if step.get("name") != step_name:
            continue

        # Found the step — now find the file entry by filename
        files = step.get("files", [])
        if not isinstance(files, list):
            return False

        for i, entry in enumerate(files):
            if isinstance(entry, str):
                # Plain string entry — match and promote to dict
                if entry == filename:
                    files[i] = {
                        "file": filename,
                        "metadata": dict(metadata_dict),
                    }
                    _atomic_write_yaml(path, data)
                    return True
            elif isinstance(entry, dict):
                # Dict entry — match by "file" key and merge metadata
                if entry.get("file") == filename:
                    entry.setdefault("metadata", {}).update(metadata_dict)
                    _atomic_write_yaml(path, data)
                    return True

        # File not found in this step
        return False

    # Step not found
    return False


def get_pulse_steps_with_metadata(
    project_root: Path, study_filter: str = "",
) -> list[dict]:
    """List pulse steps from protocol.yaml, enriched with metadata.

    Parameters
    ----------
    project_root:
        Path to the project directory containing ``protocol.yaml``.
    study_filter:
        Optional study prefix filter (e.g. ``"pulse:pulse-stp-decay"``).

    Returns
    -------
    list[dict]
        List of dicts with keys: ``name``, ``study``, ``files``, ``metadata``.
    """
    protocol_path = project_root / "protocol.yaml"
    if not protocol_path.exists():
        return []

    try:
        data = yaml.safe_load(protocol_path.read_text()) or {}
    except Exception:
        return []

    if not isinstance(data, dict):
        return []

    results: list[dict] = []
    for step in data.get("steps", []) or []:
        if not isinstance(step, dict):
            continue
        study = step.get("study", "")
        if not study.startswith("pulse"):
            continue
        if study_filter and study != study_filter:
            continue
        results.append({
            "name": step.get("name", ""),
            "study": study,
            "files": step.get("files", []),
            "metadata": step.get("metadata", {}),
        })

    return results


# ── Per-file analyze config ──────────────────────────────────────────


def resolve_file_analyze_config(
    filepath: str | Path,
    function_name: str,
) -> dict:
    """Read per-file analyze overrides from protocol.yaml.

    Walks up from *filepath* to find ``protocol/<dir>/<dir>.yaml``,
    locates the matching file entry in ``steps[*].files[*]``, and
    returns the ``analyze:<function_name>:`` dict (a top-level key on the
    file entry, **not** inside ``metadata:``).

    Args:
        filepath: Path to the data file (must be inside a protocol/ dir).
        function_name: Analyze function key, e.g. ``"ratio_histogram"``.

    Returns:
        Config dict for the given function, or ``{}`` if not found.
    """
    fp = Path(filepath)
    parts = fp.parts

    # Walk up to find protocol/<dirname>/<dirname>.yaml
    try:
        proto_idx = parts.index("protocol")
        proto_name = parts[proto_idx + 1]
        proto_yaml = Path(*parts[: proto_idx + 2]) / f"{proto_name}.yaml"
    except (ValueError, IndexError):
        return {}

    if not proto_yaml.exists():
        return {}

    try:
        data = yaml.safe_load(proto_yaml.read_text()) or {}
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    fname = fp.name
    for step in data.get("steps", []) or []:
        if not isinstance(step, dict):
            continue
        for entry in step.get("files", []) or []:
            entry_file = entry["file"] if isinstance(entry, dict) else entry
            if entry_file == fname:
                # Top-level 'analyze' key (not inside metadata)
                if isinstance(entry, dict):
                    analyze = entry.get("analyze", {})
                    if isinstance(analyze, dict):
                        return analyze.get(function_name, {})
                return {}

    return {}


# NOTE: get_step_columns() is defined in `science_cli.core.fzf_columns` to
# avoid a circular dependency between protocol.py and fzf_utils/fzf_columns.
# Callers should import from `science_cli.core.fzf_columns`.
