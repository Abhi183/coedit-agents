"""Immutable data types shared by the store, conflict detector and MCP server."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Optional

WHOLE_FILE = 0  # start_line/end_line of 0 means "the entire file"


@dataclass(frozen=True)
class Region:
    """A span of a file. Lines are 1-based and inclusive. Zero means whole file."""

    path: str
    start_line: int = WHOLE_FILE
    end_line: int = WHOLE_FILE
    symbol: Optional[str] = None

    @property
    def whole_file(self) -> bool:
        return self.start_line == WHOLE_FILE or self.end_line == WHOLE_FILE

    def overlaps(self, other: "Region") -> bool:
        if self.path != other.path:
            return False
        if self.whole_file or other.whole_file:
            return True
        return self.start_line <= other.end_line and other.start_line <= self.end_line

    def is_adjacent(self, other: "Region", gap: int = 2) -> bool:
        """True when the regions do not overlap but sit within `gap` lines of each other."""
        if self.path != other.path or self.overlaps(other):
            return False
        if self.whole_file or other.whole_file:
            return False
        distance = max(other.start_line - self.end_line, self.start_line - other.end_line)
        return 0 < distance <= gap

    def describe(self) -> str:
        if self.whole_file:
            return f"{self.path} (whole file)"
        label = f"{self.path}:{self.start_line}-{self.end_line}"
        return f"{label} [{self.symbol}]" if self.symbol else label

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Region":
        return cls(**data)


@dataclass(frozen=True)
class Lease:
    """An advisory claim on a region, with a stated intent and an expiry."""

    id: str
    agent: str
    region: Region
    intent: str
    created_at: float
    expires_at: float

    def is_expired(self, now: float) -> bool:
        return now >= self.expires_at

    def renewed(self, expires_at: float) -> "Lease":
        return replace(self, expires_at=expires_at)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "region": self.region.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Lease":
        return cls(**{**data, "region": Region.from_dict(data["region"])})


@dataclass(frozen=True)
class Edit:
    """A recorded, attributed change. The text lives on disk; this is provenance."""

    id: str
    agent: str
    region: Region
    summary: str
    created_at: float
    symbols_changed: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "region": self.region.to_dict(),
                "symbols_changed": list(self.symbols_changed)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Edit":
        return cls(**{**data, "region": Region.from_dict(data["region"]),
                      "symbols_changed": tuple(data.get("symbols_changed", ()))})


@dataclass(frozen=True)
class Message:
    """A short note from one agent to another (or to all, recipient='*')."""

    id: str
    sender: str
    recipient: str
    body: str
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(**data)
