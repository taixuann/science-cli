"""Technique detection from filenames — merges hardcoded + config patterns.

Resolution order for patterns (4-tier):
    1. Project-level overrides — highest priority
    2. Global config patterns
    3. Hardcoded fallback grammar patterns
    4. Per-field extract specs (e.g., matrix row/col)

All parsed results are normalized via standardize_grammar_fields() to include
5 universal fields: date_code, material, technique, matrix, suffix.
"""

import re
from dataclasses import dataclass, field


def _find_column(preferred: str, aliases: list[str], columns: list[str]) -> str:
    """Find the first matching column name from preferred + aliases."""
    candidates = [preferred] + list(aliases) if preferred else list(aliases)
    for c in candidates:
        if c in columns:
            return c
    return ""


@dataclass
class ColumnMap:
    """Maps standard column roles to file-specific column names."""
    x: str = ""
    y: str = ""
    x_label: str = ""
    y_label: str = ""
    extras: dict = field(default_factory=dict)
    x_aliases: list[str] = field(default_factory=list)
    y_aliases: list[str] = field(default_factory=list)

    def resolve(self, columns: list[str]) -> tuple[str, str, str, str, dict[str, str]]:
        xcol = _find_column(self.x, self.x_aliases, columns)
        ycol = _find_column(self.y, self.y_aliases, columns)
        xlabel = self.x_label or xcol or "X"
        ylabel = self.y_label or ycol or "Y"
        resolved_extras: dict[str, str] = {}
        for role, preferred in self.extras.items():
            found = _find_column(preferred, [], columns)
            if found:
                resolved_extras[role] = found
        return xcol, ycol, xlabel, ylabel, resolved_extras


@dataclass
class TechniqueDef:
    name: str
    label: str
    patterns: list[str]
    description: str = ""


# Hardcoded fallback patterns — used when no config or extensions exist
PATTERNS: dict[str, list[str]] = {
    "ec-cv": [r"_CV\.", r"\.cv$", r"cv_", r"cv-"],
    "ec-ca": [r"_CA\.", r"\.ca$", r"ca_", r"ca-"],
    "ec-eis": [r"\.mpt$", r"_EIS\.", r"\.eis$", r"_impedance", r"\.z"],
    "ec-lsv": [r"_LSV\.", r"\.lsv$"],
    "ec-swv": [r"_SWV\.", r"\.swv$"],
    "iv-sweep": [r"_IV\.", r"\.iv$", r"iv_", r"iv-", r"_sweep", r"sweep_"],
    "iv-breakdown": [r"_bd\.", r"breakdown_", r"_Vbd", r"bd_"],
    "iv-leakage": [r"_leak", r"leakage_", r"leak_"],
    "mem-endurance": [r"_endurance", r"\.end", r"end_", r"endurance", r"-endurance"],
    "mem-retention": [r"_retention", r"\.ret", r"ret_", r"retention", r"-retention"],
    "mem-switching": [r"_switch", r"\.sw", r"sw_", r"switch_", r"-switch"],
    "raman": [r"_raman", r"_sers", r"_raman-sers", r"_SERS"],
    "uv-vis": [r"_uv-vis", r"_uvvis", r"uv-vis", r"uvvis"],
}


# Hardcoded grammar fallback patterns — used when no config grammar exists
HARDCODED_GRAMMAR: dict = {
    "patterns": [
        {
            "regex": r"(?P<date_code>\d{6,8})[_-](?P<material>[A-Za-z0-9]+)[_-](?P<technique>[A-Za-z0-9]+)[_-]?(?P<matrix>[A-Za-z0-9\-\+]+)?[_-]?(?P<suffix>\d+)?",
            "description": "Standard: date_material_technique_matrix_suffix",
            "fields": [
                {"name": "date_code", "description": "Date code (YYYYMMDD)"},
                {"name": "material", "description": "Material name or code"},
                {"name": "technique", "description": "Technique abbreviation"},
                {"name": "matrix", "description": "Matrix position (r0c0 or b1-t1)", "extract": r"r(?P<row>\d+)c(?P<col>\d+)"},
                {"name": "suffix", "description": "Run number suffix"},
            ],
        },
    ],
}


