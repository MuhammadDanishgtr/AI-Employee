"""Gmail Watcher — Polls Gmail for unread important emails.

When important unread emails arrive, this watcher:
1. Fetches emails via Gmail API (is:unread is:important)
2. Creates EMAIL_<id>.md action files in /Needs_Action
3. Marks emails as read to avoid re-processing
4. Logs every action for audit

Usage:
    py watchers/gmail_watcher.py
    py watchers/gmail_watcher.py --vault D:/path/to/vault --interval 120

Environment variables (from .env):
    GMAIL_CREDENTIALS_PATH  Path to OAuth2 client credentials JSON
    GMAIL_TOKEN_PATH        Path to saved token (auto-created on first run)
    VAULT_PATH              Path to Obsidian vault
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Add parent to path for base_watcher import
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher

load_dotenv()

# Gmail API scopes — read + modify to mark emails read
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


def _get_gmail_service(credentials_path: str, token_path: str):
    """Build an authenticated Gmail API service object.

    On first run, launches an OAuth2 browser flow and saves the token.
    Subsequent runs load the saved token automatically.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Gmail dependencies missing. Run: pip install google-auth google-auth-oauthlib google-api-python-client"
        ) from exc

    creds = None
    token_file = Path(token_path)

    # Load existing token
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    # Refresh or obtain new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(credentials_path).exists():
                raise FileNotFoundError(
                    f"Gmail credentials file not found: {credentials_path}\n"
                    "Download it from Google Cloud Console → APIs & Services → Credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for next run
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)


class GmailWatcher(BaseWatcher):
    """Polls Gmail for unread important emails and creates action files."""

    def __init__(
        self,
        vault_path: str,
        credentials_path: str,
        token_path: str,
        check_interval: int = 120,
    ):
        super().__init__(vault_path, check_interval)
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.processed_ids: set[str] = set()
        self._service = None

    def _ensure_service(self):
        """Lazily build and cache the Gmail service."""
        if self._service is None:
            self._service = _get_gmail_service(self.credentials_path, self.token_path)
        return self._service

    def check_for_updates(self) -> list:
        """Fetch unread important emails from Gmail.

        Returns a list of message dicts with id, subject, sender, snippet, body.
        """
        svc = self._ensure_service()
        try:
            result = (
                svc.users()
                .messages()
                .list(userId="me", q="is:unread is:important", maxResults=20)
                .execute()
            )
        except Exception as exc:
            self.logger.error(f"Gmail API list failed: {exc}")
            return []

        messages = result.get("messages", [])
        new_emails = []

        for msg_stub in messages:
            msg_id = msg_stub["id"]
            if msg_id in self.processed_ids:
                continue

            try:
                msg = (
                    svc.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full")
                    .execute()
                )
            except Exception as exc:
                self.logger.error(f"Failed to fetch message {msg_id}: {exc}")
                continue

            headers = {
                h["name"]: h["value"]
                for h in msg.get("payload", {}).get("headers", [])
            }

            email_data = {
                "id": msg_id,
                "subject": headers.get("Subject", "(no subject)"),
                "from": headers.get("From", "unknown"),
                "date": headers.get("Date", ""),
                "snippet": msg.get("snippet", ""),
                "thread_id": msg.get("threadId", ""),
            }
            new_emails.append(email_data)

        return new_emails

    def create_action_file(self, item: dict) -> Path:
        """Create an EMAIL_<id>.md action file in /Needs_Action."""
        timestamp = datetime.now(timezone.utc)
        safe_id = item["id"][:16]
        file_id = f"EMAIL_{safe_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"

        safe_subject = item["subject"].replace('"', "'")
        safe_from = item["from"].replace('"', "'")

        content = f"""---
type: email
source: gmail
email_id: "{safe_id}"
subject: "{safe_subject}"
from: "{safe_from}"
date: "{item['date']}"
thread_id: "{item['thread_id']}"
received: {timestamp.isoformat()}
priority: high
status: pending
---

## Incoming Email

**From:** {item['from']}
**Subject:** {item['subject']}
**Date:** {item['date']}

## Preview

{item['snippet']}

## Suggested Actions
- [ ] Read full email thread
- [ ] Determine if reply is needed
- [ ] Draft reply or escalate for human review
- [ ] Move to /Done when complete

## To Reply
Create a reply draft and place in /Pending_Approval/ for human review.
"""
        meta_path = self.needs_action / f"{file_id}.md"
        meta_path.write_text(content, encoding="utf-8")

        # Mark email as read to prevent duplicate processing
        self._mark_as_read(item["id"])

        self.processed_ids.add(item["id"])
        self.logger.info(f"Email action file created: {meta_path.name}")
        return meta_path

    def _mark_as_read(self, msg_id: str):
        """Remove UNREAD label from a Gmail message."""
        try:
            svc = self._ensure_service()
            svc.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()
        except Exception as exc:
            self.logger.warning(f"Could not mark message {msg_id} as read: {exc}")

    def run(self):
        """Override base run() to print a banner."""
        self.log_action("watcher_start", f"GmailWatcher started (interval: {self.check_interval}s)")

        print(f"\n--- Gmail Watcher Active ---")
        print(f"  Vault:       {self.vault_path}")
        print(f"  Output:      {self.needs_action}")
        print(f"  Interval:    {self.check_interval}s")
        print(f"  Query:       is:unread is:important")
        print(f"  Press Ctrl+C to stop\n")

        super().run()


def main():
    parser = argparse.ArgumentParser(description="AI Employee Gmail Watcher")
    parser.add_argument(
        "--vault",
        default=os.getenv("VAULT_PATH", "D:/hackathon-0-PersonalAI-Employee/AI_Employee_Vault"),
        help="Path to Obsidian vault",
    )
    parser.add_argument(
        "--credentials",
        default=os.getenv("GMAIL_CREDENTIALS_PATH", "./credentials/gmail_credentials.json"),
        help="Path to Gmail OAuth2 credentials JSON",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GMAIL_TOKEN_PATH", "./credentials/gmail_token.json"),
        help="Path to saved OAuth2 token",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("SCHEDULE_GMAIL_INTERVAL", "120")),
        help="Poll interval in seconds (default: 120)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    watcher = GmailWatcher(
        vault_path=args.vault,
        credentials_path=args.credentials,
        token_path=args.token,
        check_interval=args.interval,
    )
    watcher.run()


if __name__ == "__main__":
    main()
