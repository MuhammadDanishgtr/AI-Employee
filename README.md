# AI Employee — Silver Tier

> Personal AI Employee built for **Panaversity Hackathon 0** — an autonomous agent that manages tasks, monitors Gmail, auto-posts to LinkedIn, maintains an audit trail, and keeps humans in the loop for sensitive actions.

## Overview

This project implements a **Silver Tier** Personal AI Employee using **Claude Code** as the reasoning engine, an **Obsidian vault** as the knowledge base and dashboard, and multiple watchers coordinated by an APScheduler orchestrator.

## Architecture

| Component | Technology | Role |
|-----------|-----------|------|
| Brain | Claude Code (claude-sonnet-4-6) | Reads tasks, makes decisions, writes reports |
| Memory / GUI | Obsidian Vault | Dashboard, logs, plans, approvals |
| Watcher 1 | Python `watchdog` | Monitors `Drop_Folder/` for new files |
| Watcher 2 | Gmail API + `google-auth` | Polls Gmail for unread important emails |
| Poster | Playwright (Chromium) | Auto-posts approved content to LinkedIn |
| Orchestrator | APScheduler | Coordinates all watchers on schedules |
| MCP Server | `mcp` + Gmail API | `send_email` / `draft_email` tools for Claude |
| Rules | `Company_Handbook.md` | Defines permission boundaries |

## Folder Structure

```
AI_Employee_Vault/
├── Dashboard.md            # Main status dashboard (auto-updated)
├── Company_Handbook.md     # Rules of engagement
├── Inbox/                  # Raw inputs
├── Needs_Action/           # Items awaiting processing
├── Plans/                  # AI-generated action plans (Plan.md loop)
├── Pending_Approval/       # Needs human approval (HITL)
├── Approved/               # Human-approved actions
├── Rejected/               # Human-rejected actions
├── Done/                   # Completed / archived
├── Logs/                   # Audit logs (JSON lines)
├── Briefings/              # Generated reports
└── Drop_Folder/            # Watched by File System Watcher
```

## Key Rules

1. **Read `Company_Handbook.md` before sensitive actions** — it defines what is auto-approved vs. what needs human sign-off.
2. **Never delete files** — always move to `/Done` for a full audit trail.
3. **Log everything** — JSON entries appended to `Logs/YYYY-MM-DD.json`.
4. **Human-in-the-loop** — payments, new contacts, emails, LinkedIn posts, and bulk operations go to `/Pending_Approval/` first.
5. **Update Dashboard** — `Dashboard.md` is refreshed every 10 minutes automatically.

## Getting Started

### Prerequisites