# Built-in technique definitions — replaces extension registry
BUILTIN_TECHNIQUES: dict[str, TechniqueDef] = {
    "iv-sweep": TechniqueDef(name="iv-sweep", label="IV Sweep", patterns=[r"_IV\.", r"\.iv$", r"iv_", r"iv-", r"_sweep", r"sweep_"], description="Current-Voltage sweep"),
    "iv-breakdown": TechniqueDef(name="iv-breakdown", label="Breakdown", patterns=[r"_bd\.", r"breakdown_", r"_Vbd", r"bd_"], description="Ramped voltage to breakdown"),
    "iv-leakage": TechniqueDef(name="iv-leakage", label="Leakage", patterns=[r"_leak", r"leakage_", r"leak_"], description="Low-bias leakage current"),
    "ec-cv": TechniqueDef(name="ec-cv", label="CV", patterns=[r"_CV\.", r"\.cv$", r"cv_", r"cv-"], description="Cyclic Voltammetry"),
    "ec-ca": TechniqueDef(name="ec-ca", label="CA", patterns=[r"_CA\.", r"\.ca$", r"ca_", r"ca-"], description="Chronoamperometry"),
    "ec-eis": TechniqueDef(name="ec-eis", label="EIS", patterns=[r"\.mpt$", r"_EIS\.", r"\.eis$", r"_impedance", r"\.z"], description="Electrochemical Impedance Spectroscopy"),
    "ec-lsv": TechniqueDef(name="ec-lsv", label="LSV", patterns=[r"_LSV\.", r"\.lsv$"], description="Linear Sweep Voltammetry"),
    "ec-swv": TechniqueDef(name="ec-swv", label="SWV", patterns=[r"_SWV\.", r"\.swv$"], description="Square Wave Voltammetry"),
    "mem-endurance": TechniqueDef(name="mem-endurance", label="Endurance", patterns=[r"_endurance", r"\.end", r"end_", r"endurance", r"-endurance"], description="DC/pulsed endurance cycling"),
    "mem-retention": TechniqueDef(name="mem-retention", label="Retention", patterns=[r"_retention", r"\.ret", r"ret_", r"retention", r"-retention"], description="Retention time test"),
    "mem-switching": TechniqueDef(name="mem-switching", label="Switching", patterns=[r"_switch", r"\.sw", r"sw_", r"switch_", r"-switch"], description="Switching time / voltage characterization"),
}


def _config_patterns() -> dict[str, list[str]]:
    """Try loading technique patterns from the config system.

    Tries get_technique_config() first (complete dict), falling back to
    get_technique_patterns() (patterns only). Config patterns are prepended
    (take priority) before hardcoded ones.
    Returns a dict of technique → patterns, or empty dict on failure.
    """
    try:
        from science_cli.core.config import get_technique_config, get_technique_patterns
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        project_root = proj if proj else None
        result: dict[str, list[str]] = {}
        # Get patterns for all known techniques (config may add new ones)
        all_techs = set(PATTERNS.keys())
        for tech in all_techs:
            # Try full technique config first (may have patterns + more)
            tconfig = get_technique_config(tech, project_root)
            if tconfig and "patterns" in tconfig:
                result[tech] = tconfig["patterns"]
            else:
                # Fall back to get_technique_patterns()
                patterns = get_technique_patterns(tech, project_root)
                if patterns != PATTERNS.get(tech, []):
                    result[tech] = patterns
        return result
    except ImportError:
        return {}


