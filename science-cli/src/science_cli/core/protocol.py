"""Protocol validation — checks protocol structure for completeness."""


def validate_protocol(data: dict) -> list[str]:
    """Validate a protocol dict and return a list of warnings.

    Args:
        data: Protocol dict with expected keys 'name' and 'steps'.

    Returns:
        List of warning strings (empty if valid).
    """
    warnings = []
    if not data.get("name"):
        warnings.append("Protocol has no name")
    if not data.get("steps"):
        warnings.append("Protocol has no steps")
    return warnings
