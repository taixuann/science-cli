"""Device assignment service: maps device/material specifications to memristor models.

This module provides a pure assignment service that accepts device/material
specifications and returns the appropriate memristor model configuration.
It is independent of the IV-sweep measurement module.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class MaterialType(Enum):
    """Known memristor material systems used in the lab."""

    TA_PDA_ITO = "Ta-PDA-ITO"
    TA_PDAC_ITO = "Ta-PDAc-ITO"
    PDA_ITO = "PDA-ITO"
    ALOX = "AlOx"
    HFOX = "HfOx"
    TIO2 = "TiO2"
    WOX = "WOx"
    CUSTOM = "custom"


class MemristorModel(Enum):
    """Memristor compact models available for assignment."""

    # Physics-based models
    ASU = "ASU"  # Arizona State University model
    STANFORD = "Stanford"  # Stanford/HP model
    KNOWM = "Knowm"  # Knowm Inc. model
    YAKOPOVCIC = "Yakopcic"  # Yakopcic/TaOx model
    PICKETT = "Pickett"  # Pickett/TiO2 model

    # Empirical/behavioral models
    JILES_AHERN = "Jiles-Ahner"  # Magnetic-inspired (adapted)
    VTEAM = "VTEAM"  # Voltage-Team threshold switching
    THRESHOLD_SWITCHING = "ThresholdSwitching"  # Generic threshold switching

    # No model (pure measurement)
    NONE = "none"


@dataclass
class DeviceGeometry:
    """Physical device geometry specification."""

    rows: int = 1
    cols: int = 1
    cell_area_um2: Optional[float] = None
    top_electrode: str = "Ta"
    bottom_electrode: str = "ITO"
    active_layer: str = "PDA"
    active_layer_thickness_nm: Optional[float] = None
    doping: Optional[str] = None


@dataclass
class MaterialSpec:
    """Material specification for a memristor device."""

    material_type: MaterialType
    batch: str = ""
    geometry: DeviceGeometry = field(default_factory=DeviceGeometry)
    custom_params: dict = field(default_factory=dict)

    @property
    def material_key(self) -> str:
        """Generate material key like 'Ta-PDA-ITO(1)'."""
        base = self.material_type.value
        if self.batch:
            return f"{base}({self.batch})"
        return base

    @classmethod
    def from_material_key(cls, key: str) -> "MaterialSpec":
        """Parse material key like 'Ta-PDA-ITO(1)' into a MaterialSpec.

        Args:
            key: Material key string (e.g., "Ta-PDA-ITO(1)", "AlOx", "HfOx(2)")

        Returns:
            MaterialSpec instance
        """
        import re

        match = re.match(r"^([A-Za-z0-9\-/]+)(?:\(([A-Za-z0-9]+)\))?$", key)
        if not match:
            return cls(material_type=MaterialType.CUSTOM, custom_params={"raw_key": key})

        material_str, batch = match.groups()
        batch = batch or ""

        # Map known material strings to MaterialType
        material_type = MaterialType.CUSTOM
        for mt in MaterialType:
            if mt.value.replace("-", "").replace("_", "").lower() == material_str.replace("-", "").replace("_", "").lower():
                material_type = mt
                break

        # Store raw key for custom materials
        custom_params = {}
        if material_type == MaterialType.CUSTOM:
            custom_params["raw_key"] = key

        return cls(material_type=material_type, batch=batch, custom_params=custom_params)


@dataclass
class ModelConfig:
    """Configuration returned by the assignment service for a given material."""

    model: MemristorModel
    material_spec: MaterialSpec
    switching_params: dict = field(default_factory=dict)
    endurance_params: dict = field(default_factory=dict)
    retention_params: dict = field(default_factory=dict)
    analysis_defaults: dict = field(default_factory=dict)
    plotting_defaults: dict = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "model": self.model.value,
            "material_key": self.material_spec.material_key,
            "material_type": self.material_spec.material_type.value,
            "batch": self.material_spec.batch,
            "geometry": {
                "rows": self.material_spec.geometry.rows,
                "cols": self.material_spec.geometry.cols,
                "cell_area_um2": self.material_spec.geometry.cell_area_um2,
                "top_electrode": self.material_spec.geometry.top_electrode,
                "bottom_electrode": self.material_spec.geometry.bottom_electrode,
                "active_layer": self.material_spec.geometry.active_layer,
                "active_layer_thickness_nm": self.material_spec.geometry.active_layer_thickness_nm,
                "doping": self.material_spec.geometry.doping,
            },
            "switching_params": self.switching_params,
            "endurance_params": self.endurance_params,
            "retention_params": self.retention_params,
            "analysis_defaults": self.analysis_defaults,
            "plotting_defaults": self.plotting_defaults,
            "notes": self.notes,
        }


# Material-to-model mapping registry
# Maps MaterialType to default ModelConfig
_MATERIAL_REGISTRY: dict[MaterialType, ModelConfig] = {}


def _register_material(material_type: MaterialType, config: ModelConfig) -> None:
    """Register a material configuration."""
    _MATERIAL_REGISTRY[material_type] = config


def _build_default_config(material_type: MaterialType, material_spec: MaterialSpec) -> ModelConfig:
    """Build a default configuration for a material type."""
    base = ModelConfig(
        model=MemristorModel.NONE,
        material_spec=material_spec,
        notes=f"Default configuration for {material_type.value}",
    )

    # Material-specific defaults
    if material_type == MaterialType.TA_PDA_ITO:
        base.model = MemristorModel.VTEAM
        base.switching_params = {
            "v_read": 0.1,
            "expected_vset_range": (0.5, 2.0),
            "expected_vreset_range": (-2.0, -0.5),
            "on_off_ratio_min": 10,
        }
        base.endurance_params = {
            "read_voltage": 0.1,
            "failure_threshold_ratio": 10,
            "expected_cycles": 1000,
        }
        base.retention_params = {
            "read_voltage": 0.1,
            "temperature_k": 298,
            "decay_model_preference": "log",
        }
        base.plotting_defaults = {
            "xlabel": "Voltage (V)",
            "ylabel": "Current (A)",
            "color": "#2E86AB",
        }
        base.notes = "Ta/PDA/ITO: organic-inorganic memristor, VTEAM model suitable"

    elif material_type == MaterialType.TA_PDAC_ITO:
        base.model = MemristorModel.VTEAM
        base.switching_params = {
            "v_read": 0.1,
            "expected_vset_range": (0.4, 1.8),
            "expected_vreset_range": (-1.8, -0.4),
            "on_off_ratio_min": 15,
        }
        base.endurance_params = {
            "read_voltage": 0.1,
            "failure_threshold_ratio": 10,
            "expected_cycles": 2000,
        }
        base.retention_params = {
            "read_voltage": 0.1,
            "temperature_k": 298,
            "decay_model_preference": "log",
        }
        base.plotting_defaults = {
            "xlabel": "Voltage (V)",
            "ylabel": "Current (A)",
            "color": "#A23B72",
        }
        base.notes = "Ta/PDAc/ITO: modified PDA, higher endurance expected"

    elif material_type == MaterialType.PDA_ITO:
        base.model = MemristorModel.THRESHOLD_SWITCHING
        base.switching_params = {
            "v_read": 0.1,
            "expected_vset_range": (0.8, 3.0),
            "expected_vreset_range": (-3.0, -0.8),
            "on_off_ratio_min": 5,
        }
        base.endurance_params = {
            "read_voltage": 0.1,
            "failure_threshold_ratio": 5,
            "expected_cycles": 500,
        }
        base.retention_params = {
            "read_voltage": 0.1,
            "temperature_k": 298,
            "decay_model_preference": "power",
        }
        base.plotting_defaults = {
            "xlabel": "Voltage (V)",
            "ylabel": "Current (A)",
            "color": "#F18F01",
        }
        base.notes = "PDA/ITO: pure organic, threshold switching dominant"

    elif material_type == MaterialType.ALOX:
        base.model = MemristorModel.YAKOPOVCIC
        base.switching_params = {
            "v_read": 0.2,
            "expected_vset_range": (1.0, 3.5),
            "expected_vreset_range": (-3.5, -1.0),
            "on_off_ratio_min": 50,
        }
        base.endurance_params = {
            "read_voltage": 0.2,
            "failure_threshold_ratio": 10,
            "expected_cycles": 10000,
        }
        base.retention_params = {
            "read_voltage": 0.2,
            "temperature_k": 298,
            "decay_model_preference": "log",
        }
        base.plotting_defaults = {
            "xlabel": "Voltage (V)",
            "ylabel": "Current (A)",
            "color": "#C73E1D",
        }
        base.notes = "AlOx: oxide-based, Yakopcic model for valence change"

    elif material_type == MaterialType.HFOX:
        base.model = MemristorModel.YAKOPOVCIC
        base.switching_params = {
            "v_read": 0.2,
            "expected_vset_range": (1.2, 4.0),
            "expected_vreset_range": (-4.0, -1.2),
            "on_off_ratio_min": 100,
        }
        base.endurance_params = {
            "read_voltage": 0.2,
            "failure_threshold_ratio": 10,
            "expected_cycles": 50000,
        }
        base.retention_params = {
            "read_voltage": 0.2,
            "temperature_k": 298,
            "decay_model_preference": "log",
        }
        base.plotting_defaults = {
            "xlabel": "Voltage (V)",
            "ylabel": "Current (A)",
            "color": "#592E83",
        }
        base.notes = "HfOx: high-k oxide, excellent retention"

    elif material_type == MaterialType.TIO2:
        base.model = MemristorModel.PICKETT
        base.switching_params = {
            "v_read": 0.1,
            "expected_vset_range": (0.8, 2.5),
            "expected_vreset_range": (-2.5, -0.8),
            "on_off_ratio_min": 1000,
        }
        base.endurance_params = {
            "read_voltage": 0.1,
            "failure_threshold_ratio": 100,
            "expected_cycles": 100000,
        }
        base.retention_params = {
            "read_voltage": 0.1,
            "temperature_k": 298,
            "decay_model_preference": "log",
        }
        base.plotting_defaults = {
            "xlabel": "Voltage (V)",
            "ylabel": "Current (A)",
            "color": "#1B998B",
        }
        base.notes = "TiO2: classic HP memristor material, Pickett model"

    elif material_type == MaterialType.WOX:
        base.model = MemristorModel.YAKOPOVCIC
        base.switching_params = {
            "v_read": 0.15,
            "expected_vset_range": (1.0, 3.0),
            "expected_vreset_range": (-3.0, -1.0),
            "on_off_ratio_min": 20,
        }
        base.endurance_params = {
            "read_voltage": 0.15,
            "failure_threshold_ratio": 20,
            "expected_cycles": 10000,
        }
        base.retention_params = {
            "read_voltage": 0.15,
            "temperature_k": 298,
            "decay_model_preference": "log",
        }
        base.plotting_defaults = {
            "xlabel": "Voltage (V)",
            "ylabel": "Current (A)",
            "color": "#ED217C",
        }
        base.notes = "WOx: tungsten oxide, bipolar switching"

    else:
        # Custom material - use threshold switching as generic default
        base.model = MemristorModel.THRESHOLD_SWITCHING
        base.switching_params = {
            "v_read": 0.1,
            "expected_vset_range": (0.5, 3.0),
            "expected_vreset_range": (-3.0, -0.5),
            "on_off_ratio_min": 10,
        }
        base.endurance_params = {
            "read_voltage": 0.1,
            "failure_threshold_ratio": 10,
            "expected_cycles": 1000,
        }
        base.retention_params = {
            "read_voltage": 0.1,
            "temperature_k": 298,
            "decay_model_preference": "log",
        }
        base.plotting_defaults = {
            "xlabel": "Voltage (V)",
            "ylabel": "Current (A)",
            "color": "#666666",
        }
        base.notes = f"Custom material: {material_spec.material_key}"

    return base


def assign_device(
    material_spec: MaterialSpec,
    override_model: Optional[MemristorModel] = None,
    custom_config: Optional[dict] = None,
) -> ModelConfig:
    """Assign a memristor model and configuration to a device based on material.

    This is the main entry point for the device assignment service.

    Args:
        material_spec: Device material specification (type, batch, geometry).
        override_model: Optional explicit model override.
        custom_config: Optional custom configuration to merge with defaults.

    Returns:
        ModelConfig with assigned model, parameters, and defaults.
    """
    # Get or build base configuration for this material type
    if material_spec.material_type in _MATERIAL_REGISTRY:
        config = _MATERIAL_REGISTRY[material_spec.material_type]
        # Create a new config with the provided material_spec (may have different batch/geometry)
        config = ModelConfig(
            model=config.model,
            material_spec=material_spec,
            switching_params=config.switching_params.copy(),
            endurance_params=config.endurance_params.copy(),
            retention_params=config.retention_params.copy(),
            analysis_defaults=config.analysis_defaults.copy(),
            plotting_defaults=config.plotting_defaults.copy(),
            notes=config.notes,
        )
    else:
        config = _build_default_config(material_spec.material_type, material_spec)

    # Apply model override if provided
    if override_model is not None:
        config.model = override_model

    # Merge custom configuration
    if custom_config:
        if "switching_params" in custom_config:
            config.switching_params.update(custom_config["switching_params"])
        if "endurance_params" in custom_config:
            config.endurance_params.update(custom_config["endurance_params"])
        if "retention_params" in custom_config:
            config.retention_params.update(custom_config["retention_params"])
        if "analysis_defaults" in custom_config:
            config.analysis_defaults.update(custom_config["analysis_defaults"])
        if "plotting_defaults" in custom_config:
            config.plotting_defaults.update(custom_config["plotting_defaults"])
        if "notes" in custom_config:
            config.notes = custom_config["notes"]

    return config


def assign_device_from_key(
    material_key: str,
    override_model: Optional[MemristorModel] = None,
    geometry: Optional[DeviceGeometry] = None,
    custom_config: Optional[dict] = None,
) -> ModelConfig:
    """Convenience function to assign from a material key string.

    Args:
        material_key: Material key like "Ta-PDA-ITO(1)", "AlOx", "HfOx(2)"
        override_model: Optional explicit model override.
        geometry: Optional device geometry.
        custom_config: Optional custom configuration.

    Returns:
        ModelConfig for the material.
    """
    spec = MaterialSpec.from_material_key(material_key)
    if geometry:
        spec.geometry = geometry
    return assign_device(spec, override_model, custom_config)


def list_known_materials() -> list[dict]:
    """List all known material types with their default models.

    Returns:
        List of dicts with material info.
    """
    result = []
    for mt in MaterialType:
        if mt == MaterialType.CUSTOM:
            continue
        spec = MaterialSpec(material_type=mt)
        config = _build_default_config(mt, spec)
        result.append(
            {
                "material_type": mt.value,
                "default_model": config.model.value,
                "notes": config.notes,
            }
        )
    return result


def get_assignment_for_protocol(
    protocol_materials: list[str],
    default_geometry: Optional[DeviceGeometry] = None,
) -> dict[str, ModelConfig]:
    """Get model assignments for all materials in a protocol.

    Args:
        protocol_materials: List of material keys from protocol.
        default_geometry: Default geometry to use if not specified.

    Returns:
        Dict mapping material key to ModelConfig.
    """
    assignments = {}
    for mat_key in protocol_materials:
        spec = MaterialSpec.from_material_key(mat_key)
        if default_geometry and (
            spec.geometry.rows == 1
            and spec.geometry.cols == 1
            and spec.geometry.cell_area_um2 is None
        ):
            spec.geometry = default_geometry
        assignments[mat_key] = assign_device(spec)
    return assignments


# Initialize registry with default configurations
for mt in MaterialType:
    if mt != MaterialType.CUSTOM:
        spec = MaterialSpec(material_type=mt)
        _register_material(mt, _build_default_config(mt, spec))

__all__ = [
    "MaterialType",
    "MemristorModel",
    "DeviceGeometry",
    "MaterialSpec",
    "ModelConfig",
    "assign_device",
    "assign_device_from_key",
    "list_known_materials",
    "get_assignment_for_protocol",
]