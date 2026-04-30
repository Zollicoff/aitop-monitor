"""Collector for Claude Code sessions and usage data."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import psutil


CLAUDE_DIR = Path.home() / ".claude"
SESSIONS_DIR = CLAUDE_DIR / "sessions"
PROJECTS_DIR = CLAUDE_DIR / "projects"

TIMEFRAMES = ["today", "7d", "30d", "all"]
TIMEFRAME_LABELS = {
    "today": "Today",
    "7d": "Last 7 Days",
    "30d": "Last 30 Days",
    "all": "All Time",
}

# Anthropic API pricing (USD per million tokens)
# Source: https://platform.claude.com/docs/en/about-claude/pricing
# Cache write uses 5-minute rate (1.25x input), matching Claude_Code_CLI_Usage
# Cache read = 0.1x input
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-7":          {"input": 5.0,  "output": 25.0, "cache_write": 6.25,  "cache_read": 0.50},
    "claude-opus-4-6":          {"input": 5.0,  "output": 25.0, "cache_write": 6.25,  "cache_read": 0.50},
    "claude-opus-4-5-20251101": {"input": 5.0,  "output": 25.0, "cache_write": 6.25,  "cache_read": 0.50},
    "claude-opus-4-1-20250805": {"input": 15.0, "output": 75.0, "cache_write": 18.75, "cache_read": 1.50},
    "claude-opus-4-20250514":   {"input": 15.0, "output": 75.0, "cache_write": 18.75, "cache_read": 1.50},
    "claude-sonnet-4-6":        {"input": 3.0,  "output": 15.0, "cache_write": 3.75,  "cache_read": 0.30},
    "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.30},
    "claude-sonnet-4-20250514": {"input": 3.0,  "output": 15.0, "cache_write": 3.75,  "cache_read": 0.30},
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0,  "cache_write": 1.25,  "cache_read": 0.10},
    "claude-haiku-3-5-20241022": {"input": 0.80, "output": 4.0, "cache_write": 1.0,   "cache_read": 0.08},
}

DEFAULT_PRICING = MODEL_PRICING["claude-sonnet-4-6"]


def _match_pricing(model: str) -> dict[str, float]:
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    lower = model.lower()
    for key, pricing in MODEL_PRICING.items():
        if key in lower or lower in key:
            return pricing
    for pattern, pricing in [
        ("opus-4-7", MODEL_PRICING["claude-opus-4-7"]),
        ("opus-4-6", MODEL_PRICING["claude-opus-4-6"]),
        ("opus-4-5", MODEL_PRICING["claude-opus-4-5-20251101"]),
        ("opus-4-1", MODEL_PRICING["claude-opus-4-1-20250805"]),
        ("opus-4",   MODEL_PRICING["claude-opus-4-20250514"]),
        ("sonnet-4-6", MODEL_PRICING["claude-sonnet-4-6"]),
        ("sonnet-4-5", MODEL_PRICING["claude-sonnet-4-5-20250929"]),
        ("sonnet-4",   MODEL_PRICING["claude-sonnet-4-20250514"]),
        ("haiku-4-5",  MODEL_PRICING["claude-haiku-4-5-20251001"]),
        ("haiku-3-5",  MODEL_PRICING["claude-haiku-3-5-20241022"]),
    ]:
        if pattern in lower:
            return pricing
    return DEFAULT_PRICING


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_create_tokens: int = 0

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_create_tokens
        )

    def total_str(self) -> str:
        t = self.total
        if t >= 1_000_000:
            return f"{t / 1_000_000:.1f}M"
        if t >= 1_000:
            return f"{t / 1_000:.1f}K"
        return str(t)

    def add(self, other: TokenUsage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_create_tokens += other.cache_create_tokens


@dataclass
class SessionCost:
    input_cost: float = 0.0
    output_cost: float = 0.0
    cache_read_cost: float = 0.0
    cache_create_cost: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.input_cost
            + self.output_cost
            + self.cache_read_cost
            + self.cache_create_cost
        )

    def total_str(self) -> str:
        t = self.total
        if t < 0.01:
            return f"${t:.4f}"
        return f"${t:.2f}"

    def add(self, other: SessionCost) -> None:
        self.input_cost += other.input_cost
        self.output_cost += other.output_cost
        self.cache_read_cost += other.cache_read_cost
        self.cache_create_cost += other.cache_create_cost


@dataclass
class UsageEntry:
    timestamp: str  # ISO format
    tokens: TokenUsage
    cost: SessionCost
    cwd: str = ""
    model: str = ""


@dataclass
class ClaudeSession:
    pid: int
    session_id: str
    cwd: str
    status: str
    started_at: int  # ms epoch
    version: str
    kind: str
    model: str = ""
    agent_name: str = ""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    entries: list[UsageEntry] = field(default_factory=list)

    @property
    def uptime_str(self) -> str:
        elapsed = time.time() - (self.started_at / 1000)
        if elapsed < 60:
            return f"{int(elapsed)}s"
        if elapsed < 3600:
            return f"{int(elapsed // 60)}m"
        hours = int(elapsed // 3600)
        mins = int((elapsed % 3600) // 60)
        return f"{hours}h {mins}m"

    @property
    def status_display(self) -> str:
        if self.status == "busy":
            return "[bold green]● active[/]"
        if self.status == "idle":
            return "[dim]○ idle[/]"
        return f"[yellow]? {self.status}[/]"



@dataclass
class ClaudeData:
    sessions: list[ClaudeSession] = field(default_factory=list)
    total_sessions: int = 0
    active_sessions: int = 0


def _derive_agent_name(cwd: str) -> str:
    path = Path(cwd)
    name = path.name
    if name.startswith("prime-"):
        return name.removeprefix("prime-").capitalize()
    return name


def _find_session_jsonl(session_id: str, cwd: str) -> Path | None:
    project_key = cwd.replace("/", "-")
    candidate = PROJECTS_DIR / project_key / f"{session_id}.jsonl"
    if candidate.exists():
        return candidate
    return None


def _compute_cost(model: str, usage: dict) -> tuple[TokenUsage, SessionCost]:
    pricing = _match_pricing(model)
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    c_read = usage.get("cache_read_input_tokens", 0)
    c_create = usage.get("cache_creation_input_tokens", 0)

    tokens = TokenUsage(
        input_tokens=inp,
        output_tokens=out,
        cache_read_tokens=c_read,
        cache_create_tokens=c_create,
    )
    cost = SessionCost(
        input_cost=inp * pricing["input"] / 1_000_000,
        output_cost=out * pricing["output"] / 1_000_000,
        cache_read_cost=c_read * pricing["cache_read"] / 1_000_000,
        cache_create_cost=c_create * pricing["cache_write"] / 1_000_000,
    )
    return tokens, cost


def _parse_session_usage(jsonl_path: Path) -> tuple[str, list[UsageEntry]]:
    entries: list[UsageEntry] = []
    last_model = ""
    seen: set[str] = set()

    with open(jsonl_path) as f:
        for line in f:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg = data.get("message")
            if not isinstance(msg, dict):
                continue

            usage = msg.get("usage")
            if not usage:
                continue

            msg_id = msg.get("id", "")
            req_id = data.get("requestId", "")
            if msg_id and req_id:
                dedup_key = f"{msg_id}:{req_id}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

            inp = usage.get("input_tokens", 0)
            out = usage.get("output_tokens", 0)
            c_create = usage.get("cache_creation_input_tokens", 0)
            c_read = usage.get("cache_read_input_tokens", 0)
            if not (inp or out or c_create or c_read):
                continue

            model = msg.get("model", "")
            if model == "<synthetic>" or not model:
                model = last_model or "unknown"
            else:
                last_model = model

            tokens, cost = _compute_cost(model, usage)

            timestamp = data.get("timestamp", "")
            entry_cwd = data.get("cwd", "")
            entries.append(UsageEntry(
                timestamp=timestamp, tokens=tokens, cost=cost,
                cwd=entry_cwd, model=model,
            ))

    return last_model, entries


class ClaudeCollector:
    def collect(self) -> ClaudeData:
        data = ClaudeData()
        data.sessions = self._collect_sessions()
        data.total_sessions = len(data.sessions)
        data.active_sessions = sum(1 for s in data.sessions if s.status == "busy")
        return data

    def _collect_sessions(self) -> list[ClaudeSession]:
        sessions: list[ClaudeSession] = []
        if not SESSIONS_DIR.exists():
            return sessions

        for f in SESSIONS_DIR.glob("*.json"):
            try:
                raw = json.loads(f.read_text())
                pid = raw.get("pid", 0)

                cpu = 0.0
                mem_mb = 0.0
                try:
                    proc = psutil.Process(pid)
                    cpu = proc.cpu_percent(interval=0)
                    mem_mb = proc.memory_info().rss / (1024 * 1024)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

                cwd = raw.get("cwd", "")
                session_id = raw.get("sessionId", "")

                model = ""
                entries: list[UsageEntry] = []

                jsonl_path = _find_session_jsonl(session_id, cwd)
                if jsonl_path:
                    model, entries = _parse_session_usage(jsonl_path)
                    subagent_dir = jsonl_path.parent / session_id / "subagents"
                    if subagent_dir.is_dir():
                        for sub_jsonl in subagent_dir.glob("*.jsonl"):
                            _, sub_entries = _parse_session_usage(sub_jsonl)
                            entries.extend(sub_entries)

                session = ClaudeSession(
                    pid=pid,
                    session_id=session_id,
                    cwd=cwd,
                    status=raw.get("status", "unknown"),
                    started_at=raw.get("startedAt", 0),
                    version=raw.get("version", "?"),
                    kind=raw.get("kind", "?"),
                    model=model,
                    agent_name=_derive_agent_name(cwd),
                    cpu_percent=cpu,
                    memory_mb=mem_mb,
                    entries=entries,
                )
                sessions.append(session)
            except (json.JSONDecodeError, KeyError):
                continue

        sessions.sort(key=lambda s: (s.status != "busy", s.started_at))
        return sessions

