---
name: create-plan
description: |
  Create a structured Plan.md for any task using the AI Employee reasoning loop.
  Reads the task from /Needs_Action or from user input, decomposes it into
  steps with dependencies and approval requirements, saves to /Plans/,
  and logs the plan creation. Use for any complex task that needs structure.
invocation: user
---

# Create Plan Skill

Create a structured, actionable Plan.md for any task using the AI Employee's
Plan → Execute → Verify reasoning loop.

## Vault Location

The vault is at: `D:/hackathon-0-PersonalAI-Employee/AI_Employee_Vault`

## Reasoning Loop

This skill implements the core Silver Tier reasoning loop:

```
READ task → ANALYZE requirements → DECOMPOSE into steps →
IDENTIFY dependencies → FLAG approval gates → WRITE Plan.md →
LOG creation → RETURN to executor
```

## Workflow

### Step 1: Read Company Handbook
Always read permission rules before planning:
```
Read file: AI_Employee_Vault/Company_Handbook.md
```

### Step 2: Identify the Task
**Option A — From Needs_Action:**
```
Glob: AI_Employee_Vault/Needs_Action/*.md
```
Read the highest-priority item. Extract: objective, type, constraints.

**Option B — From user input:**
Use the task description provided by the user directly.

### Step 3: Decompose the Task
Break the task into concrete, executable steps:
- Each step should be a single atomic action
- Identify which steps need external resources (API calls, emails, etc.)
- Identify which steps require human approval (per Company Handbook)
- Identify dependencies between steps (what must complete before what)

### Step 4: Create the Plan File
Save to `/Plans/` using this format:

```markdown
# AI_Employee_Vault/Plans/PLAN_<description>_<YYYYMMDD>.md
---
type: plan
status: pending
created: [ISO timestamp]
task: "[brief task description]"
priority: [high/medium/low]
estimated_steps: [n]
requires_approval: [yes/no]
---

## Objective

[Clear statement of what needs to be accomplished and why]

## Context

[Relevant background information, constraints, and assumptions]

## Steps

- [ ] **Step 1:** [Action description]
  - *Owner:* AI Employee / Human
  - *Requires approval:* No
  - *Depends on:* —

- [ ] **Step 2:** [Action description]
  - *Owner:* AI Employee / Human
  - *Requires approval:* Yes — [reason]
  - *Depends on:* Step 1

- [ ] **Step 3:** [Action description]
  - *Owner:* AI Employee
  - *Requires approval:* No
  - *Depends on:* Step 2

## Dependencies

| Step | Depends On | Blocker? |
|------|-----------|---------|
| 2    | 1         | Yes     |
| 3    | 2         | Yes     |

## Approval Requirements

| Step | Approval Needed | Reason |
|------|----------------|--------|
| 2    | Human          | [reason per Company Handbook] |

## Success Criteria

- [ ] [Measurable outcome 1]
- [ ] [Measurable outcome 2]

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| [Risk 1] | Medium | [Mitigation] |

---
*Plan created by AI Employee v0.2 — Silver Tier*
*Created: [ISO timestamp]*
```

### Step 5: Create Approval Files (if needed)
For any step requiring human approval, create a corresponding approval file
in `/Pending_Approval/` before execution begins:

```markdown
# AI_Employee_Vault/Pending_Approval/APPROVE_<step>_<date>.md
---
type: approval_request
action: [step description]
plan_file: "[PLAN_*.md filename]"
step_number: [n]
created: [ISO timestamp]
status: pending
---

## Action to Approve

[Detailed description of what will be done]

## To Approve
Move this file to `/Approved`.

## To Reject
Move this file to `/Rejected`.
```

### Step 6: Log Plan Creation
Append to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`:
```json
{
  "timestamp": "[ISO]",
  "action_type": "plan_created",
  "actor": "claude_code",
  "details": "Plan created: PLAN_[description]_[date].md — [n] steps",
  "result": "success"
}
```

### Step 7: Update Dashboard
Run `/update-dashboard` to show the new plan in the dashboard.

## Output
Report:
- Plan file created at: `Plans/PLAN_<description>_<date>.md`
- Total number of steps
- Steps requiring human approval
- Estimated complexity
- Suggested next action (execute, await approval, etc.)
