"""YAML schema validators for the modular config files.

Each validator returns a list of error strings (empty = valid).
"""

from typing import Any


_STUDIES_TECHNIQUES = {"iv", "pulse", "raman", "uv-vis", "ec", "afm", "memristor"}

_REQUIRED_STUDY_FIELDS = {"label", "patterns", "legacy_codes", "instruments"}

_REQUIRED_DEVICE_TYPE_FIELDS = {"label", "description", "studies",
                                "analysis_mode", "library"}

_VALID_ANALYSIS_MODES = {"volatile", "bipolar", "linear", "general"}

_REQUIRED_INSTRUMENT_FIELDS = {"label", "location", "type",
                               "parsing"}

_REQUIRED_GRAMMAR_PATTERN_FIELDS = {"id", "template", "description",
                                    "regex", "fields"}

_TEMPLATE_KEYS = {"templates"}
_TEMPLATE_REQUIRED_TOP_FIELDS = {"font", "fontsize", "dpi", "figure_format"}

_ALLOWED_DEVICES_TOP_KEYS = {"device_types", "legacy_to_study"}

_ALLOWED_STUDIES_TOP_KEYS = {"studies"}

_ALLOWED_INSTRUMENTS_TOP_KEYS = {"instruments", "devices"}

_ALLOWED_GRAMMAR_TOP_KEYS = {"file_naming"}

_ALLOWED_TEMPLATE_TOP_KEYS = {"templates"}

_VALID_DATA_SHAPE_KINDS = {"waveform_2d", "spectrum_2d", "trace_2d", "image_2d"}


def _check_type(value: Any, expected_type: type, path: str) -> list[str]:
    """Type-check a value and return an error list."""
    if not isinstance(value, expected_type):
        return [f"{path}: expected {expected_type.__name__}, got {type(value).__name__}"]
    return []


def _check_missing_keys(data: dict, required: set, path: str) -> list[str]:
    """Check for missing required keys."""
    return [f"{path}: missing required key '{k}'" for k in required if k not in data]


def _check_unknown_keys(data: dict, allowed: set, path: str) -> list[str]:
    """Warn about unknown keys (not errors, just warnings)."""
    return [f"{path}: unknown key '{k}'" for k in data if k not in allowed]


def validate_devices_config(data: dict) -> list[str]:
    """Validate config-devices.yaml structure (no studies — moved to config-studies.yaml)."""
    errors: list[str] = []

    errors.extend(_check_type(data, dict, "root"))
    if not isinstance(data, dict):
        return errors

    errors.extend(_check_unknown_keys(data, _ALLOWED_DEVICES_TOP_KEYS, "root"))

    # Validate device_types section
    device_types = data.get("device_types", {})
    if not isinstance(device_types, dict):
        errors.append("device_types: expected dict")
    else:
        for dt_name, dt_cfg in device_types.items():
            dt_path = f"device_types.{dt_name}"
            if not isinstance(dt_cfg, dict):
                errors.append(f"{dt_path}: expected dict")
                continue
            errors.extend(_check_missing_keys(dt_cfg, _REQUIRED_DEVICE_TYPE_FIELDS,
                                              dt_path))
            mode = dt_cfg.get("analysis_mode")
            if mode and mode not in _VALID_ANALYSIS_MODES:
                errors.append(f"{dt_path}.analysis_mode: unknown mode '{mode}'")
            studies_list = dt_cfg.get("studies")
            if studies_list is not None:
                errors.extend(_check_type(studies_list, list, f"{dt_path}.studies"))

    # Validate legacy_to_study section
    legacy = data.get("legacy_to_study", {})
    if not isinstance(legacy, dict):
        errors.append("legacy_to_study: expected dict")

    return errors


