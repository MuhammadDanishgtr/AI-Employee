"""Orchestrator — Master process that coordinates all AI Employee watchers.

Uses APScheduler to run all watchers on configurable schedules:
  - FileSystem Watcher: continuous (watchdog-based, always running)
  - Gmail Watcher:      every 2 minutes (polls Gmail API)
  - LinkedIn Poster:    every 15 minutes (checks /Approved for posts)
  - Dashboard Update:   every 10 minutes (refreshes Dashboard.md)

Health monitoring restarts crashed watcher threads automatically.

Usage:
    py watchers/orchestrator.py
    py watchers/orchestrator.py --vault D:/path/to/vault

Environment variables (from .env):
    VAULT_PATH                  Path to Obsidian vault
    DROP_FOLDER_PATH            Drop folder for filesystem watcher
    GMAIL_CREDENTIALS_PATH      Gmail OAuth2 credentials
    GMAIL_TOKEN_PATH            Gmail OAuth2 token
    LINKEDIN_SESSION_PATH       Playwright session directory
    SCHEDULE_GMAIL_INTERVAL     Gmail poll interval in seconds (default 120)
    SCHEDULE_LINKEDIN_INTERVAL  LinkedIn check interval in seconds (default 900)
    SCHEDULE_DASHBOARD_INTERVAL Dashboard refresh interval in seconds (default 600)
"""

import argparse
import json
import logging
import os
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Add watchers dir to path
sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger("Orchestrator")


def _log_action(vault_path: Path, action_type: str, details: str, result: str = "success"):
    """Write an audit log entry."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = vault_path / "Logs" / f"{today}.json"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "actor": "Orchestrator",
        "details": details,
        "result": result,
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _update_dashboard(vault_path: Path):
    """Refresh Dashboard.md with current folder counts and recent logs."""
    def count_items(folder: Path) -> int:
        if not folder.exists():
            return 0
        return sum(1 for f in folder.iterdir() if not f.name.startswith("."))

    folders = {
        "Inbox": vault_path / "Inbox",
        "Needs_Action": vault_path / "Needs_Action",
        "Pending_Approval": vault_path / "Pending_Approval",
        "Approved": vault_path / "Approved",
        "Plans": vault_path / "Plans",
        "Done": vault_path / "Done",
    }
    counts = {name: count_items(path) for name, path in folders.items()}

    # Read last 5 log entries
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = vault_path / "Logs" / f"{today}.json"
    recent_entries = []
    if log_file.exists():
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        for line in lines[-5:]:
            try:
                entry = json.loads(line)
                recent_entries.append(entry)
            except json.JSONDecodeError:
                pass

    now = datetime.now(timezone.utc)
    recent_rows = "\n".join(
        f"| {e.get('timestamp','')[:19]} | {e.get('action_type','')} | {e.get('details','')} | {e.get('result','')} |"
        for e in recent_entries
    ) or "| — | No activity yet | — | — |"

    dashboard_content = f"""---
title: AI Employee Dashboard
last_updated: {now.isoformat()}
version: "0.2"
tier: Silver
---

# AI Employee Dashboard

## System Status
| Component          | Status  | Last Check              |
|--------------------|---------|-------------------------|
| Orchestrator       | Active  | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| File Watcher       | Active  | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| Gmail Watcher      | Active  | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| LinkedIn Poster    | Active  | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| Vault Connection   | Active  | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| AI Engine          | Ready   | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |

## Folder Summary
| Folder            | Count |
|-------------------|-------|
| Inbox             | {counts['Inbox']}     |
| Needs_Action      | {counts['Needs_Action']}     |
| Pending_Approval  | {counts['Pending_Approval']}     |
| Approved          | {counts['Approved']}     |
| Plans             | {counts['Plans']}     |
| Done              | {counts['Done']}     |

## Recent Activity
| Timestamp           | Action | Details | Status |
|---------------------|--------|---------|--------|
{recent_rows}

## Quick Links
- [[Company_Handbook]] — Rules of engagement
- [[Plans/]] — Active plans

---
*Updated by AI Employee v0.2 — Silver Tier*
"""
    dashboard_path = vault_path / "Dashboard.md"
    dashboard_path.write_text(dashboard_content, encoding="utf-8")
    logger.info("Dashboard updated")
    _log_action(vault_path, "dashboard_update", "Dashboard.md refreshed")


class WatcherThread(threading.Thread):
    """Wraps a watcher's run() in a daemon thread with restart capability."""

    def __init__(self, name: str, target_fn, args=(), kwargs=None):
        super().__init__(name=name, daemon=True)
        self.target_fn = target_fn
        self.args = args
        self.kwargs = kwargs or {}
        self._exception: Exception | None = None

    def run(self):
        try:
            self.target_fn(*self.args, **self.kwargs)
        except Exception as exc:
            self._exception = exc
            logger.error(f"Thread {self.name} crashed: {exc}")

    @property
    def crashed(self) -> bool:
        return self._exception is not None


def _start_filesystem_watcher(vault_path: str, drop_folder: str, interval: int):
    """Start the filesystem watcher (blocking)."""
    from filesystem_watcher import FileSystemWatcher
    watcher = FileSystemWatcher(
        vault_path=vault_path,
        drop_folder=drop_folder,
        check_interval=interval,
    )
    watcher.run()


