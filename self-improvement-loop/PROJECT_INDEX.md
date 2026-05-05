# Project Index: self-improvement-loop

Generated: 2026-04-26

## 📁 Project Structure

```
self-improvement-loop/
├── SKILL.md              # Main skill documentation (v4.6.13)
├── _meta.json            # Package metadata (ownerId, slug, version)
├── install.sh            # Installation script
├── _meta.json
├── .clawhub/             # Hub configuration
│   └── origin.json
├── hooks/                # Hook handlers for OpenClaw
│   ├── HOOK.md           # Hook documentation
│   └── handler.js        # Hook implementation
├── scripts/              # Core automation scripts
│   ├── setup_crons.py    # Creates per-agent cron jobs
│   ├── distill.sh        # Shell wrapper for distillation
│   ├── distill_json.py   # JSON-based learning distillation
│   ├── archive.sh        # Archives old learnings
│   ├── write_notified.py # Writes notified state
│   ├── agents-append.md  # A/B/C/D handling logic
│   └── cron-payloads.json # Cron job payloads
├── learnings/             # Learning files (per-agent, generated)
│   ├── LEARNINGS.md
│   ├── ERRORS.md
│   └── FEATURE_REQUESTS.md
└── references/
    └── setup-guide.md    # Setup guide
```

## 🚀 Entry Points

- **CLI**: `install.sh` - Installs self-improvement-loop into agent workspaces
- **Cron Entry**: `scripts/setup_crons.py` - Creates per-agent cron jobs (hourly distill + scheduled archive)
- **Hook Entry**: `hooks/handler.js` - Captures corrections/errors from OpenClaw hooks

## 📦 Core Modules

### Script: setup_crons.py
- Path: scripts/setup_crons.py
- Exports: `setup_crons()`, `create_agent_crons()`, `get_agent_info()`
- Purpose: Creates and manages per-agent cron jobs for the improvement loop

### Script: distill_json.py
- Path: scripts/distill_json.py
- Exports: `distill_learnings()`, `extract_patterns()`, `generate_suggestions()`
- Purpose: Distills raw learnings into structured patterns with confidence scores

### Script: archive.sh
- Path: scripts/archive.sh
- Exports: archive_old_learnings(), rotate_archives()
- Purpose: Archives learnings older than threshold (default 30 days)

### Script: write_notified.py
- Path: scripts/write_notified.py
- Exports: `mark_notified()`, `check_notified()`
- Purpose: Tracks which patterns have been notified to prevent duplicates

### Config: agents-append.md
- Path: scripts/agents-append.md
- Exports: A/B/C/D decision handling logic
- Purpose: Shared logic for implementing user decisions in the correct agent session

### Hook: handler.js
- Path: hooks/handler.js
- Exports: `handle_hook()`
- Purpose: Processes OpenClaw hook events (corrections, errors, feature requests)

## 🔧 Configuration

- `cron-payloads.json`: Defines cron job payloads for distill and archive operations
- `_meta.json`: Package metadata (ownerId: `kn70ps8raw9bhs1czcvkg53z31842jqm`, slug: `self-improvement-loop`, version: `4.6.13`)
- `.clawhub/origin.json`: Hub origin configuration

## 📚 Documentation

- `SKILL.md`: Full skill documentation with data flow diagrams, per-agent architecture, and usage guide
- `references/setup-guide.md`: Setup guide for installing the skill
- `hooks/HOOK.md`: Hook documentation for OpenClaw integration

## 🧪 Test Coverage

- No test files detected in repository

## 🔗 Key Dependencies

- OpenClaw workspace structure (workspace/agents/{agent-name}/.learnings/)
- Per-agent channel bindings (agentId → accountId mapping)
- OpenClaw hook system

## 📝 Quick Start

1. Run `install.sh` to install the skill into agent workspaces
2. `install.sh` creates per-agent .learnings/ directories and configures hooks
3. `scripts/setup_crons.py` sets up hourly cron jobs for pattern detection
4. Pattern matches (count ≥ 2) trigger notifications via per-agent channel bots

## 🔄 Data Flow

```
User correction → Hook captures → Writes to {agent}/.learnings/
    ↓
Hourly cron (distill) → Pattern detection (count ≥ 2)
    ↓
Notification via agent's channel bot
    ↓
User responds A/B/C/D → Correct agent session executes → Updates workspace
```