"""aitop — AI Tools Terminal Monitor."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.widgets import Header, Footer, Static

from textual.events import Click

from .collectors.claude import (
    ClaudeCollector,
    ClaudeData,
    ClaudeSession,
    TIMEFRAMES,
    TIMEFRAME_LABELS,
)
from .detail import AgentDetailScreen


REFRESH_INTERVAL = 5.0
CSS_PATH = Path(__file__).parent / "css" / "app.tcss"

LOGO = """\
  ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
  █                                                  █
  █  ░█▀▀▄ ░▀█▀ ▀▀█▀▀ ░▄▀▀▄ ░█▀▀▄        AI Tools    █
  █  ░█▄▄█ ░░█░ ░░█░░ ░█░░█ ░█▄▄█        Monitor     █
  █  ░█░░█ ░▄█▄ ░░█░░ ░░▀▀░ ░█░░░        v0.1.0      █
  █                                                  █
  ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀"""

GAUGE_CHARS = "░▒▓█"

TF_SHORT = {"today": "Today", "7d": "7 Day", "30d": "30 Day", "all": "All"}

THEMES = [
    "textual-dark",
    "dracula",
    "tokyo-night",
    "catppuccin-mocha",
    "nord",
    "gruvbox",
    "monokai",
    "rose-pine",
    "solarized-dark",
    "textual-light",
    "catppuccin-latte",
    "solarized-light",
]


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

        lines = []
        for tf in TIMEFRAMES:
            val = costs[tf]
            gauge = cost_gauge(val, max_cost, 24)
            lines.append(
                f"  [bold]{TF_SHORT[tf]:<7}[/]"
                f" {gauge}"
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
            ("Input", "input_cost"),
            ("Output", "output_cost"),
            ("Cache read", "cache_read_cost"),
            ("Cache write", "cache_create_cost"),
        ]

        for label, attr in row_defs:
            row = f"  [dim]{label:<14}[/]"
            for tf in TIMEFRAMES:
                _, tc = self._data.totals_for(tf)
                val = getattr(tc, attr)
                row += f" {fmt_cost(val):>8}"
            lines.append(row)

        lines.append(f"  {'─' * 48}")

        total_row = f"  [bold]{'TOTAL':<14}[/]"
        for tf in TIMEFRAMES:
            _, tc = self._data.totals_for(tf)
            total_row += f" [bold reverse] {fmt_cost(tc.total):>6} [/]"
        lines.append(total_row)

        return "\n".join(lines)


class AgentCard(Static):
    can_focus = True

    def __init__(self, session: ClaudeSession, max_cost: float) -> None:
        super().__init__()
        self.session = session
        self.max_cost = max_cost

    def on_click(self, event: Click) -> None:
        self.app.push_screen(AgentDetailScreen(self.session))

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.app.push_screen(AgentDetailScreen(self.session))

    def render(self) -> str:
        s = self.session
        tokens_today, cost_today = s.usage_for("today")

        if s.status == "busy":
            indicator = "[bold]▶[/]"
            name_style = "bold"
        else:
            indicator = "[dim]●[/]"
            name_style = "dim"

        model = short_model(s.model) if s.model else "—"
        gauge = cost_gauge(cost_today.total, self.max_cost, 12)

        return (
            f" {indicator} [{name_style}]{s.agent_name:<9}[/]"
            f" [dim]{model:<13}[/]"
            f" {gauge}"
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
        Binding("t", "cycle_theme", "Theme"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.collector = ClaudeCollector()
        self._data: ClaudeData | None = None
        self._theme_idx = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            yield Static(LOGO, id="logo")
            with Horizontal(id="top-panels"):
                with Vertical(id="burn-panel"):
                    yield Static("[bold]BURN RATE[/]", classes="panel-title")
                    yield BurnRatePanel()
                with Vertical(id="cost-grid-panel"):
                    yield Static("[bold]COST BREAKDOWN[/]", classes="panel-title")
                    yield CostGrid()
            with Vertical(id="fleet-panel"):
                yield Static("[bold]FLEET STATUS[/]", classes="panel-title")
                yield Static("", id="fleet-header")
                yield Vertical(id="fleet-cards")
        yield Footer()

    def on_mount(self) -> None:
        self.theme = THEMES[0]
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
            f"   {'Agent':<9} {'Model':<13}"
            f" {'Burn':>12}  {'Cost':>9}"
            f" │ {'Tokens':>7}"
            f" │ {'Uptime':>8}"
            f" │ {'Mem':>6}"
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

    def action_cycle_theme(self) -> None:
        self._theme_idx = (self._theme_idx + 1) % len(THEMES)
        self.theme = THEMES[self._theme_idx]
        self.sub_title = f"AI Tools Monitor — {self.theme}"

    def action_quit(self) -> None:
        self.exit()


def run() -> None:
    app = AiTop()
    app.run()
