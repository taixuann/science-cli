"""Instrument model data models."""

from dataclasses import dataclass, field


@dataclass
class InstrumentConfig:
    delimiter: str = ","
    decimal: str = "."
    header_lines: int = 0
    encoding: str = "utf-8"

    @classmethod
    def from_dict(cls, d: dict) -> "InstrumentConfig":
        return cls(
            delimiter=d.get("delimiter", ","),
            decimal=d.get("decimal", "."),
            header_lines=d.get("header_lines", 0),
            encoding=d.get("encoding", "utf-8"),
        )

    def to_dict(self) -> dict:
        return {
            "delimiter": self.delimiter,
            "decimal": self.decimal,
            "header_lines": self.header_lines,
            "encoding": self.encoding,
        }


@dataclass
class Instrument:
    name: str
    label: str
    type: str
    location: str = ""
    techniques: list[str] = field(default_factory=list)
    config: InstrumentConfig = field(default_factory=InstrumentConfig)

    @classmethod
    def from_dict(cls, name: str, d: dict) -> "Instrument":
        return cls(
            name=name,
            label=d.get("label", name),
            location=d.get("location", ""),
            type=d.get("type", "unknown"),
            techniques=d.get("techniques", []),
            config=InstrumentConfig.from_dict(d.get("config", {})),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "location": self.location,
            "type": self.type,
            "techniques": sorted(self.techniques),
            "config": self.config.to_dict(),
        }
