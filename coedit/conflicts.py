"""Classify how a proposed region interacts with other agents' active leases.

Severity ladder, from the Docs analogy outward:
  NONE      disjoint, carry on
  ADJACENT  within a couple of lines of someone else's region; textual merge may still
            interleave, so the agent is warned
  OVERLAP   same lines; advisory block
  SEMANTIC  no line overlap, but the region defines a symbol that another agent's
            leased region references (or vice versa); a line-level merge would succeed
            and then break at runtime
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .models import Lease, Region
from .regions import python_symbols, symbols_in_lines

ADJACENT_GAP = 2


class Severity(str, Enum):
    NONE = "none"
    ADJACENT = "adjacent"
    OVERLAP = "overlap"
    SEMANTIC = "semantic"


@dataclass(frozen=True)
class SemanticConflict:
    symbol: str
    agent: str
    direction: str  # "they_depend_on_mine" | "i_depend_on_theirs"


@dataclass(frozen=True)
class Classification:
    severity: Severity
    detail: str
    semantic: tuple[SemanticConflict, ...] = ()


def semantic_conflicts(source: str, region: Region, others: list[Lease]) -> list[SemanticConflict]:
    """Dependency edges between the symbols in `region` and symbols in other leases.

    Only same-file analysis for now; cross-file import tracking is a follow-up.
    """
    if region.whole_file:
        return []
    mine = symbols_in_lines(source, region.start_line, region.end_line)
    my_names = {s.name for s in mine}
    my_refs = set().union(*(s.references for s in mine)) if mine else set()
    found: list[SemanticConflict] = []
    for lease in others:
        if lease.region.path != region.path or lease.region.whole_file:
            continue
        theirs = symbols_in_lines(source, lease.region.start_line, lease.region.end_line)
        for span in theirs:
            for name in sorted(span.references & my_names):
                found.append(SemanticConflict(name, lease.agent, "they_depend_on_mine"))
            if span.name in my_refs:
                found.append(SemanticConflict(span.name, lease.agent, "i_depend_on_theirs"))
    return found


def classify(region: Region, others: list[Lease], source: Optional[str] = None) -> Classification:
    overlapping = [l for l in others if l.region.overlaps(region)]
    if overlapping:
        who = "; ".join(f"{l.agent} ({l.intent}) at {l.region.describe()}" for l in overlapping)
        return Classification(Severity.OVERLAP, f"overlaps active lease: {who}")

    if source is not None:
        sem = semantic_conflicts(source, region, others)
        if sem:
            who = "; ".join(f"{c.agent} via `{c.symbol}` ({c.direction})" for c in sem)
            return Classification(Severity.SEMANTIC, f"symbol dependency with: {who}", tuple(sem))

    adjacent = [l for l in others if l.region.is_adjacent(region, gap=ADJACENT_GAP)]
    if adjacent:
        who = "; ".join(f"{l.agent} ({l.intent}) at {l.region.describe()}" for l in adjacent)
        return Classification(Severity.ADJACENT, f"adjacent to active lease: {who}")

    return Classification(Severity.NONE, "no interaction with other agents")
