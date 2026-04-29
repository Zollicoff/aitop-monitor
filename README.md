# aitop

Terminal monitor for AI coding tools. Track active sessions, token usage, and costs in real-time.

Currently supports **Claude Code**. Built with [Textual](https://github.com/Textualize/textual).

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Live session monitoring** — see all running Claude Code sessions with status, model, uptime, and memory
- **Cost tracking** — per-session and aggregate costs across four timeframes (today, 7 day, 30 day, all time)
- **Burn rate gauges** — visual bars showing relative spend across timeframes
- **Cost breakdown grid** — input, output, cache read, and cache write costs at a glance
- **Agent detail view** — click or press Enter on any session to see per-project cost breakdown
- **Persistent history** — SQLite store preserves usage data even after Claude Code prunes old session logs
- **12 built-in themes** — dracula, tokyo-night, catppuccin, nord, gruvbox, monokai, rose-pine, solarized, and more
- **Auto-refresh** — updates every 5 seconds

## Install

```bash
git clone https://github.com/Zollicoff/aitop-monitor.git
cd aitop-monitor
python3 -m venv .venv
source .venv/bin/activate
pip install textual psutil
```

## Usage

```bash
source .venv/bin/activate
python run.py
```

### Keybindings

| Key | Action |
|-----|--------|
| `t` | Cycle through themes |
| `r` | Force refresh |
| `Enter` | Open agent detail view |
| `Esc` | Back to main view |
| `q` | Quit |

## Data Sources

aitop reads from Claude Code's local data:

| Source | What it provides |
|--------|-----------------|
| `~/.claude/sessions/*.json` | Active session registry (PID, status, CWD, uptime) |
| `~/.claude/projects/*/*.jsonl` | Per-message token usage for live sessions |
| `~/.claude/usage-cache/dashboard-cache.json` | Historical cost data with pre-calculated costs |

On first run, aitop imports the dashboard cache into a local SQLite database at `~/.local/share/aitop/usage.db`. Subsequent runs merge new data from active session logs, so history is preserved even after Claude Code prunes old files.

## Pricing

Costs are calculated using official Anthropic API rates. Cache writes use the 5-minute rate (1.25x input price). All prices per million tokens:

| Model | Input | Output | Cache Write | Cache Read |
|-------|-------|--------|-------------|------------|
| Opus 4.7 | $5.00 | $25.00 | $6.25 | $0.50 |
| Opus 4.6 | $5.00 | $25.00 | $6.25 | $0.50 |
| Sonnet 4.6 | $3.00 | $15.00 | $3.75 | $0.30 |
| Haiku 4.5 | $1.00 | $5.00 | $1.25 | $0.10 |

These are API-equivalent costs for comparison purposes. If you're on a Claude Max subscription, your actual billing is a flat monthly fee.

## Roadmap

- [ ] Codex CLI support
- [ ] Gemini CLI support
- [ ] Subagent cost tracking
- [ ] Daily/weekly cost graphs
- [ ] Budget alerts
- [ ] Export to CSV

## License

MIT