def validate_studies_config(data: dict) -> list[str]:
    """Validate config-studies.yaml structure.

    Checks:
        - Top-level ``studies`` key is a dict
        - Each study has required fields (label, patterns, legacy_codes, instruments)
        - ``data_shape`` (optional) has ``kind`` in VALID_DATA_SHAPE_KINDS and ``columns`` (list)
        - ``device_overrides`` (optional) is a dict with ``add``/``exclude`` keys
        - ``derived_metadata`` (optional) is a list of strings
    """
    errors: list[str] = []

    errors.extend(_check_type(data, dict, "root"))
    if not isinstance(data, dict):
        return errors

    errors.extend(_check_unknown_keys(data, _ALLOWED_STUDIES_TOP_KEYS, "root"))

    # Validate studies section
    studies = data.get("studies", {})
    if not isinstance(studies, dict):
        errors.append("studies: expected dict")
        return errors

    for tech_name, tech_studies in studies.items():
        tech_path = f"studies.{tech_name}"
        if not isinstance(tech_studies, dict):
            errors.append(f"{tech_path}: expected dict")
            continue
        for study_name, study_cfg in tech_studies.items():
            study_path = f"{tech_path}.{study_name}"
            if not isinstance(study_cfg, dict):
                errors.append(f"{study_path}: expected dict")
                continue
            errors.extend(_check_missing_keys(study_cfg, _REQUIRED_STUDY_FIELDS,
                                              study_path))
            patterns = study_cfg.get("patterns")
            if patterns is not None:
                errors.extend(_check_type(patterns, list, f"{study_path}.patterns"))
            legacy_codes = study_cfg.get("legacy_codes")
            if legacy_codes is not None:
                errors.extend(_check_type(legacy_codes, list,
                                          f"{study_path}.legacy_codes"))

            # Validate data_shape (optional)
            data_shape = study_cfg.get("data_shape")
            if data_shape is not None:
                if not isinstance(data_shape, dict):
                    errors.append(f"{study_path}.data_shape: expected dict")
                else:
                    kind = data_shape.get("kind")
                    if kind not in _VALID_DATA_SHAPE_KINDS:
                        errors.append(
                            f"{study_path}.data_shape.kind: unknown kind '{kind}' "
                            f"(expected one of: {sorted(_VALID_DATA_SHAPE_KINDS)})"
                        )
                    columns = data_shape.get("columns")
                    if not isinstance(columns, list):
                        errors.append(f"{study_path}.data_shape.columns: expected list")
                    units = data_shape.get("units")
                    if units is not None and not isinstance(units, list):
                        errors.append(f"{study_path}.data_shape.units: expected list")

            # Validate device_overrides (optional)
            device_overrides = study_cfg.get("device_overrides")
            if device_overrides is not None:
                if not isinstance(device_overrides, dict):
                    errors.append(f"{study_path}.device_overrides: expected dict")
                else:
                    for dt_key, dt_val in device_overrides.items():
                        do_path = f"{study_path}.device_overrides.{dt_key}"
                        if not isinstance(dt_val, dict):
                            errors.append(f"{do_path}: expected dict")
                            continue
                        for op_key in ("add", "exclude"):
                            if op_key in dt_val:
                                if not isinstance(dt_val[op_key], list):
                                    errors.append(f"{do_path}.{op_key}: expected list")

            # Validate derived_metadata (optional)
            derived = study_cfg.get("derived_metadata")
            if derived is not None:
                if not isinstance(derived, list):
                    errors.append(f"{study_path}.derived_metadata: expected list")
                elif not all(isinstance(item, str) for item in derived):
                    errors.append(f"{study_path}.derived_metadata: expected list of strings")

    return errors


