# Google Workspace Agent Skills Bundle

A hierarchical set of AI agent skills for the [`gws` CLI](https://github.com/googleworkspace/cli).

## Structure

```
workspace-skills/
├── setup.sh                    # One-time interactive setup script
├── README.md                   # This file
└── workspace/
    ├── SKILL.md                # Top-level router — dispatches to product skills
    ├── drive/
    │   └── SKILL.md            # Google Drive specialist
    ├── gmail/
    │   └── SKILL.md            # Gmail specialist
    ├── calendar/
    │   └── SKILL.md            # Google Calendar specialist
    ├── sheets/
    │   └── SKILL.md            # Google Sheets specialist
    ├── docs/
    │   └── SKILL.md            # Google Docs specialist
    ├── slides/
    │   └── SKILL.md            # Google Slides specialist
    └── meet/
        └── SKILL.md            # Google Meet specialist
```

## How It Works

**Router skill** (`workspace/SKILL.md`): The top-level entry point. It reads user
intent, matches it to the right product using a hybrid routing table (keyword hints
plus domain descriptions), and delegates to the product-specific skill. Cross-product
workflows are handled by invoking multiple product skills in sequence.

**Product skills** (`workspace/<product>/SKILL.md`): Each is a self-contained expert
for one Google Workspace product. They can be used standalone (without the router) or
via the router. Each skill is organized into clearly separated Read and Write operation
sections with real, copy-pasteable `gws` CLI commands.

## Setup

```bash
chmod +x setup.sh
./setup.sh
```

The setup script will:
1. Check for Node.js 18+
2. Check for (or install) the `gws` CLI
3. Let you pick which Google Workspace services to enable
4. Walk through GCP project setup and API enablement
5. Authenticate via OAuth with scoped permissions
6. Verify the setup works

## Installing Skills Into Your Agent

**Generic (copy into your agent's skill directory):**
```bash
cp -r workspace/ /path/to/your/agent/skills/
```

**Claude Code:**
```bash
cp -r workspace/ .claude/skills/
```

**OpenClaw:**
```bash
ln -s $(pwd)/workspace ~/.openclaw/skills/workspace
```

## Using Skills Standalone

Each product skill works independently. If you only need Gmail support, just
use `workspace/gmail/SKILL.md` without the router. The skill contains everything
needed: command syntax, read/write operations, API resource references, and
discovery commands.

## Safety

All skills enforce a confirmation rule: any command that creates, updates, or
deletes data must be confirmed with the user before execution. Use `--dry-run`
to preview uncertain commands safely.
