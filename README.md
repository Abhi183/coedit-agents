# coedit-agents

Google Docs style coordination for two or more coding agents editing the same
repository at the same time. Docs lets people work in one document without
stepping on each other because everyone sees live cursors, the merge is
fine-grained, and there are no branches. This tool gives coding agents the same
three things, adapted to code:

- **Intent regions instead of cursors.** An agent claims a file, a symbol or a
  line range and says in one sentence what it is about to do. Every other agent
  sees that claim inline when it reads the file.
- **Advisory leases with expiry.** Claims block overlapping claims by other
  agents, but they time out, so a crashed agent never wedges the others.
- **Conflict classification.** Overlap is caught before an edit happens. So is
  the case Docs cannot see: two regions that do not share a line but share a
  symbol, where a line-level merge would succeed and then break at runtime.

State lives in a SQLite file under `.coedit/` in the repository, so any number
of agent processes on one machine share it with no daemon.

## Install

```
uv venv .venv && uv pip install -p .venv/bin/python -e ".[dev]"
```

Python 3.11 or newer. On an Apple Silicon Mac make sure the interpreter is
arm64, since the x86_64 build pulls a source build of cryptography.

## Use with Claude Code

In the repository the agents will share:

```
coedit init
```

This creates `.coedit/` and registers the MCP server in `.mcp.json`. Then start
each agent in that directory with its own name:

```
COEDIT_AGENT=alice claude
COEDIT_AGENT=bob   claude
```

Watch live from a third terminal:

```
coedit status --watch
```

The MCP server ships its own instructions, so an agent that connects is told the
protocol: check status, claim before editing, read annotated, record after
editing, release when done.

## Tools exposed to the agent

| Tool | What it does |
|---|---|
| `coedit_status` | Active leases with intents, other agents' edits since last check, new messages |
| `coedit_claim` | Claim a file, symbol or line range with an intent. Refused on overlap, warned on semantic dependency |
| `coedit_read` | File with line numbers and inline markers for other agents' regions and recent edits |
| `coedit_record` | Announce an edit so others see it immediately |
| `coedit_renew` / `coedit_release` | Extend or drop leases |
| `coedit_send` | Short message to another agent or to everyone |
| `coedit_whoami` | Your name and the repository root |

## Layout

```
coedit/models.py     frozen dataclasses: Region, Lease, Edit, Message
coedit/regions.py    Python symbol spans and references via ast
coedit/store.py      SQLite store, lease claim is an atomic transaction
coedit/conflicts.py  none / adjacent / overlap / semantic classification
coedit/annotate.py   inline presence rendering
coedit/service.py    Coordinator: the operations, transport-free
coedit/server.py     MCP adapter (mcp 2.x MCPServer)
coedit/cli.py        init, serve, status, release
```

## Tests

```
.venv/bin/python -m pytest --cov=coedit
```

## Limits in this version

- Symbol resolution and semantic conflicts are Python-only and same-file only.
  Tree-sitter and import tracking are the next step.
- The shared state is one machine. A networked backend replaces `store.py`.
- Files on disk are the shared text. There is no CRDT yet, so two agents
  writing the same lines at the same instant still race at the filesystem;
  the leases exist to make that not happen.
