"""Render a file with other agents' presence inline, the way Docs shows cursors."""

from __future__ import annotations

from .models import Edit, Lease

RECENT_EDIT_WINDOW = 10  # how many edits to surface in the gutter


def _gutter_for_line(line_no: int, leases: list[Lease], edits: list[Edit]) -> str:
    tags = []
    for lease in leases:
        r = lease.region
        if not r.whole_file and r.start_line <= line_no <= r.end_line:
            tags.append(f"<{lease.agent}: {lease.intent}>")
    for edit in edits[-RECENT_EDIT_WINDOW:]:
        r = edit.region
        if not r.whole_file and r.start_line <= line_no <= r.end_line:
            tags.append(f"<{edit.agent} edited: {edit.summary}>")
    return " ".join(tags)


def annotate_source(source: str, leases: list[Lease], edits: list[Edit]) -> str:
    header = [f"# [coedit] whole file leased by {l.agent}: {l.intent}"
              for l in leases if l.region.whole_file]
    body = []
    for i, text in enumerate(source.splitlines(), start=1):
        gutter = _gutter_for_line(i, leases, edits)
        suffix = f"    # {gutter}" if gutter else ""
        body.append(f"{i:4d} | {text}{suffix}")
    return "\n".join(header + body)
