# aitop

Terminal monitor for AI coding tools. Track active sessions, token usage, and costs in real-time.

Supports **Claude Code**, **OpenAI Codex CLI**, and **Google Gemini CLI**. Built with [Textual](https://github.com/Textualize/textual).

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Multi-tool monitoring** — Claude Code, Codex CLI, and Gemini CLI in one dashboard
- **Live session detection** — see all running AI tool sessions with status, model, uptime, and memory
- **Cost tracking** — per-session and aggregate costs across four timeframes (today, 7 day, 30 day, all time)
- **Burn rate gauges** — visual bars showing relative spend across timeframes
- **Cost breakdown grid** — input, output, cache read, and cache write costs at a glance
- **Daily cost graph** — 30-day sparkline with today/average/peak stats
- **Agent detail view** — click or press Enter on any session to see per-project cost breakdown
- **Budget alerts** — set daily/weekly/monthly limits, get OVER/WARN indicators
- **Persistent history** — SQLite store preserves usage data even after tools prune old session logs
- **CSV export** — dump full usage history for external analysis
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
| `b` | Set budget alerts |
| `e` | Export all data to CSV |
| `q` | Quit |

## Supported Tools

### Claude Code

| Source | What it provides |
|--------|-----------------|
| `~/.claude/sessions/*.json` | Active session registry (PID, status, CWD, uptime) |
| `~/.claude/projects/*/*.jsonl` | Per-message token usage for live sessions |
| `~/.claude/projects/*/subagents/*.jsonl` | Subagent (background task) token usage |
| `~/.claude/usage-cache/dashboard-cache.json` | Historical cost data with pre-calculated costs |

### Codex CLI (OpenAI)

| Source | What it provides |
|--------|-----------------|
| `~/.codex/sessions/**/*.jsonl` | Session rollout files with token_count events |

### Gemini CLI (Google)

| Source | What it provides |
|--------|-----------------|
| `~/.gemini/tmp/*/chats/session-*.json` | Per-message token data (input/output/cached/thoughts) |

On first run, aitop imports all available data into a local SQLite database at `~/.local/share/aitop/usage.db`. Subsequent runs merge new data from active session logs, so history is preserved even after tools prune old files.

## Pricing

Costs are calculated using official API rates. All prices per million tokens:

### Claude (Anthropic)

| Model | Input | Output | Cache Write | Cache Read |
|-------|-------|--------|-------------|------------|
| Opus 4.7 | $5.00 | $25.00 | $6.25 | $0.50 |
| Opus 4.6 | $5.00 | $25.00 | $6.25 | $0.50 |
| Sonnet 4.6 | $3.00 | $15.00 | $3.75 | $0.30 |
| Haiku 4.5 | $1.00 | $5.00 | $1.25 | $0.10 |

### Codex (OpenAI)

| Model | Input | Output | Cached |
|-------|-------|--------|--------|
| GPT-5.5 | $2.00 | $8.00 | $0.50 |
| GPT-4o | $2.50 | $10.00 | $1.25 |
| o4-mini | $1.10 | $4.40 | $0.275 |

### Gemini (Google)

| Model | Input | Output | Cached |
|-------|-------|--------|--------|
| Gemini 2.5 Pro | $1.25 | $10.00 | $0.125 |
| Gemini 2.5 Flash | $0.30 | $2.50 | $0.03 |

These are API-equivalent costs for comparison purposes. Subscription plans (Claude Max, etc.) have flat monthly fees.

## Budget Alerts

Press `b` to set daily, weekly, and monthly spending limits. The burn rate panel shows:
- **OVER** — spend exceeded the threshold
- **WARN** — spend is above 80% of the threshold
- **Percentage** — current spend relative to budget

Config is saved to `~/.local/share/aitop/config.json`.

## License

MIT
