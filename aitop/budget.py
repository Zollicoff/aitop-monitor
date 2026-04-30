"""Budget configuration screen for aitop."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Input, Label

from .config import Config


class BudgetScreen(Screen):
    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
    ]

    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config = config

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="budget-container"):
            yield Static("[bold]SET BUDGET ALERTS[/]", classes="panel-title")
            yield Static(
                "  Set spending limits. Leave 0 to disable.\n"
                "  Alerts flash when spend exceeds the threshold.\n",
            )
            yield Label("  Daily budget ($):")
            yield Input(
                value=str(self._config.daily_budget or ""),
                placeholder="e.g. 50",
                id="daily-input",
            )
            yield Label("  Weekly budget ($):")
            yield Input(
                value=str(self._config.weekly_budget or ""),
                placeholder="e.g. 250",
                id="weekly-input",
            )
            yield Label("  Monthly budget ($):")
            yield Input(
                value=str(self._config.monthly_budget or ""),
                placeholder="e.g. 1000",
                id="monthly-input",
            )
            yield Static("", id="budget-status")
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._save_all()

    def _save_all(self) -> None:
        try:
            daily = self.query_one("#daily-input", Input).value.strip()
            self._config.daily_budget = float(daily) if daily else 0
        except ValueError:
            pass
        try:
            weekly = self.query_one("#weekly-input", Input).value.strip()
            self._config.weekly_budget = float(weekly) if weekly else 0
        except ValueError:
            pass
        try:
            monthly = self.query_one("#monthly-input", Input).value.strip()
            self._config.monthly_budget = float(monthly) if monthly else 0
        except ValueError:
            pass

        status = self.query_one("#budget-status", Static)
        status.update("  [bold]Saved![/]")

    def action_pop_screen(self) -> None:
        self._save_all()
        self.app.pop_screen()