def _run_gmail_watcher_once(vault_path: str, credentials_path: str, token_path: str):
    """Run one Gmail check cycle (called by scheduler)."""
    try:
        from gmail_watcher import GmailWatcher
        watcher = GmailWatcher(
            vault_path=vault_path,
            credentials_path=credentials_path,
            token_path=token_path,
            check_interval=999999,  # won't loop
        )
        items = watcher.check_for_updates()
        for item in items:
            watcher.create_action_file(item)
        logger.info(f"Gmail check: {len(items)} new email(s)")
    except Exception as exc:
        logger.error(f"Gmail watcher error: {exc}")


def _run_linkedin_check_once(vault_path: str, session_path: str):
    """Run one LinkedIn posting cycle (called by scheduler)."""
    try:
        from linkedin_watcher import LinkedInPoster
        poster = LinkedInPoster(
            vault_path=vault_path,
            session_path=session_path,
            linkedin_email=os.getenv("LINKEDIN_EMAIL", ""),
            linkedin_password=os.getenv("LINKEDIN_PASSWORD", ""),
        )
        items = poster.check_for_updates()
        for item in items:
            poster.create_action_file(item)
        if items:
            logger.info(f"LinkedIn check: processed {len(items)} post(s)")
    except Exception as exc:
        logger.error(f"LinkedIn poster error: {exc}")


def main():
    parser = argparse.ArgumentParser(description="AI Employee Orchestrator")
    parser.add_argument(
        "--vault",
        default=os.getenv("VAULT_PATH", "D:/hackathon-0-PersonalAI-Employee/AI_Employee_Vault"),
        help="Path to Obsidian vault",
    )
    parser.add_argument(
        "--drop",
        default=os.getenv("DROP_FOLDER_PATH", None),
        help="Drop folder path (defaults to vault/Drop_Folder)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    vault_path = Path(args.vault)
    drop_folder = args.drop or str(vault_path / "Drop_Folder")

    credentials_path = os.getenv("GMAIL_CREDENTIALS_PATH", "./credentials/gmail_credentials.json")
    token_path = os.getenv("GMAIL_TOKEN_PATH", "./credentials/gmail_token.json")
    session_path = os.getenv("LINKEDIN_SESSION_PATH", "./credentials/linkedin_session")

    gmail_interval = int(os.getenv("SCHEDULE_GMAIL_INTERVAL", "120"))
    linkedin_interval = int(os.getenv("SCHEDULE_LINKEDIN_INTERVAL", "900"))
    dashboard_interval = int(os.getenv("SCHEDULE_DASHBOARD_INTERVAL", "600"))

    print(f"\n{'='*50}")
    print(f"  AI Employee Orchestrator — Silver Tier")
    print(f"{'='*50}")
    print(f"  Vault:      {vault_path}")
    print(f"  Drop:       {drop_folder}")
    print(f"  Gmail:      every {gmail_interval}s")
    print(f"  LinkedIn:   every {linkedin_interval}s")
    print(f"  Dashboard:  every {dashboard_interval}s")
    print(f"{'='*50}\n")

    _log_action(vault_path, "orchestrator_start", "Silver Tier orchestrator started")

    # Import APScheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.error("APScheduler not installed. Run: pip install apscheduler")
        sys.exit(1)

    scheduler = BackgroundScheduler()

    # Schedule Gmail watcher
    scheduler.add_job(
        _run_gmail_watcher_once,
        "interval",
        seconds=gmail_interval,
        id="gmail_watcher",
        args=[str(vault_path), credentials_path, token_path],
        max_instances=1,
    )

    # Schedule LinkedIn poster
    scheduler.add_job(
        _run_linkedin_check_once,
        "interval",
        seconds=linkedin_interval,
        id="linkedin_poster",
        args=[str(vault_path), session_path],
        max_instances=1,
    )

    # Schedule dashboard update
    scheduler.add_job(
        _update_dashboard,
        "interval",
        seconds=dashboard_interval,
        id="dashboard_update",
        args=[vault_path],
        max_instances=1,
    )

    scheduler.start()
    logger.info("Scheduler started with Gmail, LinkedIn, and Dashboard jobs")

    # Start filesystem watcher in a background thread
    fs_thread = WatcherThread(
        name="FileSystemWatcher",
        target_fn=_start_filesystem_watcher,
        args=(str(vault_path), drop_folder, 10),
    )
    fs_thread.start()
    logger.info("FileSystem watcher thread started")

    # Initial dashboard update
    _update_dashboard(vault_path)

    # Health monitor loop
    try:
        while True:
            time.sleep(30)

            # Restart crashed filesystem watcher
            if not fs_thread.is_alive():
                logger.warning("FileSystem watcher thread died — restarting...")
                _log_action(vault_path, "watcher_restart", "FileSystemWatcher restarted", result="warning")
                fs_thread = WatcherThread(
                    name="FileSystemWatcher",
                    target_fn=_start_filesystem_watcher,
                    args=(str(vault_path), drop_folder, 10),
                )
                fs_thread.start()

    except KeyboardInterrupt:
        print("\n--- Orchestrator stopped ---")
        _log_action(vault_path, "orchestrator_stop", "Stopped by user")
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
