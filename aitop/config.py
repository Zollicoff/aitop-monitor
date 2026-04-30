"""Configuration management for aitop."""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".local" / "share" / "aitop"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULTS = {
    "daily_budget": 0,
    "weekly_budget": 0,
    "monthly_budget": 0,
}


class Config:
    def __init__(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if CONFIG_PATH.exists():
            try:
                self._data = json.loads(CONFIG_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}
        for key, default in DEFAULTS.items():
            self._data.setdefault(key, default)

    def save(self) -> None:
        CONFIG_PATH.write_text(json.dumps(self._data, indent=2) + "\n")

    @property
    def daily_budget(self) -> float:
        return float(self._data.get("daily_budget", 0))

    @daily_budget.setter
    def daily_budget(self, val: float) -> None:
        self._data["daily_budget"] = val
        self.save()

    @property
    def weekly_budget(self) -> float:
        return float(self._data.get("weekly_budget", 0))

    @weekly_budget.setter
    def weekly_budget(self, val: float) -> None:
        self._data["weekly_budget"] = val
        self.save()

    @property
    def monthly_budget(self) -> float:
        return float(self._data.get("monthly_budget", 0))

    @monthly_budget.setter
    def monthly_budget(self, val: float) -> None:
        self._data["monthly_budget"] = val
        self.save()

    @property
    def has_budgets(self) -> bool:
        return any(
            self._data.get(k, 0) > 0
            for k in ("daily_budget", "weekly_budget", "monthly_budget")
        )
