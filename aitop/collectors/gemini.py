"""Collector for Google Gemini CLI sessions and usage data."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import psutil

from .claude import TokenUsage, SessionCost, UsageEntry

GEMINI_DIR = Path.home() / ".gemini"

# Google Gemini pricing (USD per million tokens)
GEMINI_PRICING = {
    "gemini-2.5-pro":          {"input": 1.25, "output": 10.0, "cached": 0.125},
    "gemini-2.5-flash":        {"input": 0.30, "output": 2.50, "cached": 0.03},
    "gemini-2.0-flash":        {"input": 0.10, "output": 0.40, "cached": 0.025},
    "gemini-3-flash-preview":  {"input": 0.30, "output": 2.50, "cached": 0.03},
}

DEFAULT_GEMINI_PRICING = GEMINI_PRICING["gemini-2.5-flash"]


def _match_gemini_pricing(model: str) -> dict[str, float]:
    lower = model.lower()
    for key, pricing in GEMINI_PRICING.items():
        if key in lower:
            return pricing
    if "pro" in lower:
        return GEMINI_PRICING["gemini-2.5-pro"]
    if "flash" in lower:
        return GEMINI_PRICING["gemini-2.5-flash"]
    return DEFAULT_GEMINI_PRICING


@dataclass
class GeminiSession:
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


def _parse_gemini_session(session_path: Path) -> tuple[str, list[UsageEntry]]:
    entries: list[UsageEntry] = []
    model = ""

    try:
        data = json.loads(session_path.read_text())
    except (json.JSONDecodeError, OSError):
        return model, entries

    cwd = ""
    project_root = session_path.parent / ".project_root"
    if project_root.exists():
        cwd = project_root.read_text().strip()

    for msg in data.get("messages", []):
        tokens_data = msg.get("tokens")
        if not tokens_data:
            continue

        msg_model = msg.get("model", "")
        if msg_model:
            model = msg_model

        inp = tokens_data.get("input", 0)
        out = tokens_data.get("output", 0)
        cached = tokens_data.get("cached", 0)
        thoughts = tokens_data.get("thoughts", 0)
        out_total = out + thoughts

        if not (inp or out_total):
            continue

        pricing = _match_gemini_pricing(model)
        net_input = max(inp - cached, 0)
        tokens = TokenUsage(
            input_tokens=net_input,
            output_tokens=out_total,
            cache_read_tokens=cached,
            cache_create_tokens=0,
        )
        cost = SessionCost(
            input_cost=net_input * pricing["input"] / 1_000_000,
            output_cost=out_total * pricing["output"] / 1_000_000,
            cache_read_cost=cached * pricing["cached"] / 1_000_000,
            cache_create_cost=0,
        )
        timestamp = msg.get("timestamp", "")
        entries.append(UsageEntry(
            timestamp=timestamp, tokens=tokens, cost=cost,
            cwd=cwd, model=model,
        ))

    return model, entries


class GeminiCollector:
    def collect_history(self) -> list[UsageEntry]:
        all_entries: list[UsageEntry] = []
        chats_dirs = GEMINI_DIR / "tmp"
        if not chats_dirs.exists():
            return all_entries

        for session_file in chats_dirs.rglob("session-*.json"):
            _, entries = _parse_gemini_session(session_file)
            all_entries.extend(entries)

        return all_entries

    def detect_running(self) -> list[GeminiSession]:
        sessions: list[GeminiSession] = []
        for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
            try:
                name = proc.info["name"] or ""
                cmdline = proc.info["cmdline"] or []
                if "gemini" not in name.lower() and not any("gemini" in c.lower() for c in cmdline):
                    continue
                if "grep" in name.lower():
                    continue

                mem_mb = proc.memory_info().rss / (1024 * 1024)
                sessions.append(GeminiSession(
                    pid=proc.info["pid"],
                    cwd="",
                    status="active",
                    started_at=proc.info["create_time"],
                    model="gemini-2.5-flash",
                    memory_mb=mem_mb,
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return sessions
