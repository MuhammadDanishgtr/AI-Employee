"""Gmail Send MCP Server — Exposes Gmail send/draft tools to Claude Code.

Tools exposed via MCP:
  send_email(to, subject, body, cc?)   — HITL: creates approval file, sends after approval
  draft_email(to, subject, body, cc?)  — Creates a Gmail draft without sending
  list_drafts()                        — Lists pending Gmail drafts

All actual sends require a matching approval file in /Approved.
Drafts are created immediately and shown in Gmail's Drafts folder.

Setup:
    pip install mcp google-auth google-auth-oauthlib google-api-python-client python-dotenv
    py mcp_servers/gmail_send/server.py

Configure in Claude Code (~/.claude.json or project .mcp.json):
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

Environment variables:
    VAULT_PATH                  Path to Obsidian vault (for approval files)
    GMAIL_CREDENTIALS_PATH      Gmail OAuth2 client credentials JSON
    GMAIL_TOKEN_PATH            Path to saved OAuth2 token
"""

import base64
import json
import logging
import os
import sys
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("GmailSendMCP")

# Gmail API scopes for sending
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
]

VAULT_PATH = Path(os.getenv("VAULT_PATH", "D:/hackathon-0-PersonalAI-Employee/AI_Employee_Vault"))
CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "./credentials/gmail_credentials.json")
TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "./credentials/gmail_token.json")


def _get_gmail_service():
    """Build authenticated Gmail service."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Gmail dependencies missing: pip install google-auth google-auth-oauthlib google-api-python-client") from exc

    creds = None
    token_file = Path(TOKEN_PATH)

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)


def _log_action(action_type: str, details: str, result: str = "success"):
    """Append a JSON log entry to today's log file."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = VAULT_PATH / "Logs" / f"{today}.json"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "actor": "GmailSendMCP",
        "details": details,
        "result": result,
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _create_approval_request(to: str, subject: str, body: str, cc: str = "") -> str:
    """Create an approval file in /Pending_Approval and return the file path."""
    pending_dir = VAULT_PATH / "Pending_Approval"
    pending_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc)
    file_id = f"EMAIL_SEND_{timestamp.strftime('%Y%m%d_%H%M%S')}"
    approval_path = pending_dir / f"{file_id}.md"

    safe_to = to.replace('"', "'")
    safe_subject = subject.replace('"', "'")
    safe_cc = cc.replace('"', "'")
    cc_line = f'cc: "{safe_cc}"' if cc else ""

    content = f"""---
type: email_send
action: send_email
to: "{safe_to}"
subject: "{safe_subject}"
{cc_line}
created: {timestamp.isoformat()}
expires: {timestamp.replace(hour=23, minute=59).isoformat()}
status: pending
---

## Email to Send

**To:** {to}
**Subject:** {subject}
{"**CC:** " + cc if cc else ""}

## Body

{body}

---

## To Approve
Move this file to the `/Approved` folder. The orchestrator will send the email.

## To Reject
Move this file to the `/Rejected` folder.
"""
    approval_path.write_text(content, encoding="utf-8")
    _log_action("approval_created", f"Email approval request: {file_id}")
    return str(approval_path)


def _draft_email_gmail(to: str, subject: str, body: str, cc: str = "") -> str:
    """Create a Gmail draft. Returns the draft ID."""
    svc = _get_gmail_service()
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    if cc:
        msg["cc"] = cc

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    draft = svc.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    draft_id = draft.get("id", "unknown")
    _log_action("email_drafted", f"Draft created: {draft_id} to {to}")
    return draft_id


def _list_drafts_gmail() -> list[dict]:
    """List pending Gmail drafts (up to 10)."""
    svc = _get_gmail_service()
    result = svc.users().drafts().list(userId="me", maxResults=10).execute()
    drafts = result.get("drafts", [])
    output = []
    for d in drafts:
        draft_detail = svc.users().drafts().get(userId="me", id=d["id"]).execute()
        headers = {
            h["name"]: h["value"]
            for h in draft_detail.get("message", {}).get("payload", {}).get("headers", [])
        }
        output.append({
            "id": d["id"],
            "to": headers.get("To", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
        })
    return output


# ─── MCP Server ────────────────────────────────────────────────────────────────

try:
    import mcp.server.stdio
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    import asyncio

    app = Server("gmail-send")

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="send_email",
                description=(
                    "Queue an email for sending via Gmail. "
                    "Creates a HITL approval file in /Pending_Approval — "
                    "a human must move it to /Approved before the email is sent. "
                    "Use this for any outbound email."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Recipient email address"},
                        "subject": {"type": "string", "description": "Email subject line"},
                        "body": {"type": "string", "description": "Email body (plain text)"},
                        "cc": {"type": "string", "description": "CC email address (optional)", "default": ""},
                    },
                    "required": ["to", "subject", "body"],
                },
            ),
            Tool(
                name="draft_email",
                description=(
                    "Create a Gmail draft without sending. "
                    "The draft appears in the Gmail Drafts folder for human review. "
                    "Safe to call without approval."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Recipient email address"},
                        "subject": {"type": "string", "description": "Email subject line"},
                        "body": {"type": "string", "description": "Email body (plain text)"},
                        "cc": {"type": "string", "description": "CC email address (optional)", "default": ""},
                    },
                    "required": ["to", "subject", "body"],
                },
            ),
            Tool(
                name="list_drafts",
                description="List the 10 most recent Gmail drafts.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "send_email":
            approval_path = _create_approval_request(
                to=arguments["to"],
                subject=arguments["subject"],
                body=arguments["body"],
                cc=arguments.get("cc", ""),
            )
            return [TextContent(
                type="text",
                text=(
                    f"Approval request created: {Path(approval_path).name}\n\n"
                    f"Move the file to /Approved to send the email, or /Rejected to cancel.\n"
                    f"Path: {approval_path}"
                ),
            )]

        elif name == "draft_email":
            draft_id = _draft_email_gmail(
                to=arguments["to"],
                subject=arguments["subject"],
                body=arguments["body"],
                cc=arguments.get("cc", ""),
            )
            return [TextContent(
                type="text",
                text=f"Gmail draft created successfully.\nDraft ID: {draft_id}\nCheck Gmail Drafts folder.",
            )]

        elif name == "list_drafts":
            drafts = _list_drafts_gmail()
            if not drafts:
                return [TextContent(type="text", text="No drafts found.")]
            lines = [f"Found {len(drafts)} draft(s):"]
            for d in drafts:
                lines.append(f"  • [{d['id']}] To: {d['to']} | Subject: {d['subject']}")
            return [TextContent(type="text", text="\n".join(lines))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    async def _main():
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())

    if __name__ == "__main__":
        logging.basicConfig(level=logging.INFO)
        asyncio.run(_main())

except ImportError:
    # MCP not installed — print helpful message
    if __name__ == "__main__":
        print("MCP package not installed. Run: pip install mcp")
        print("Then restart: py mcp_servers/gmail_send/server.py")
        sys.exit(1)