- Python 3.13+
- [Obsidian](https://obsidian.md/) (optional, for the GUI dashboard)
- Claude Code CLI
- Docker (optional)

### Install dependencies

```bash
pip install watchdog google-auth google-auth-oauthlib google-api-python-client \
            apscheduler playwright python-dotenv mcp
playwright install chromium
```

### Configure environment

```bash
cp .env.example .env
# Edit .env with your values
```

### Start the Orchestrator (all watchers)

```bash
py watchers/orchestrator.py
```

The orchestrator starts all watchers:
- **File System Watcher** — continuous, monitors `Drop_Folder/`
- **Gmail Watcher** — every 2 minutes (requires Gmail credentials)
- **LinkedIn Poster** — every 15 minutes (requires LinkedIn credentials)
- **Dashboard Update** — every 10 minutes

### Start individual watchers

```bash
# File system watcher only
py watchers/filesystem_watcher.py

# Gmail watcher only
py watchers/gmail_watcher.py --interval 120

# LinkedIn poster only
py watchers/linkedin_watcher.py --once
```

## Gmail Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable **Gmail API**
3. Create OAuth2 credentials (Desktop app type)
4. Download `credentials.json` → save as `credentials/gmail_credentials.json`
5. Set in `.env`:
   ```
   GMAIL_CREDENTIALS_PATH=./credentials/gmail_credentials.json
   GMAIL_TOKEN_PATH=./credentials/gmail_token.json
   ```
6. Run Gmail watcher once — a browser window will open for OAuth consent
7. After consent, token is saved automatically for future runs

## LinkedIn Setup

1. Set your LinkedIn credentials in `.env`:
   ```
   LINKEDIN_EMAIL=your@email.com
   LINKEDIN_PASSWORD=yourpassword
   LINKEDIN_SESSION_PATH=./credentials/linkedin_session
   ```
2. Run `/linkedin-poster` skill to create a draft post
3. Review and move the approval file to `/Approved/`
4. The orchestrator will post it within 15 minutes

## MCP Server Setup

The Gmail Send MCP server exposes `send_email`, `draft_email`, and `list_drafts` tools to Claude Code.

Add to your Claude Code configuration (`~/.claude.json` or project `.mcp.json`):
```json
{
  "mcpServers": {
    "gmail-send": {
      "command": "py",
      "args": ["mcp_servers/gmail_send/server.py"],
      "env": {
        "VAULT_PATH": "D:/hackathon-0-PersonalAI-Employee/AI_Employee_Vault",
        "GMAIL_CREDENTIALS_PATH": "./credentials/gmail_credentials.json",
        "GMAIL_TOKEN_PATH": "./credentials/gmail_token.json"
      }
    }
  }
}
```

## Docker

### Build

```bash
docker build -t ai-employee-silver .
```

### Run

```bash
docker run -d \
  --name ai-employee \
  -v "$(pwd)/AI_Employee_Vault:/app/AI_Employee_Vault" \
  -v "$(pwd)/credentials:/app/credentials" \
  -e GMAIL_CREDENTIALS_PATH=/app/credentials/gmail_credentials.json \
  -e GMAIL_TOKEN_PATH=/app/credentials/gmail_token.json \
  -e LINKEDIN_EMAIL=your@email.com \
  -e LINKEDIN_PASSWORD=yourpassword \
  ai-employee-silver
```

### View logs

```bash
docker logs -f ai-employee
```

## Available Claude Code Skills

| Skill | Description |
|-------|-------------|
| `/process-inbox` | Process pending items in `/Needs_Action` |
| `/update-dashboard` | Refresh `Dashboard.md` with current vault status |
| `/vault-manager` | Manage vault files, create plans, check approvals, archive items |
| `/gmail-checker` | Manually trigger Gmail check and process email action files |
| `/linkedin-poster` | Draft a LinkedIn post and route through HITL approval |
| `/create-plan` | Create a structured Plan.md using the reasoning loop |

## HITL Workflow

```
AI drafts action
      ↓
Creates file in /Pending_Approval/
      ↓
Human reviews in Obsidian
      ↓
Move to /Approved  ──→  Orchestrator executes
Move to /Rejected  ──→  Archived to /Done
```

## Hackathon Tier

**Tier: Silver** — Panaversity Hackathon 0

| Requirement | Status |
|-------------|--------|
| Obsidian vault with `Dashboard.md` & `Company_Handbook.md` | ✅ |
| Two+ working Watcher scripts (File System + Gmail) | ✅ |
| LinkedIn auto-posting via Playwright | ✅ |
| Claude Code reading from & writing to the vault | ✅ |
| Basic folder structure `/Inbox`, `/Needs_Action`, `/Done` | ✅ |
| All AI functionality implemented as Agent Skills | ✅ |
| Plan.md reasoning loop (`/create-plan` skill) | ✅ |
| One working MCP server (Gmail Send) | ✅ |
| Human-in-the-loop approval workflow | ✅ |
| Basic scheduling via APScheduler orchestrator | ✅ |
| Public GitHub repository with README | ✅ |
| Docker image & container | ✅ |

## Security

Credentials are **never** stored in the vault or committed to version control.

- All secrets (API keys, tokens) are loaded via **environment variables** from a `.env` file
- `.env` is listed in `.gitignore` — see `.env.example` for the required variables
- The `credentials/` directory is listed in `.gitignore` — mount as a Docker volume
- All AI actions are logged with timestamp, actor, and result in `Logs/YYYY-MM-DD.json`
- Sensitive actions (emails, LinkedIn posts, payments) require human approval first

## License

MIT
