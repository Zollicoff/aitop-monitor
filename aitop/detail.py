"""Agent detail screen for aitop."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, Static

from .collectors.claude import (
    ClaudeSession,
    SessionCost,
    TIMEFRAMES,
)
from .store import UsageStore
from .utils import cost_gauge, fmt_cost, short_path, since_for, TF_SHORT


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
                agent_name=name, since=since_for(tf)
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
