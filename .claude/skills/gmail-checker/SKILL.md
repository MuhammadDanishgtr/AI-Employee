---
name: gmail-checker
description: |
  Manually trigger a Gmail inbox check for the AI Employee.
  Reads EMAIL_* action files from /Needs_Action, drafts replies for
  known contacts (auto-approve), creates approval requests for new contacts.
  Use when you want to process incoming emails or check for new messages.
invocation: user
---

# Gmail Checker Skill

Manually process incoming emails from the AI Employee vault's `/Needs_Action` folder.

## Vault Location

The vault is at: `D:/hackathon-0-PersonalAI-Employee/AI_Employee_Vault`

## Workflow

### Step 1: Read Company Handbook
Before processing any emails, read the permission rules:
```
Read file: AI_Employee_Vault/Company_Handbook.md
```
Note which contacts are trusted/known vs. new contacts.

### Step 2: Scan for Email Action Files
List all `EMAIL_*.md` files in `/Needs_Action`:
```
Glob pattern: AI_Employee_Vault/Needs_Action/EMAIL_*.md
```
If none are found, report "No new emails to process."

### Step 3: Process Each Email File
For each `EMAIL_*.md` file found:

1. **Read the file** — parse YAML frontmatter for `from`, `subject`, `status`, `email_id`
2. **Identify sender type:**
   - Known contact (in Company Handbook trusted list) → Draft auto-reply
   - New/unknown contact → Create approval request before replying
3. **Draft a reply** based on the email content:
   - Acknowledge receipt
   - Provide relevant information if available
   - Flag anything requiring human decision
4. **Check if reply should be auto-approved:**
   - Known contacts + routine responses → Create draft via `draft_email` MCP tool
   - New contacts or sensitive content → Create approval file in `/Pending_Approval/`

### Step 4: Create Reply Approval File (for new contacts)
When a reply needs human approval:

```markdown
# AI_Employee_Vault/Pending_Approval/REPLY_<email_id>_<date>.md
---
type: email_send
action: send_email
to: "[sender email]"
subject: "Re: [original subject]"
created: [ISO timestamp]
status: pending
source_email: "[EMAIL_*.md filename]"
---

## Proposed Reply

[Draft reply content]

## Context
[Why this email requires human approval]

## To Approve
Move this file to the `/Approved` folder.

## To Reject
Move this file to the `/Rejected` folder.
```

### Step 5: Move Processed Email Files
After processing, move to `/Done`:
```bash
mv "AI_Employee_Vault/Needs_Action/EMAIL_*.md" "AI_Employee_Vault/Done/"
```

### Step 6: Log the Actions
Append to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`:
```json
{"timestamp": "[ISO]", "action_type": "email_processed", "actor": "claude_code", "details": "[subject] from [sender]", "result": "success"}
```

### Step 7: Update Dashboard
Run `/update-dashboard` to refresh counts.

## Output
Report:
- Number of emails processed
- Replies drafted (auto-approved)
- Replies awaiting human approval
- Any emails flagged for attention
