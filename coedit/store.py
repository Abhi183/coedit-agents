"""SQLite-backed shared state. Every agent's MCP adapter opens the same file.

SQLite's file locking gives us the multi-process safety we need for two to a
handful of agents on one machine. A networked backend can replace this module
without touching the rest of the system.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

from .models import Edit, Lease, Message, Region

_SCHEMA = """
CREATE TABLE IF NOT EXISTS leases (
    id TEXT PRIMARY KEY, agent TEXT NOT NULL, region TEXT NOT NULL,
    intent TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL,
    released INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS edits (
    id TEXT PRIMARY KEY, agent TEXT NOT NULL, region TEXT NOT NULL,
    summary TEXT NOT NULL, created_at REAL NOT NULL, symbols_changed TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY, sender TEXT NOT NULL, recipient TEXT NOT NULL,
    body TEXT NOT NULL, created_at REAL NOT NULL);
"""


class LeaseConflict(Exception):
    """Raised when a claim overlaps an active lease held by a different agent."""

    def __init__(self, holders: list[Lease]):
        self.holders = holders
        held = "; ".join(f"{l.agent}: {l.region.describe()} ({l.intent})" for l in holders)
        super().__init__(f"region already leased by {held}")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    # ---- leases ---------------------------------------------------------

    def active_leases(self, now: Optional[float] = None, path: Optional[str] = None) -> list[Lease]:
        now = time.time() if now is None else now
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, agent, region, intent, created_at, expires_at FROM leases "
                "WHERE released = 0 AND expires_at > ? ORDER BY created_at", (now,)).fetchall()
        leases = [self._lease_from_row(r) for r in rows]
        return [l for l in leases if path is None or l.region.path == path]

    def blocking_leases(self, agent: str, region: Region, now: Optional[float] = None) -> list[Lease]:
        return [l for l in self.active_leases(now=now, path=region.path)
                if l.agent != agent and l.region.overlaps(region)]

    def claim(self, agent: str, region: Region, intent: str, ttl: float,
              now: Optional[float] = None) -> Lease:
        now = time.time() if now is None else now
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            holders = self.blocking_leases(agent, region, now=now)
            if holders:
                conn.execute("ROLLBACK")
                raise LeaseConflict(holders)
            lease = Lease(id=_new_id(), agent=agent, region=region, intent=intent,
                          created_at=now, expires_at=now + ttl)
            conn.execute(
                "INSERT INTO leases (id, agent, region, intent, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (lease.id, agent, json.dumps(region.to_dict()), intent, now, lease.expires_at))
            conn.execute("COMMIT")
        return lease

    def heartbeat(self, lease_id: str, ttl: float, now: Optional[float] = None,
                  agent: Optional[str] = None) -> bool:
        """Extend a live lease. Returns False if it is unknown, expired, released,
        or (when `agent` is given) held by someone else. An expired lease can not be
        revived, because another agent may have claimed the region in the meantime."""
        now = time.time() if now is None else now
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE leases SET expires_at = ? WHERE id = ? AND released = 0 "
                "AND expires_at > ? AND (? IS NULL OR agent = ?)",
                (now + ttl, lease_id, now, agent, agent))
            return cur.rowcount == 1

    def release(self, lease_id: str, agent: Optional[str] = None) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE leases SET released = 1 WHERE id = ? AND released = 0 "
                "AND (? IS NULL OR agent = ?)", (lease_id, agent, agent))
            return cur.rowcount == 1

    def release_all(self, agent: str) -> int:
        with self._connect() as conn:
            cur = conn.execute("UPDATE leases SET released = 1 WHERE agent = ? AND released = 0",
                               (agent,))
            return cur.rowcount

    # ---- edits ----------------------------------------------------------

    def record_edit(self, agent: str, region: Region, summary: str,
                    symbols_changed: tuple[str, ...] = (), now: Optional[float] = None) -> Edit:
        now = time.time() if now is None else now
        edit = Edit(id=_new_id(), agent=agent, region=region, summary=summary,
                    created_at=now, symbols_changed=symbols_changed)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO edits (id, agent, region, summary, created_at, symbols_changed) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (edit.id, agent, json.dumps(region.to_dict()), summary, now,
                 json.dumps(list(symbols_changed))))
        return edit

    def edits_since(self, since: float, exclude_agent: Optional[str] = None) -> list[Edit]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, agent, region, summary, created_at, symbols_changed FROM edits "
                "WHERE created_at > ? ORDER BY created_at", (since,)).fetchall()
        edits = [Edit(id=r[0], agent=r[1], region=Region.from_dict(json.loads(r[2])),
                      summary=r[3], created_at=r[4], symbols_changed=tuple(json.loads(r[5])))
                 for r in rows]
        return [e for e in edits if e.agent != exclude_agent]

    # ---- messages -------------------------------------------------------

    def send_message(self, sender: str, recipient: str, body: str,
                     now: Optional[float] = None) -> Message:
        now = time.time() if now is None else now
        msg = Message(id=_new_id(), sender=sender, recipient=recipient, body=body, created_at=now)
        with self._connect() as conn:
            conn.execute("INSERT INTO messages (id, sender, recipient, body, created_at) "
                         "VALUES (?, ?, ?, ?, ?)", (msg.id, sender, recipient, body, now))
        return msg

    def inbox(self, agent: str, since: float) -> list[Message]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, sender, recipient, body, created_at FROM messages "
                "WHERE created_at > ? AND (recipient = ? OR recipient = '*') AND sender != ? "
                "ORDER BY created_at", (since, agent, agent)).fetchall()
        return [Message(*r) for r in rows]

    # ---- helpers --------------------------------------------------------

    @staticmethod
    def _lease_from_row(row: tuple) -> Lease:
        return Lease(id=row[0], agent=row[1], region=Region.from_dict(json.loads(row[2])),
                     intent=row[3], created_at=row[4], expires_at=row[5])
