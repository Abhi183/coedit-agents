"""Coordinator: the agent-facing operations, independent of the MCP transport."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from .annotate import annotate_source
from .conflicts import Severity, classify
from .models import Region
from .regions import resolve_symbol
from .store import LeaseConflict, Store

DEFAULT_TTL = 15 * 60  # seconds; agents heartbeat by re-claiming or calling renew
STATE_DIR = ".coedit"


class Coordinator:
    def __init__(self, repo_root: Path | str, agent: str, store: Optional[Store] = None):
        self.root = Path(repo_root).resolve()
        self.agent = agent
        self.store = store or Store(self.root / STATE_DIR / "state.db")
        self._last_inbox_check = 0.0
        self._last_edit_check = time.time()

    # ---- region helpers -------------------------------------------------

    def _read_file(self, path: str) -> Optional[str]:
        target = (self.root / path)
        if not target.is_file():
            return None
        try:
            return target.read_text()
        except (OSError, UnicodeDecodeError):
            return None

    def _resolve_region(self, path: str, symbol: Optional[str], start_line: Optional[int],
                        end_line: Optional[int]) -> Region | dict[str, Any]:
        if symbol:
            source = self._read_file(path)
            if source is None:
                return {"ok": False, "error": f"file not found or unreadable: {path}"}
            span = resolve_symbol(source, symbol)
            if span is None:
                return {"ok": False, "error": f"symbol `{symbol}` not found in {path}"}
            return Region(path, span.start_line, span.end_line, symbol)
        if start_line and end_line:
            if start_line > end_line or start_line < 1:
                return {"ok": False, "error": "start_line must be >= 1 and <= end_line"}
            return Region(path, start_line, end_line)
        return Region(path)

    # ---- operations -----------------------------------------------------

    def claim(self, path: str, intent: str, symbol: Optional[str] = None,
              start_line: Optional[int] = None, end_line: Optional[int] = None,
              ttl: float = DEFAULT_TTL) -> dict[str, Any]:
        if not intent.strip():
            return {"ok": False, "error": "intent is required: say what you are about to do"}
        region = self._resolve_region(path, symbol, start_line, end_line)
        if isinstance(region, dict):
            return region
        others = [l for l in self.store.active_leases(path=path) if l.agent != self.agent]
        verdict = classify(region, others, source=self._read_file(path))
        try:
            lease = self.store.claim(self.agent, region, intent, ttl)
        except LeaseConflict as exc:
            return {"ok": False, "severity": Severity.OVERLAP.value, "error": str(exc),
                    "holders": [l.to_dict() for l in exc.holders],
                    "advice": "wait, pick a different region, or message the holder"}
        result: dict[str, Any] = {"ok": True, "lease": lease.to_dict(),
                                  "severity": verdict.severity.value}
        if verdict.severity is not Severity.NONE:
            result["warning"] = verdict.detail
        return result

    def renew(self, lease_id: str, ttl: float = DEFAULT_TTL) -> dict[str, Any]:
        self.store.heartbeat(lease_id, ttl)
        return {"ok": True, "lease_id": lease_id, "ttl": ttl}

    def release(self, lease_id: Optional[str] = None) -> dict[str, Any]:
        if lease_id:
            self.store.release(lease_id)
            return {"ok": True, "released": 1}
        return {"ok": True, "released": self.store.release_all(self.agent)}

    def read(self, path: str) -> str:
        source = self._read_file(path)
        if source is None:
            return f"[coedit] file not found or unreadable: {path}"
        leases = self.store.active_leases(path=path)
        edits = [e for e in self.store.edits_since(0.0) if e.region.path == path]
        return annotate_source(source, leases, edits)

    def record_edit(self, path: str, summary: str, symbol: Optional[str] = None,
                    start_line: Optional[int] = None, end_line: Optional[int] = None) -> dict[str, Any]:
        region = self._resolve_region(path, symbol, start_line, end_line)
        if isinstance(region, dict):
            return region
        others = [l for l in self.store.active_leases(path=path) if l.agent != self.agent]
        verdict = classify(region, others, source=self._read_file(path))
        symbols = (symbol,) if symbol else ()
        edit = self.store.record_edit(self.agent, region, summary, symbols)
        result: dict[str, Any] = {"ok": True, "edit": edit.to_dict(),
                                  "severity": verdict.severity.value}
        if verdict.severity is not Severity.NONE:
            result["warning"] = verdict.detail
        return result

    def send(self, to: str, body: str) -> dict[str, Any]:
        msg = self.store.send_message(self.agent, to, body)
        return {"ok": True, "message": msg.to_dict()}

    def status(self) -> dict[str, Any]:
        now = time.time()
        leases = self.store.active_leases(now=now)
        edits = self.store.edits_since(self._last_edit_check, exclude_agent=self.agent)
        inbox = self.store.inbox(self.agent, since=self._last_inbox_check)
        self._last_edit_check = now
        self._last_inbox_check = now
        return {
            "agent": self.agent,
            "leases": [l.to_dict() for l in leases],
            "recent_edits": [e.to_dict() for e in edits],
            "inbox": [m.to_dict() for m in inbox],
        }