def _all_patterns() -> dict[str, list[str]]:
    """Merge config and hardcoded patterns. Priority: config > hardcoded."""
    patterns: dict[str, list[str]] = {}
    for tech, pats in PATTERNS.items():
        patterns[tech] = list(pats)
    # Layer config on top (highest priority)
    for tech, pats in _config_patterns().items():
        if tech not in patterns:
            patterns[tech] = []
        existing = patterns[tech]
        new = [p for p in pats if p not in existing]
        patterns[tech] = new + existing
    return patterns


def detect_technique(filename: str) -> str:
    """Detect technique from filename using merged patterns.

    Checks: config patterns first, then hardcoded.
    Gracefully skips invalid regex patterns (e.g. glob-style ``*pattern*``).
    """
    for tech, patterns in _all_patterns().items():
        for p in patterns:
            try:
                if re.search(p, filename, re.IGNORECASE):
                    return tech
            except re.error:
                continue
    return ""


def technique_label(tech: str) -> str:
    """Return a human-readable label for a technique key."""
    labels = {
        "ec-cv": "CV",
        "ec-ca": "CA",
        "ec-eis": "EIS",
        "ec-lsv": "LSV",
        "ec-swv": "SWV",
        "iv-sweep": "IV Sweep",
        "iv-breakdown": "Breakdown",
        "iv-leakage": "Leakage",
        "mem-endurance": "Endurance",
        "mem-retention": "Retention",
        "mem-switching": "Switching",
    }
    return labels.get(tech, tech.upper())


def get_technique_label(technique: str, project_root=None) -> str:
    """Return a human-readable label for a technique, checking config first.

    Checks get_technique_config() for a ``label`` field first,
    then falls back to the hardcoded technique_label() function.
    """
    try:
        from science_cli.core.config import get_technique_config
        tconfig = get_technique_config(technique, project_root)
        if tconfig and "label" in tconfig:
            return tconfig["label"]
    except ImportError:
        pass
    return technique_label(technique)


def _merge_grammar(base: dict, override: dict) -> dict:
    """Merge two grammar dicts, with override patterns taking priority.

    Override patterns are prepended before base patterns. Duplicate regexes
    are skipped (first occurrence wins based on priority order).
    Top-level non-pattern keys from override are applied to the result.
    """
    merged = dict(base)
    base_patterns = merged.get("patterns", [])
    override_patterns = override.get("patterns", [])

    existing_regexes: set[str] = set()
    new_patterns: list[dict] = []

    # Prepend override patterns first (highest priority)
    for p in override_patterns:
        regex = p.get("regex", "")
        if regex and regex not in existing_regexes:
            new_patterns.append(dict(p))
            existing_regexes.add(regex)

    # Append base patterns (lower priority), skipping dupes
    for p in base_patterns:
        regex = p.get("regex", "")
        if regex and regex not in existing_regexes:
            new_patterns.append(dict(p))
            existing_regexes.add(regex)

    merged["patterns"] = new_patterns

    # Merge top-level keys from override (non-patterns)
    for k, v in override.items():
        if k != "patterns":
            merged[k] = v

    return merged


def _resolve_grammar_from_merged_config(project_root=None) -> dict:
    """Resolve file naming grammar via 4-tier resolution chain.

    Resolution order:
        1. Hardcoded grammar (fallback base) — lowest priority
        2. Global config patterns via get_file_naming_grammar()
        3. Project-level overrides (via project_root) — highest priority
        4. Per-pattern extract specs applied at match time

    Returns merged grammar dict with ``patterns`` key.
    """
    merged = dict(HARDCODED_GRAMMAR)

    try:
        from science_cli.core.config import get_file_naming_grammar

        # Layer 2: Global config grammar
        global_grammar = get_file_naming_grammar(None)
        if global_grammar and global_grammar.get("patterns"):
            merged = _merge_grammar(merged, global_grammar)

        # Layer 3: Project-level overrides (only if different from global)
        if project_root is not None:
            proj_grammar = get_file_naming_grammar(project_root)
            if (
                proj_grammar
                and proj_grammar.get("patterns")
                and proj_grammar != global_grammar
            ):
                merged = _merge_grammar(merged, proj_grammar)

        return merged
    except ImportError:
        return merged


