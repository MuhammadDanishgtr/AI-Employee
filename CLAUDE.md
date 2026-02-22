# AI Employee — Project Instructions

## Overview
This is a Personal AI Employee (Silver Tier) built for the Panaversity Hackathon 0. It uses Claude Code as the reasoning engine and an Obsidian vault as the knowledge base and dashboard.

## Vault Location
The Obsidian vault is at: `D:/hackathon-0-PersonalAI-Employee/AI_Employee_Vault`

## Architecture
- **Brain:** Claude Code (this agent) — reads tasks, makes decisions, writes reports
- **Memory/GUI:** Obsidian vault with Dashboard.md as the main status view
- **Watcher 1:** File System Watcher (Python/watchdog) monitors `Drop_Folder/` for new files
- **Watcher 2:** Gmail Watcher polls Gmail for unread important emails every 2 minutes
- **Poster:** LinkedIn Poster publishes approved posts via Playwright every 15 minutes
- **Orchestrator:** APScheduler coordinates all watchers and auto-updates Dashboard
- **MCP Server:** `mcp_servers/gmail_send/server.py` exposes send_email/draft_email tools
- **Rules:** `Company_Handbook.md` defines all permission boundaries and behavior rules

## Key Rules
1. **Always read `Company_Handbook.md` before taking sensitive actions** — it defines what's auto-approved vs. what needs human approval.
2. **Never delete files** — always move them to `/Done` for audit trail.
3. **Log everything** — append JSON entries to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`.
4. **Human-in-the-loop** — for sensitive actions (payments, new contacts, emails, LinkedIn posts, bulk operations), create approval files in `/Pending_Approval/` instead of acting directly.
5. **Update Dashboard** — after processing items, refresh `Dashboard.md` with current counts and status.

## Available Skills
- `/process-inbox` — Process pending items in `/Needs_Action`
- `/update-dashboard` — Refresh Dashboard.md with current vault status
- `/vault-manager` — Manage vault files, create plans, check approvals, archive items
- `/gmail-checker` — Manually trigger Gmail check and process email action files
- `/linkedin-poster` — Draft a LinkedIn post and route through HITL approval
- `/create-plan` — Create a structured Plan.md using the reasoning loop

## Folder Structure
```
AI_Employee_Vault/
├── Dashboard.md            # Main status dashboard (auto-updated every 10 min)
├── Company_Handbook.md     # Rules of engagement
├── Inbox/                  # Raw inputs
├── Needs_Action/           # Items awaiting processing
├── Plans/                  # Action plans (Plan.md reasoning loop)
├── Pending_Approval/       # Needs human approval (HITL)
├── Approved/               # Approved actions (orchestrator executes)
├── Rejected/               # Rejected actions
├── Done/                   # Completed/archived
├── Logs/                   # Audit logs (JSON lines)
├── Briefings/              # Generated reports
└── Drop_Folder/            # Watched by File System Watcher
```

## Starting the Orchestrator
Start all watchers with the orchestrator:
```bash
py watchers/orchestrator.py
```
Or start individual watchers:
```bash
py watchers/filesystem_watcher.py   # File system only
py watchers/gmail_watcher.py        # Gmail only
py watchers/linkedin_watcher.py     # LinkedIn poster only
```

## MCP Server
The Gmail Send MCP server provides `send_email`, `draft_email`, and `list_drafts` tools.
Start it with: `py mcp_servers/gmail_send/server.py`

## Python
Use `py` command (not `python`) to run Python scripts on this system.
