"""Agent detail screen for aitop."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, Static

from .collectors.claude import (
    ClaudeSession,
    TokenUsage,
    SessionCost,
    TIMEFRAMES,
)
from .store import UsageStore

TF_SHORT = {"today": "Today", "7d": "7 Day", "30d": "30 Day", "all": "All"}

GAUGE_CHARS = "░▒▓█"


def _since_for(tf: str) -> str | None:
    now = datetime.now(timezone.utc)
    if tf == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    if tf == "7d":
        return (now - timedelta(days=7)).isoformat()
    if tf == "30d":
        return (now - timedelta(days=30)).isoformat()
    return None


def fmt_cost(val: float) -> str:
    if val >= 10_000:
        return f"${val / 1000:.1f}K"
    if val >= 1000:
        return f"${val:,.0f}"
    if val >= 1:
        return f"${val:.2f}"
    if val > 0:
        return f"${val:.3f}"
    return "$0"


def cost_gauge(value: float, max_val: float, width: int = 20) -> str:
    if max_val <= 0:
        return GAUGE_CHARS[0] * width
    ratio = min(value / max_val, 1.0)
    filled = int(ratio * width)
    remainder = (ratio * width) - filled
    bar = GAUGE_CHARS[3] * filled
    if filled < width:
        partial_idx = int(remainder * (len(GAUGE_CHARS) - 1))
        bar += GAUGE_CHARS[partial_idx]
        bar += GAUGE_CHARS[0] * (width - filled - 1)
    return bar


def short_path(cwd: str) -> str:
    home = str(Path.home())
    if cwd.startswith(home):
        return "~" + cwd[len(home):]
    return cwd


class AgentSummary(Static):
    def __init__(self, session: ClaudeSession, store: UsageStore) -> None:
        super().__init__()
        self._session = session
        self._store = store

    def render(self) -> str:
        s = self._session
        name = s.agent_name.lower()
        status = "[bold]● active[/]" if s.status == "busy" else "[dim]○ idle[/]"
        model = s.model.replace("claude-", "").replace("-20251001", "")

        lines = [
            f"  [bold]{s.agent_name}[/]  {status}",
            f"  Model: {model}   PID: {s.pid}   Uptime: {s.uptime_str}   Mem: {s.memory_mb:.0f}MB",
            "",
        ]

        header = f"  {'':14}"
        for tf in TIMEFRAMES:
            header += f" [bold underline]{TF_SHORT[tf]:>8}[/]"
        lines.append(header)

        costs: dict[str, SessionCost] = {}
        for tf in TIMEFRAMES:
            _, sc = self._store.query_totals(
                agent_name=name, since=_since_for(tf)
            )
            costs[tf] = sc

        for label, attr in [
            ("Input", "input_cost"),
            ("Output", "output_cost"),
            ("Cache read", "cache_read_cost"),
            ("Cache write", "cache_create_cost"),
        ]:
            row = f"  [dim]{label:<14}[/]"
            for tf in TIMEFRAMES:
                row += f" {fmt_cost(getattr(costs[tf], attr)):>8}"
            lines.append(row)

        lines.append(f"  {'─' * 48}")
        total_row = f"  [bold]{'TOTAL':<14}[/]"
        for tf in TIMEFRAMES:
            total_row += f" [bold reverse] {fmt_cost(costs[tf].total):>6} [/]"
        lines.append(total_row)

        return "\n".join(lines)


class ProjectBreakdown(Static):
    def __init__(self, session: ClaudeSession, store: UsageStore) -> None:
        super().__init__()
        self._session = session
        self._store = store

    def render(self) -> str:
        name = self._session.agent_name.lower()
        projects = self._store.query_by_project(agent_name=name)
        if not projects:
            return "  [dim]No project data[/]"

        max_cost = max((sc.total for _, _, sc in projects), default=1) or 0.01
        lines = []
        lines.append(
            f"  [dim]{'Project':<40} {'Burn':>16}"
            f"  {'Cost':>9} │ {'Tokens':>7}[/]"
        )

        for cwd, tokens, cost in projects:
            path = short_path(cwd)
            if len(path) > 38:
                path = "…" + path[-37:]
            gauge = cost_gauge(cost.total, max_cost, 16)
            lines.append(
                f"  {path:<40} {gauge}"
                f"  [bold]{fmt_cost(cost.total):>9}[/]"
                f" │ {tokens.total_str():>7}"
            )

        return "\n".join(lines)


class AgentDetailScreen(Screen):
    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, session: ClaudeSession, store: UsageStore) -> None:
        super().__init__()
        self._session = session
        self._store = store

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="detail-container"):
            yield Static(
                f"[bold]AGENT: {self._session.agent_name.upper()}[/]",
                classes="panel-title",
            )
            yield AgentSummary(self._session, self._store)
            yield Static("")
            yield Static("[bold]COST BY PROJECT (all time)[/]", classes="panel-title")
            yield ProjectBreakdown(self._session, self._store)
        yield Footer()

    def action_pop_screen(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()
