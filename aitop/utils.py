"""Shared utilities for aitop."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

GAUGE_CHARS = "░▒▓█"
SPARK_CHARS = "▁▂▃▄▅▆▇█"

TF_SHORT = {"today": "Today", "7d": "7 Day", "30d": "30 Day", "all": "All"}


def since_for(tf: str) -> str | None:
    now = datetime.now(timezone.utc)
    if tf == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    if tf == "7d":
        return (now - timedelta(days=7)).isoformat()
    if tf == "30d":
        return (now - timedelta(days=30)).isoformat()
    return None


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


def sparkline(values: list[float]) -> str:
    if not values:
        return ""
    max_val = max(values) or 1
    return "".join(
        SPARK_CHARS[min(int(v / max_val * (len(SPARK_CHARS) - 1)), len(SPARK_CHARS) - 1)]
        for v in values
    )


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


def short_path(cwd: str) -> str:
    from pathlib import Path
    home = str(Path.home())
    if cwd.startswith(home):
        return "~" + cwd[len(home):]
    return cwd
