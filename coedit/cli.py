"""`coedit` command line: init a repo, serve the MCP adapter, watch live status."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .service import STATE_DIR, Coordinator
from .store import Store

MCP_CONFIG = {
    "mcpServers": {
        "coedit": {
            "command": "coedit",
            "args": ["serve"],
        }
    }
}


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    (root / STATE_DIR).mkdir(parents=True, exist_ok=True)
    Store(root / STATE_DIR / "state.db")
    config_path = root / ".mcp.json"
    if config_path.exists():
        existing = json.loads(config_path.read_text())
        merged = {**existing, "mcpServers": {**existing.get("mcpServers", {}),
                                            **MCP_CONFIG["mcpServers"]}}
    else:
        merged = MCP_CONFIG
    config_path.write_text(json.dumps(merged, indent=2) + "\n")
    print(f"initialised {root / STATE_DIR} and registered the coedit MCP server in {config_path}")
    print("start each agent in this directory with its own COEDIT_AGENT=<name> env var")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .server import main as serve_main
    serve_main()
    return 0


def _render(root: Path) -> str:
    store = Store(root / STATE_DIR / "state.db")
    now = time.time()
    lines = [f"coedit @ {root}   {time.strftime('%H:%M:%S')}", ""]
    leases = store.active_leases(now=now)
    lines.append("ACTIVE LEASES" if leases else "ACTIVE LEASES: none")
    for l in leases:
        remaining = int(l.expires_at - now)
        lines.append(f"  {l.agent:14} {l.region.describe():40} {l.intent}  ({remaining}s left)")
    edits = store.edits_since(now - 600)
    lines.append("")
    lines.append("EDITS (last 10 min)" if edits else "EDITS (last 10 min): none")
    for e in edits[-15:]:
        lines.append(f"  {time.strftime('%H:%M:%S', time.localtime(e.created_at))} "
                     f"{e.agent:14} {e.region.describe():40} {e.summary}")
    return "\n".join(lines)


def cmd_status(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if not (root / STATE_DIR).exists():
        print(f"no {STATE_DIR}/ here; run `coedit init` first", file=sys.stderr)
        return 1
    if not args.watch:
        print(_render(root))
        return 0
    try:
        while True:
            print("\033[2J\033[H" + _render(root), flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


def cmd_release(args: argparse.Namespace) -> int:
    coord = Coordinator(Path(args.root), args.agent)
    print(json.dumps(coord.release()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="coedit", description="coordination for concurrent coding agents")
    p.add_argument("--root", default=".", help="repository root (default: cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create .coedit/ and register the MCP server").set_defaults(fn=cmd_init)
    sub.add_parser("serve", help="run the MCP adapter over stdio").set_defaults(fn=cmd_serve)
    st = sub.add_parser("status", help="show who is working where")
    st.add_argument("-w", "--watch", action="store_true")
    st.add_argument("-i", "--interval", type=float, default=2.0)
    st.set_defaults(fn=cmd_status)
    rel = sub.add_parser("release", help="release all leases held by an agent")
    rel.add_argument("agent")
    rel.set_defaults(fn=cmd_release)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
