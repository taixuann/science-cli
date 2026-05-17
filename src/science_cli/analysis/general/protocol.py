"""Shim: analysis/general/protocol."""


def validate_protocol(data):
    warnings = []
    if not data.get("name"):
        warnings.append("Protocol has no name")
    if not data.get("steps"):
        warnings.append("Protocol has no steps")
    return warnings
