"""aitop — AI Tools Terminal Monitor."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.widgets import Header, Footer, Static

from .collectors.claude import (
    ClaudeCollector,
    ClaudeData,
    ClaudeSession,
    TIMEFRAMES,
    TIMEFRAME_LABELS,
)


REFRESH_INTERVAL = 5.0
CSS_PATH = Path(__file__).parent / "css" / "app.tcss"

LOGO = """[bold cyan]  ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
  █                                                  █
  █  ░█▀▀▄ ░▀█▀ ▀▀█▀▀ ░▄▀▀▄ ░█▀▀▄        [dim]AI Tools[/][bold cyan]    █
  █  ░█▄▄█ ░░█░ ░░█░░ ░█░░█ ░█▄▄█        [dim]Monitor[/][bold cyan]     █
  █  ░█░░█ ░▄█▄ ░░█░░ ░░▀▀░ ░█░░░        [dim]v0.1.0[/][bold cyan]      █
  █                                                  █
  ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀[/]"""

GAUGE_CHARS = "░▒▓█"

TF_SHORT = {"today": "Today", "7d": "7 Day", "30d": "30 Day", "all": "All"}


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


def short_model(model: str) -> str:
    return (
        model
        .replace("claude-", "")
        .replace("-20251001", "")
    )


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


class BurnRatePanel(Static):
    def __init__(self) -> None:
        super().__init__()
        self._data: ClaudeData | None = None

    def update_data(self, data: ClaudeData) -> None:
        self._data = data
        self.refresh()

    def render(self) -> str:
        if not self._data:
            return ""

        costs = {}
        for tf in TIMEFRAMES:
            _, tc = self._data.totals_for(tf)
            costs[tf] = tc.total

        max_cost = max(costs.values()) or 1
        colors = {
            "today": "bold green",
            "7d": "bold cyan",
            "30d": "bold yellow",
            "all": "bold magenta",
        }

        lines = []
        for tf in TIMEFRAMES:
            val = costs[tf]
            gauge = cost_gauge(val, max_cost, 24)
            c = colors[tf]
            lines.append(
                f"  [{c}]{TF_SHORT[tf]:<7}[/]"
                f" [{c}]{gauge}[/]"
                f" [bold]{fmt_cost(val):>8}[/]"
            )
        return "\n".join(lines)


class CostGrid(Static):
    def __init__(self) -> None:
        super().__init__()
        self._data: ClaudeData | None = None

    def update_data(self, data: ClaudeData) -> None:
        self._data = data
        self.refresh()

    def render(self) -> str:
        if not self._data:
            return ""

        lines = []

        header = f"  [bold]{'':14}[/]"
        for tf in TIMEFRAMES:
            header += f" [bold underline]{TF_SHORT[tf]:>8}[/]"
        lines.append(header)

        row_defs = [
            ("Input", "input_cost", "dim cyan"),
            ("Output", "output_cost", "bold cyan"),
            ("Cache read", "cache_read_cost", "green"),
            ("Cache write", "cache_create_cost", "yellow"),
        ]

        for label, attr, color in row_defs:
            row = f"  [{color}]{label:<14}[/]"
            for tf in TIMEFRAMES:
                _, tc = self._data.totals_for(tf)
                val = getattr(tc, attr)
                row += f" [{color}]{fmt_cost(val):>8}[/]"
            lines.append(row)

        lines.append(f"  {'─' * 48}")

        total_row = f"  [bold]{'TOTAL':<14}[/]"
        for tf in TIMEFRAMES:
            _, tc = self._data.totals_for(tf)
            total_row += f" [bold reverse] {fmt_cost(tc.total):>6} [/]"
        lines.append(total_row)

        return "\n".join(lines)


class AgentCard(Static):
    def __init__(self, session: ClaudeSession, max_cost: float) -> None:
        super().__init__()
        self.session = session
        self.max_cost = max_cost

    def render(self) -> str:
        s = self.session
        tokens_today, cost_today = s.usage_for("today")

        if s.status == "busy":
            indicator = "[bold green]▶[/]"
            name_style = "bold green"
        else:
            indicator = "[dim]●[/]"
            name_style = "dim"

        model = short_model(s.model) if s.model else "—"
        gauge = cost_gauge(cost_today.total, self.max_cost, 12)

        if cost_today.total > self.max_cost * 0.5:
            gauge_color = "yellow"
        elif cost_today.total > 0:
            gauge_color = "cyan"
        else:
            gauge_color = "dim"

        return (
            f" {indicator} [{name_style}]{s.agent_name:<9}[/]"
            f" [dim]{model:<13}[/]"
            f" [{gauge_color}]{gauge}[/]"
            f" [bold]{fmt_cost(cost_today.total):>9}[/]"
            f" [dim]│[/] {tokens_today.total_str():>7}"
            f" [dim]│[/] {s.uptime_str:>8}"
            f" [dim]│[/] {s.memory_mb:>5.0f}M"
        )


class AiTop(App):
    TITLE = "aitop"
    SUB_TITLE = "AI Tools Monitor"
    CSS_PATH = CSS_PATH

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("d", "toggle_dark", "Dark/Light"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.collector = ClaudeCollector()
        self._data: ClaudeData | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            yield Static(LOGO, id="logo")
            with Horizontal(id="top-panels"):
                with Vertical(id="burn-panel"):
                    yield Static("[bold] BURN RATE[/]", classes="panel-title")
                    yield BurnRatePanel()
                with Vertical(id="cost-grid-panel"):
                    yield Static("[bold] COST BREAKDOWN[/]", classes="panel-title")
                    yield CostGrid()
            with Vertical(id="fleet-panel"):
                yield Static("[bold] FLEET STATUS[/]", classes="panel-title")
                yield Static("", id="fleet-header")
                yield Vertical(id="fleet-cards")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_data()
        self.set_interval(REFRESH_INTERVAL, self._refresh_data)

    def _refresh_data(self) -> None:
        self._data = self.collector.collect()
        self._update_all()

    def _update_all(self) -> None:
        if not self._data:
            return
        self.query_one(BurnRatePanel).update_data(self._data)
        self.query_one(CostGrid).update_data(self._data)
        self._update_fleet()

    def _update_fleet(self) -> None:
        if not self._data:
            return

        header = self.query_one("#fleet-header", Static)
        header.update(
            f" [dim]  {'Agent':<9} {'Model':<13}"
            f" {'Burn':>12}  {'Cost':>9}"
            f" │ {'Tokens':>7}"
            f" │ {'Uptime':>8}"
            f" │ {'Mem':>6}[/]"
        )

        container = self.query_one("#fleet-cards")
        container.remove_children()

        max_cost = max(
            (s.usage_for("today")[1].total for s in self._data.sessions), default=1
        ) or 0.01

        for s in self._data.sessions:
            container.mount(AgentCard(s, max_cost))

    def action_refresh(self) -> None:
        self._refresh_data()

    def action_toggle_dark(self) -> None:
        if self.theme == "textual-dark":
            self.theme = "textual-light"
        else:
            self.theme = "textual-dark"


def run() -> None:
    app = AiTop()
    app.run()
