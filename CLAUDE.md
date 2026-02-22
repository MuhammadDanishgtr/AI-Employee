# AI Employee — Project Instructions

## Overview
This is a Personal AI Employee (Bronze Tier) built for the Panaversity Hackathon 0. It uses Claude Code as the reasoning engine and an Obsidian vault as the knowledge base and dashboard.

## Vault Location
The Obsidian vault is at: `D:/hackathon-0-PersonalAI-Employee/AI_Employee_Vault`

## Architecture
- **Brain:** Claude Code (this agent) — reads tasks, makes decisions, writes reports
- **Memory/GUI:** Obsidian vault with Dashboard.md as the main status view
- **Senses:** File System Watcher (Python/watchdog) monitors `Drop_Folder/` for new files
- **Rules:** `Company_Handbook.md` defines all permission boundaries and behavior rules

## Key Rules
1. **Always read `Company_Handbook.md` before taking sensitive actions** — it defines what's auto-approved vs. what needs human approval.
2. **Never delete files** — always move them to `/Done` for audit trail.
3. **Log everything** — append JSON entries to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`.
4. **Human-in-the-loop** — for sensitive actions (payments, new contacts, bulk operations), create approval files in `/Pending_Approval/` instead of acting directly.
5. **Update Dashboard** — after processing items, refresh `Dashboard.md` with current counts and status.

## Available Skills
- `/process-inbox` — Process pending items in `/Needs_Action`
- `/update-dashboard` — Refresh Dashboard.md with current vault status
- `/vault-manager` — Manage vault files, create plans, check approvals, archive items

## Folder Structure
```
AI_Employee_Vault/
├── Dashboard.md            # Main status dashboard
├── Company_Handbook.md     # Rules of engagement
├── Inbox/                  # Raw inputs
├── Needs_Action/           # Items awaiting processing
├── Plans/                  # Action plans
├── Pending_Approval/       # Needs human approval
├── Approved/               # Approved actions
├── Rejected/               # Rejected actions
├── Done/                   # Completed/archived
├── Logs/                   # Audit logs (JSON lines)
├── Briefings/              # Generated reports
└── Drop_Folder/            # Watched by File System Watcher
```

## File Watcher
Start the file watcher with:
```bash
py watchers/filesystem_watcher.py
```
It monitors `Drop_Folder/` and creates action files in `/Needs_Action` automatically.

## Python
Use `py` command (not `python`) to run Python scripts on this system.