def validate_instruments_config(data: dict) -> list[str]:
    """Validate config-instruments.yaml structure."""
    errors: list[str] = []

    errors.extend(_check_type(data, dict, "root"))
    if not isinstance(data, dict):
        return errors

    errors.extend(_check_unknown_keys(data, _ALLOWED_INSTRUMENTS_TOP_KEYS, "root"))

    instruments = data.get("instruments", {})
    if not isinstance(instruments, dict):
        errors.append("instruments: expected dict")
        return errors

    for ins_name, ins_cfg in instruments.items():
        ins_path = f"instruments.{ins_name}"
        if not isinstance(ins_cfg, dict):
            errors.append(f"{ins_path}: expected dict")
            continue
        errors.extend(_check_missing_keys(ins_cfg, _REQUIRED_INSTRUMENT_FIELDS,
                                          ins_path))
        parsing = ins_cfg.get("parsing")
        if parsing is not None:
            errors.extend(_check_type(parsing, dict, f"{ins_path}.parsing"))

    return errors


def validate_grammar_config(data: dict) -> list[str]:
    """Validate config-grammar.yaml structure."""
    errors: list[str] = []

    errors.extend(_check_type(data, dict, "root"))
    if not isinstance(data, dict):
        return errors

    errors.extend(_check_unknown_keys(data, _ALLOWED_GRAMMAR_TOP_KEYS, "root"))

    file_naming = data.get("file_naming", {})
    if not isinstance(file_naming, dict):
        errors.append("file_naming: expected dict")
        return errors

    patterns = file_naming.get("patterns", [])
    if not isinstance(patterns, list):
        errors.append("file_naming.patterns: expected list")
        return errors

    for i, pattern in enumerate(patterns):
        pat_path = f"file_naming.patterns[{i}]"
        if not isinstance(pattern, dict):
            errors.append(f"{pat_path}: expected dict")
            continue
        errors.extend(_check_missing_keys(pattern, _REQUIRED_GRAMMAR_PATTERN_FIELDS,
                                          pat_path))
        pattern_id = pattern.get("id")
        if pattern_id is not None:
            errors.extend(_check_type(pattern_id, str, f"{pat_path}.id"))
        regex = pattern.get("regex")
        if regex is not None:
            errors.extend(_check_type(regex, str, f"{pat_path}.regex"))

    return errors


def validate_template_config(data: dict) -> list[str]:
    """Validate config-template.yaml structure."""
    errors: list[str] = []

    errors.extend(_check_type(data, dict, "root"))
    if not isinstance(data, dict):
        return errors

    errors.extend(_check_unknown_keys(data, _ALLOWED_TEMPLATE_TOP_KEYS, "root"))

    templates = data.get("templates", {})
    if not isinstance(templates, dict):
        errors.append("templates: expected dict")
        return errors

    for tmpl_name, tmpl_cfg in templates.items():
        tmpl_path = f"templates.{tmpl_name}"
        if not isinstance(tmpl_cfg, dict):
            errors.append(f"{tmpl_path}: expected dict")
            continue
        errors.extend(_check_missing_keys(tmpl_cfg, _TEMPLATE_REQUIRED_TOP_FIELDS,
                                          tmpl_path))
        rcparams = tmpl_cfg.get("rcparams")
        if rcparams is not None:
            errors.extend(_check_type(rcparams, dict, f"{tmpl_path}.rcparams"))

    return errors


def validate_all(data: dict) -> list[str]:
    """Run all validators on a merged config dict.

    Extracts each section from the merged dict and validates independently.
    This avoids unknown-key false positives when multiple configs are combined.
    """
    errors: list[str] = []

    if "studies" in data:
        studies_section = {"studies": data["studies"]}
        errors.extend(validate_studies_config(studies_section))

    if any(k in data for k in ("device_types", "legacy_to_study")):
        devices_section = {k: v for k, v in data.items()
                           if k in _ALLOWED_DEVICES_TOP_KEYS}
        if devices_section:
            errors.extend(validate_devices_config(devices_section))

    if "instruments" in data:
        instr_section = {"instruments": data["instruments"]}
        errors.extend(validate_instruments_config(instr_section))

    if "file_naming" in data:
        grammar_section = {"file_naming": data["file_naming"]}
        errors.extend(validate_grammar_config(grammar_section))

    if "templates" in data:
        tmpl_section = {"templates": data["templates"]}
        errors.extend(validate_template_config(tmpl_section))

    return errors
