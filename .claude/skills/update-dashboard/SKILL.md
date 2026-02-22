---
name: update-dashboard
description: |
  Update the AI Employee Dashboard.md with current vault status.
  Scans all vault folders, counts items, and refreshes the dashboard
  with pending items, recent activity, and folder summaries.
  Use after processing inbox items or when asked for a status update.
invocation: user
---

# Update Dashboard Skill

Refresh the `Dashboard.md` file in the AI Employee vault with current status.

## Vault Location

The vault is at: `D:/hackathon-0-PersonalAI-Employee/AI_Employee_Vault`

## Workflow

### Step 1: Scan All Folders
Count files in each vault folder (ignore `.gitkeep`):

```
Glob: AI_Employee_Vault/Inbox/*
Glob: AI_Employee_Vault/Needs_Action/*
Glob: AI_Employee_Vault/Pending_Approval/*
Glob: AI_Employee_Vault/Done/*
Glob: AI_Employee_Vault/Plans/*
```

### Step 2: Read Pending Items
For each file in `/Needs_Action`, read the YAML frontmatter to extract:
- File name
- Type
- Priority
- Received timestamp

### Step 3: Read Recent Logs
Read today's log file for recent activity:
```
Read: AI_Employee_Vault/Logs/YYYY-MM-DD.json
```
Extract the last 10 entries for the Recent Activity table.

### Step 4: Update Dashboard.md
Rewrite `AI_Employee_Vault/Dashboard.md` with the following structure:

```markdown
---
title: AI Employee Dashboard
last_updated: [current ISO timestamp]
version: "0.1"
---

# AI Employee Dashboard

## System Status
| Component        | Status   | Last Check            |
|------------------|----------|-----------------------|
| File Watcher     | [status] | [last check time]     |
| Vault Connection | Active   | [current time]        |
| AI Engine        | Ready    | [current time]        |

## Pending Items
| # | File | Type | Priority | Received |
|---|------|------|----------|----------|
[List each file from /Needs_Action]

## In Progress
| # | Task | Started | Owner |
|---|------|---------|-------|
[List items from /Plans with status: in_progress]

## Recent Activity
| Date | Action | Details | Status |
|------|--------|---------|--------|
[Last 10 log entries]

## Folder Summary
| Folder            | Count |
|-------------------|-------|
| Inbox             | [n]   |
| Needs_Action      | [n]   |
| Pending_Approval  | [n]   |
| Done              | [n]   |

## Quick Links
- [[Company_Handbook]] — Rules of engagement
- [[Business_Goals]] — Quarterly objectives and metrics

---
*Updated by AI Employee v0.1 — Bronze Tier*
```

### Step 5: Verify
Read back the updated Dashboard.md to confirm it was written correctly.

## Output
Report what was updated:
- Folder counts
- Number of pending items
- Number of recent activity entries
