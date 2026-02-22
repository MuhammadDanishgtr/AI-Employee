---
name: linkedin-poster
description: |
  Create a LinkedIn post draft for the AI Employee to publish.
  User provides a topic or content idea; Claude drafts the post and saves it
  to /Pending_Approval. When moved to /Approved, the orchestrator posts
  it to LinkedIn automatically via Playwright.
  Use when asked to write or schedule a LinkedIn post.
invocation: user
---

# LinkedIn Poster Skill

Draft a LinkedIn post and route it through the HITL approval workflow.

## Vault Location

The vault is at: `D:/hackathon-0-PersonalAI-Employee/AI_Employee_Vault`

## Workflow

### Step 1: Gather Post Details
Ask the user (or use context provided) for:
- **Topic / Idea:** What should the post be about?
- **Tone:** Professional / Casual / Educational / Inspirational
- **Target audience:** Who will read this?
- **Call to action:** Should the post ask readers to do anything?

### Step 2: Draft the LinkedIn Post
Write a high-quality LinkedIn post following these guidelines:
- **Length:** 150–300 words (optimal engagement range)
- **Structure:** Hook → Value → CTA
  - Open with a compelling first line (no "I'm excited to share…")
  - Deliver the core insight or story
  - End with a question or call to action
- **Formatting:** Use line breaks generously (LinkedIn rewards visual whitespace)
- **Hashtags:** Include 3–5 relevant hashtags at the end

Example structure:
```
[Strong opening line that stops the scroll]

[2-3 short paragraphs with the core content]

[Closing question or call to action]

#Hashtag1 #Hashtag2 #Hashtag3
```

### Step 3: Save to Pending_Approval
Create a LinkedIn post approval file:

```markdown
# AI_Employee_Vault/Pending_Approval/LINKEDIN_<YYYYMMDD>_<topic>.md
---
type: linkedin_post
status: pending
created: [ISO timestamp]
topic: "[post topic]"
author: "AI Employee"
---

## Post Content

[The full drafted LinkedIn post goes here]

---

## Instructions
- **To approve:** Move this file to `/Approved/`
- **To reject:** Move this file to `/Rejected/`
- **To edit:** Edit the "Post Content" section, then move to `/Approved/`

Once in `/Approved`, the orchestrator will automatically post to LinkedIn
via Playwright within the next 15 minutes.
```

### Step 4: Log the Action
Append to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`:
```json
{"timestamp": "[ISO]", "action_type": "linkedin_draft_created", "actor": "claude_code", "details": "LinkedIn post drafted: [topic]", "result": "success"}
```

### Step 5: Report to User
Confirm:
- Post draft created at: `Pending_Approval/LINKEDIN_<date>_<topic>.md`
- Instructions on how to approve/edit/reject
- Expected posting time after approval (~15 min by orchestrator)

## Output
Show the user:
1. The draft post content (so they can review before approving)
2. The approval file path
3. Next steps to publish
