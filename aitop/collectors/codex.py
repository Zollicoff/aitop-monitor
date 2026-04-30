"""Collector for OpenAI Codex CLI sessions and usage data."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import psutil

from .claude import TokenUsage, SessionCost, UsageEntry

CODEX_DIR = Path.home() / ".codex"
SESSIONS_DIR = CODEX_DIR / "sessions"

# OpenAI pricing (USD per million tokens)
CODEX_PRICING = {
    "gpt-5.5":   {"input": 2.00, "output": 8.00, "cached": 0.50},
    "gpt-5":     {"input": 2.00, "output": 8.00, "cached": 0.50},
    "gpt-4.1":   {"input": 2.00, "output": 8.00, "cached": 0.50},
    "gpt-4o":    {"input": 2.50, "output": 10.0, "cached": 1.25},
    "o3":        {"input": 2.00, "output": 8.00, "cached": 0.50},
    "o4-mini":   {"input": 1.10, "output": 4.40, "cached": 0.275},
}

DEFAULT_CODEX_PRICING = CODEX_PRICING["gpt-4o"]


def _match_codex_pricing(model: str) -> dict[str, float]:
    lower = model.lower()
    for key, pricing in CODEX_PRICING.items():
        if key in lower:
            return pricing
    return DEFAULT_CODEX_PRICING


@dataclass
class CodexSession:
    pid: int
    cwd: str
    status: str
    started_at: float
    model: str = ""
    memory_mb: float = 0.0
    entries: list[UsageEntry] = field(default_factory=list)

    @property
    def uptime_str(self) -> str:
        elapsed = time.time() - self.started_at
        if elapsed < 60:
            return f"{int(elapsed)}s"
        if elapsed < 3600:
            return f"{int(elapsed // 60)}m"
        hours = int(elapsed // 3600)
        mins = int((elapsed % 3600) // 60)
        return f"{hours}h {mins}m"


def _parse_codex_session(jsonl_path: Path) -> tuple[str, str, list[UsageEntry]]:
    entries: list[UsageEntry] = []
    model = "openai"
    cwd = ""

    with open(jsonl_path) as f:
        for line in f:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            payload = data.get("payload")
            if not isinstance(payload, dict):
                continue

            if data.get("type") == "session_meta":
                model = payload.get("model", "openai")
                cwd = payload.get("cwd", "")

            if payload.get("type") == "token_count":
                info = payload.get("info") or {}
                last = info.get("last_token_usage") or {}
                inp = last.get("input_tokens", 0)
                out = last.get("output_tokens", 0)
                cached = last.get("cached_input_tokens", 0)
                if not (inp or out):
                    continue

                pricing = _match_codex_pricing(model)
                net_input = max(inp - cached, 0)
                tokens = TokenUsage(
                    input_tokens=net_input,
                    output_tokens=out,
                    cache_read_tokens=cached,
                    cache_create_tokens=0,
                )
                cost = SessionCost(
                    input_cost=net_input * pricing["input"] / 1_000_000,
                    output_cost=out * pricing["output"] / 1_000_000,
                    cache_read_cost=cached * pricing["cached"] / 1_000_000,
                    cache_create_cost=0,
                )
                timestamp = data.get("timestamp", "")
                entries.append(UsageEntry(
                    timestamp=timestamp, tokens=tokens, cost=cost,
                    cwd=cwd, model=model,
                ))

    return model, cwd, entries


class CodexCollector:
    def collect_history(self) -> list[UsageEntry]:
        all_entries: list[UsageEntry] = []
        if not SESSIONS_DIR.exists():
            return all_entries

        for jsonl in SESSIONS_DIR.rglob("*.jsonl"):
            _, _, entries = _parse_codex_session(jsonl)
            all_entries.extend(entries)

        return all_entries

    def detect_running(self) -> list[CodexSession]:
        sessions: list[CodexSession] = []
        for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
            try:
                name = proc.info["name"] or ""
                cmdline = proc.info["cmdline"] or []
                if "codex" not in name.lower() and not any("codex" in c.lower() for c in cmdline):
                    continue
                if "grep" in name.lower():
                    continue

                mem_mb = proc.memory_info().rss / (1024 * 1024)
                sessions.append(CodexSession(
                    pid=proc.info["pid"],
                    cwd="",
                    status="active",
                    started_at=proc.info["create_time"],
                    model="gpt-5.5",
                    memory_mb=mem_mb,
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return sessions