def parse_filename_grammar(filename: str, project_root=None) -> dict:
    """Parse a filename using the configured naming grammar patterns (4-tier resolution).

    Resolution order:
        1. Hardcoded grammar patterns (in this file as fallback)
        2. Global config patterns via get_file_naming_grammar()
        3. Project-level overrides (via project_root)
        4. Per-pattern extract specs applied to extract row/col from matrix

    Returns dict with extracted fields (date_code, material, technique, matrix,
    suffix) normalized via standardize_grammar_fields(), or dict with
    ``parse_error`` key if no pattern matches.

    When *project_root* is ``None``, attempts to auto-detect from session.
    """

    if project_root is None:
        try:
            from science_cli.core.project import get_current_project_path
            project_root = get_current_project_path()
        except ImportError:
            pass

    grammar = _resolve_grammar_from_merged_config(project_root)
    patterns = grammar.get("patterns", [])

    if not patterns:
        return {"parse_error": "no naming patterns configured"}

    for pattern in patterns:
        regex = pattern.get("regex")
        if not regex:
            continue
        try:
            m = re.search(regex, filename, re.IGNORECASE)
        except re.error:
            continue

        if m:
            result = m.groupdict()

            # Collect extract specs from both formats:
            # 1. Pattern-level "extract" dict: {matrix: "r...", ...}
            extracts: dict[str, str] = {}
            if "extract" in pattern:
                extracts.update(pattern["extract"])

            # 2. Per-field extract (fields is a LIST of dicts with 'name' + 'extract')
            fields_spec = pattern.get("fields", [])
            if isinstance(fields_spec, list):
                for fd in fields_spec:
                    if isinstance(fd, dict) and "extract" in fd:
                        fname = fd.get("name", "")
                        if fname:
                            extracts[fname] = fd["extract"]

            # Apply all extract sub-regexes
            for field, extract_spec in extracts.items():
                if field in result and result[field]:
                    try:
                        em = re.search(extract_spec, result[field])
                        if em:
                            result.update(em.groupdict())
                    except re.error:
                        pass
            # Normalize to universal fields
            return standardize_grammar_fields(result)

    return {"parse_error": "no matching pattern"}


def standardize_grammar_fields(parsed: dict) -> dict:
    """Normalize a parsed grammar result to include ALL 5 universal fields.
    
    Ensures every result has: date_code, material, technique, matrix, suffix.
    Missing fields are set to None.
    
    Also extracts row/col from matrix field if present.
    """
    result = dict(parsed)

    # Ensure universal fields exist
    for field in ("date_code", "material", "technique", "matrix", "suffix"):
        if field not in result:
            result[field] = None

    # Extract row/col from matrix field (e.g., "r0c0" or "r1-c1" -> row=0/1, col=0/1)
    if result.get("matrix") and ("row" not in result or result["row"] is None):
        m = re.search(r'r(\d+)-?c(\d+)', str(result["matrix"]), re.IGNORECASE)
        if m:
            result["row"] = int(m.group(1))
            result["col"] = int(m.group(2))

    # Also parse bN-tN format
    if result.get("matrix") and ("row" not in result or result["row"] is None):
        m = re.search(r'b(\d+)-t(\d+)', str(result["matrix"]), re.IGNORECASE)
        if m:
            result["row"] = int(m.group(2)) - 1  # tN -> 0-indexed row
            result["col"] = int(m.group(1)) - 1  # bN -> 0-indexed col

    # Convert suffix to int if possible
    if result.get("suffix") is not None:
        try:
            result["suffix"] = int(result["suffix"])
        except (ValueError, TypeError):
            pass

    return result
