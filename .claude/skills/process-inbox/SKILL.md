---
name: process-inbox
description: |
  Process pending items in the AI Employee vault's /Needs_Action folder.
  Reads each action file, determines what needs to be done, executes safe actions,
  creates approval requests for sensitive ones, and moves completed items to /Done.
  Use when there are new items to process or when asked to check pending work.
invocation: user
---

# Process Inbox Skill

Process all pending items in the AI Employee vault's `/Needs_Action` folder.

## Vault Location

The vault is at: `D:/hackathon-0-PersonalAI-Employee/AI_Employee_Vault`

## Workflow

### Step 1: Read Company Handbook
Before processing any items, read the rules:
```
Read file: AI_Employee_Vault/Company_Handbook.md
```
Follow all permission boundaries and priority levels defined there.

### Step 2: Scan Needs_Action Folder
List all `.md` files in `/Needs_Action` (ignore `.gitkeep`):
```
Glob pattern: AI_Employee_Vault/Needs_Action/*.md
```

### Step 3: Process Each Item
For each `.md` file found:

1. **Read the file** — parse the YAML frontmatter for `type`, `priority`, `status`
2. **Determine the action** based on `type`:
   - `file_drop` → Review the associated file, summarize contents, suggest next steps
   - `email` → Draft a reply or flag for human review
   - `task` → Break down into steps and create a plan
3. **Check permission boundaries** (from Company_Handbook.md):
   - If action is within auto-approve thresholds → Execute it
   - If action requires approval → Create an approval file in `/Pending_Approval/`
4. **Log the action** — append to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`

### Step 4: Move Completed Items
After processing, move the `.md` file and any associated files to `/Done/`:
```bash
# Move processed files (use Bash tool)
mv "AI_Employee_Vault/Needs_Action/FILE_xxx.md" "AI_Employee_Vault/Done/"
mv "AI_Employee_Vault/Needs_Action/FILE_xxx.txt" "AI_Employee_Vault/Done/"
```

### Step 5: Update Dashboard
After processing all items, invoke the `update-dashboard` skill to refresh the dashboard:
```
/update-dashboard
```

## Approval Request Format

When an action requires human approval, create a file in `/Pending_Approval/`:

```markdown
---
type: approval_request
action: [describe action]
created: [ISO timestamp]
expires: [24 hours from now]
status: pending
source_file: [original file name]
---

## Action Details
[What will be done]

## To Approve
Move this file to the `/Approved` folder.

## To Reject
Move this file to the `/Rejected` folder.
```

## Output
After processing, report:
- Number of items processed
- Actions taken
- Items requiring approval
- Any errors encountered
