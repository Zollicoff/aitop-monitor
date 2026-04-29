"""Persistent usage store backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .collectors.claude import (
    TokenUsage,
    SessionCost,
    UsageEntry,
    _match_pricing,
    CLAUDE_DIR,
)

DB_DIR = Path.home() / ".local" / "share" / "aitop"
DB_PATH = DB_DIR / "usage.db"
DASHBOARD_CACHE = CLAUDE_DIR / "usage-cache" / "dashboard-cache.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    session_id TEXT NOT NULL,
    agent_name TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    project_path TEXT NOT NULL DEFAULT '',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    cost REAL NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'jsonl',
    dedup_key TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage(timestamp);
CREATE INDEX IF NOT EXISTS idx_usage_agent ON usage(agent_name);
CREATE INDEX IF NOT EXISTS idx_usage_session ON usage(session_id);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class UsageStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.executescript(SCHEMA)
        self._conn.execute("PRAGMA journal_mode=WAL")

    def close(self) -> None:
        self._conn.close()

    def _get_meta(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def _set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (key, value),
        )
        self._conn.commit()

    def import_dashboard_cache(self, force: bool = False) -> int:
        if not DASHBOARD_CACHE.exists():
            return 0

        stat = DASHBOARD_CACHE.stat()
        cache_mtime = str(stat.st_mtime)
        if not force and self._get_meta("dashboard_cache_mtime") == cache_mtime:
            return 0

        data = json.loads(DASHBOARD_CACHE.read_text())
        entries = data.get("entries", [])
        if not entries:
            return 0

        inserted = 0
        for e in entries:
            ts = e.get("timestamp", "")
            sid = e.get("sessionId", "")
            dedup = f"dc:{sid}:{ts}"

            try:
                self._conn.execute(
                    """INSERT OR IGNORE INTO usage
                    (timestamp, session_id, agent_name, model, project_path,
                     input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                     cost, source, dedup_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'dashboard', ?)""",
                    (
                        ts,
                        sid,
                        e.get("agentName", ""),
                        e.get("model", ""),
                        e.get("projectPath", ""),
                        e.get("inputTokens", 0),
                        e.get("outputTokens", 0),
                        e.get("cacheReadTokens", 0),
                        e.get("cacheWriteTokens", 0),
                        e.get("cost", 0),
                        dedup,
                    ),
                )
                inserted += self._conn.execute("SELECT changes()").fetchone()[0]
            except sqlite3.IntegrityError:
                pass

        self._conn.commit()
        self._set_meta("dashboard_cache_mtime", cache_mtime)
        return inserted

    def ingest_session_entries(
        self,
        session_id: str,
        agent_name: str,
        entries: list[UsageEntry],
    ) -> int:
        inserted = 0
        for e in entries:
            dedup = f"jl:{session_id}:{e.timestamp}"

            try:
                self._conn.execute(
                    """INSERT OR IGNORE INTO usage
                    (timestamp, session_id, agent_name, model, project_path,
                     input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                     cost, source, dedup_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'jsonl', ?)""",
                    (
                        e.timestamp,
                        session_id,
                        agent_name,
                        e.model,
                        e.cwd,
                        e.tokens.input_tokens,
                        e.tokens.output_tokens,
                        e.tokens.cache_read_tokens,
                        e.tokens.cache_create_tokens,
                        e.cost.total,
                        dedup,
                    ),
                )
                inserted += self._conn.execute("SELECT changes()").fetchone()[0]
            except sqlite3.IntegrityError:
                pass

        self._conn.commit()
        return inserted

    def query_totals(
        self,
        agent_name: str | None = None,
        since: str | None = None,
    ) -> tuple[TokenUsage, SessionCost, float]:
        """Returns (tokens, cost_from_tokens, pre_calculated_cost)."""
        where = []
        params: list = []
        if agent_name:
            where.append("agent_name = ?")
            params.append(agent_name)
        if since:
            where.append("timestamp >= ?")
            params.append(since)

        clause = f"WHERE {' AND '.join(where)}" if where else ""
        row = self._conn.execute(
            f"""SELECT
                COALESCE(SUM(input_tokens), 0),
                COALESCE(SUM(output_tokens), 0),
                COALESCE(SUM(cache_read_tokens), 0),
                COALESCE(SUM(cache_write_tokens), 0),
                COALESCE(SUM(cost), 0)
            FROM usage {clause}""",
            params,
        ).fetchone()

        tokens = TokenUsage(
            input_tokens=row[0],
            output_tokens=row[1],
            cache_read_tokens=row[2],
            cache_create_tokens=row[3],
        )
        return tokens, row[4]

    def query_by_project(
        self,
        agent_name: str | None = None,
        since: str | None = None,
    ) -> list[tuple[str, TokenUsage, float]]:
        where = []
        params: list = []
        if agent_name:
            where.append("agent_name = ?")
            params.append(agent_name)
        if since:
            where.append("timestamp >= ?")
            params.append(since)

        clause = f"WHERE {' AND '.join(where)}" if where else ""
        rows = self._conn.execute(
            f"""SELECT project_path,
                COALESCE(SUM(input_tokens), 0),
                COALESCE(SUM(output_tokens), 0),
                COALESCE(SUM(cache_read_tokens), 0),
                COALESCE(SUM(cache_write_tokens), 0),
                COALESCE(SUM(cost), 0)
            FROM usage {clause}
            GROUP BY project_path
            ORDER BY SUM(cost) DESC""",
            params,
        ).fetchall()

        results = []
        for r in rows:
            tokens = TokenUsage(r[1], r[2], r[3], r[4])
            results.append((r[0], tokens, r[5]))
        return results

    def query_by_agent(
        self, since: str | None = None
    ) -> list[tuple[str, TokenUsage, float]]:
        where = []
        params: list = []
        if since:
            where.append("timestamp >= ?")
            params.append(since)

        clause = f"WHERE {' AND '.join(where)}" if where else ""
        rows = self._conn.execute(
            f"""SELECT agent_name,
                COALESCE(SUM(input_tokens), 0),
                COALESCE(SUM(output_tokens), 0),
                COALESCE(SUM(cache_read_tokens), 0),
                COALESCE(SUM(cache_write_tokens), 0),
                COALESCE(SUM(cost), 0)
            FROM usage {clause}
            GROUP BY agent_name
            ORDER BY SUM(cost) DESC""",
            params,
        ).fetchall()

        results = []
        for r in rows:
            tokens = TokenUsage(r[1], r[2], r[3], r[4])
            results.append((r[0], tokens, r[5]))
        return results

    @property
    def entry_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM usage").fetchone()[0]
