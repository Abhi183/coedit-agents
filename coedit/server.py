"""MCP adapter. One instance runs inside each agent harness; all share the repo's .coedit/ state."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from mcp.server import MCPServer

from .names import agent_name
from .service import DEFAULT_TTL, Coordinator

INSTRUCTIONS = """\
You share this repository with other coding agents working at the same time.
Protocol (like Google Docs cursors, for code):
1. Call coedit_status first and whenever you start a new subtask. It shows who
   is working where, what they intend, their recent edits, and messages to you.
2. Before editing, call coedit_claim on the file plus a symbol or line range with
   a one-sentence intent. If refused (overlap), choose another region, wait, or
   coedit_send the holder a message. A 'semantic' warning means someone holds code
   that depends on yours: coordinate before changing signatures.
3. Use coedit_read to see a file with other agents' regions marked inline.
4. After each edit, call coedit_record so others see it immediately.
5. Call coedit_release when you finish a region. Leases expire on their own, so a
   crashed agent never blocks anyone for long.
"""


def build_server(repo_root: Optional[Path] = None, agent: Optional[str] = None) -> MCPServer:
    root = Path(repo_root or os.environ.get("COEDIT_ROOT") or os.getcwd())
    coord = Coordinator(root, agent or agent_name())
    mcp = MCPServer("coedit", instructions=INSTRUCTIONS)

    def dump(obj) -> str:
        return json.dumps(obj, indent=1)

    @mcp.tool()
    def coedit_whoami() -> str:
        """Your agent name and the repository root this coordinator serves."""
        return dump({"agent": coord.agent, "root": str(coord.root)})

    @mcp.tool()
    def coedit_status() -> str:
        """Who is working where right now: active leases with intents, other agents'
        edits since your last check, and new messages addressed to you."""
        return dump(coord.status())

    @mcp.tool()
    def coedit_claim(path: str, intent: str, symbol: Optional[str] = None,
                     start_line: Optional[int] = None, end_line: Optional[int] = None,
                     ttl_seconds: int = DEFAULT_TTL) -> str:
        """Claim a region before editing it. Give `symbol` (a Python function/class name,
        dotted for methods, e.g. 'Beta.method') or `start_line`/`end_line`; omit both to
        claim the whole file. `intent` is a one-sentence description of what you will do.
        Returns ok=false with the holder's name and intent if another agent has it."""
        return dump(coord.claim(path, intent, symbol, start_line, end_line, ttl_seconds))

    @mcp.tool()
    def coedit_renew(lease_id: str, ttl_seconds: int = DEFAULT_TTL) -> str:
        """Extend a lease you hold. Call during long tasks so it does not expire."""
        return dump(coord.renew(lease_id, ttl_seconds))

    @mcp.tool()
    def coedit_release(lease_id: Optional[str] = None) -> str:
        """Release one lease by id, or all of your leases when lease_id is omitted."""
        return dump(coord.release(lease_id))

    @mcp.tool()
    def coedit_read(path: str) -> str:
        """Read a file with line numbers and inline markers showing which lines other
        agents currently hold and what they recently changed there."""
        return coord.read(path)

    @mcp.tool()
    def coedit_record(path: str, summary: str, symbol: Optional[str] = None,
                      start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        """Announce an edit you just made so other agents see it immediately. Returns a
        warning if the edit touches or depends on a region someone else holds."""
        return dump(coord.record_edit(path, summary, symbol, start_line, end_line))

    @mcp.tool()
    def coedit_send(to: str, body: str) -> str:
        """Send a short message to another agent by name, or '*' for everyone."""
        return dump(coord.send(to, body))

    return mcp


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
