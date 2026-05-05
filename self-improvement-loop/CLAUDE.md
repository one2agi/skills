# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is the `self-improvement-loop` skill (v4.6.13) for OpenClaw — a per-agent feedback loop that captures corrections/errors/features, detects patterns per agent workspace, notifies via per-agent channel bot, and executes A/B/C/D decisions.

## Architecture

Per-agent isolation means each agent has its own:
- `.learnings/` directory (workspace/agents/{agent}/.learnings/)
- cron job (self-improvement-{agent}) scanning only their learnings
- channel bot for notifications (agentId → accountId binding)

```
User correction → Hook captures → Writes to {agent}/.learnings/
    ↓
Hourly cron (distill) → Pattern detection (count ≥ 2)
    ↓
Notification via agent's channel bot
    ↓
User responds A/B/C/D → Correct agent session executes
```

## Key Components

| Component | Path | Purpose |
|-----------|------|---------|
| `install.sh` | install.sh | Installs skill, creates per-agent crons, injects bindings into openclaw.json |
| `setup_crons.py` | scripts/setup_crons.py | Creates/manages per-agent cron jobs |
| `handler.js` | hooks/handler.js | Hook that captures corrections, routes to agent workspace |
| `distill.sh` / `distill_json.py` | scripts/ | Distills learnings into patterns |
| `archive.sh` | scripts/archive.sh | Archives learnings older than 30 days |
| `agents-append.md` | scripts/agents-append.md | A/B/C/D decision handling logic (shared across agents) |

## Commands

### Installation
```bash
cd ~/.openclaw/workspace/skills/self-improvement-loop
bash install.sh
openclaw gateway restart
```

### Verification
```bash
# Check bindings
python3 -c "import json; print(json.dumps(json.load(open('$HOME/.openclaw/openclaw.json')).get('bindings',[]), indent=2))"

# List self-improvement crons
openclaw cron list | grep self-improvement

# Test distill (global)
bash ~/.openclaw/workspace/skills/self-improvement-loop/scripts/distill.sh --check-only

# Test distill (specific agent)
LEARNINGS_DIR="$HOME/.openclaw/workspace/agents/code-dev/.learnings" \
  bash ~/.openclaw/workspace/skills/self-improvement-loop/scripts/distill.sh --check-only
```

### Debug
```bash
# Pretty-print distill JSON
bash scripts/distill.sh --check-only | python3 -m json.tool

# Archive dry-run
bash scripts/archive.sh --dry-run

# View agent learnings
cat ~/.openclaw/workspace/code-dev/.learnings/LEARNINGS.md
```

### Adding Agents
1. Add agent to `openclaw.json` → `agents.list`
2. Re-run `bash install.sh` (creates cron + learnings dir, idempotent)

### Removing Agents
```bash
openclaw cron remove self-improvement-<agent_id>
rm -rf ~/.openclaw/workspace/<agent_id>/.learnings
```

## Important Notes

- **LEARNINGS_DIR is hardcoded in cron** — if agent workspace changes, re-run install.sh
- **Hook is globally shared** — routes by sessionKey → agentId → workspace
- **agents-append.md is shared** — A/B/C/D logic injected into each agent's AGENTS.md/memory.md at install time
- **No tests exist** in this repository

## Dependencies

- OpenClaw ≥2026.4
- Python3 ≥3.8 (for distill_json.py, write_notified.py)
- Node.js (for handler.js)
- skill-creator and skill-improvement (for A/B paths)