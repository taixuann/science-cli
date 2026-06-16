"""PVD deposition analysis — thickness, rate, uniformity."""
import numpy as np


def analyze_deposition(layers):
    """Analyze deposition run data.
    
    Args:
        layers: List of DepositionLayer objects.
    
    Returns:
        dict with total thickness, material list, layer counts, uniformity stats.
    """
    if not layers:
        return {"error": "No deposition layers provided", "total_thickness_nm": 0.0}
    
    materials = list(dict.fromkeys([l.material for l in layers]))
    total_thickness = sum(l.thickness_nm for l in layers)
    rates = [l.rate_nm_s for l in layers if l.rate_nm_s > 0]
    
    result = {
        "total_thickness_nm": float(total_thickness),
        "n_layers": len(layers),
        "materials": materials,
        "layer_stack": [
            {"material": l.material, "thickness_nm": l.thickness_nm,
             "rate_nm_s": l.rate_nm_s, "temperature_c": l.temperature_c}
            for l in layers
        ],
    }
    
    if rates:
        result["mean_rate_nm_s"] = float(np.mean(rates))
        result["rate_std_nm_s"] = float(np.std(rates))
    
    return result


def deposition_summary(analysis):
    """Human-readable deposition summary."""
    if "error" in analysis:
        return f"Deposition Analysis: {analysis['error']}"
    lines = [
        f"Deposition: {analysis['n_layers']} layers, {analysis['total_thickness_nm']:.1f} nm total",
        f"  Materials: {', '.join(analysis['materials'])}",
    ]
    for i, layer in enumerate(analysis.get("layer_stack", [])):
        lines.append(f"  Layer {i+1}: {layer['material']} - {layer['thickness_nm']:.1f} nm @ {layer['rate_nm_s']:.2f} nm/s")
    return "\n".join(lines)
