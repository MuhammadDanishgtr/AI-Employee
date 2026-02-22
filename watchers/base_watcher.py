"""Base Watcher — Template for all AI Employee watchers.

All watchers inherit from this class and implement:
- check_for_updates(): Returns list of new items to process
- create_action_file(): Creates .md file in Needs_Action folder
"""

import time
import json
import logging
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime, timezone


class BaseWatcher(ABC):
    def __init__(self, vault_path: str, check_interval: int = 60):
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / "Needs_Action"
        self.logs_dir = self.vault_path / "Logs"
        self.check_interval = check_interval
        self.logger = logging.getLogger(self.__class__.__name__)

        # Ensure required directories exist
        self.needs_action.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def check_for_updates(self) -> list:
        """Return list of new items to process."""

    @abstractmethod
    def create_action_file(self, item) -> Path:
        """Create .md file in Needs_Action folder."""

    def log_action(self, action_type: str, details: str, result: str = "success"):
        """Write an audit log entry to the daily log file."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.logs_dir / f"{today}.json"

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type,
            "actor": self.__class__.__name__,
            "details": details,
            "result": result,
        }

        # Append to daily log (JSON lines format)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        self.logger.info(f"[{action_type}] {details} -> {result}")

    def run(self):
        """Main loop — poll for updates and create action files."""
        self.logger.info(f"Starting {self.__class__.__name__} (interval: {self.check_interval}s)")
        self.log_action("watcher_start", f"{self.__class__.__name__} started")

        while True:
            try:
                items = self.check_for_updates()
                for item in items:
                    filepath = self.create_action_file(item)
                    self.log_action(
                        "action_file_created",
                        f"Created {filepath.name}",
                    )
            except KeyboardInterrupt:
                self.logger.info("Watcher stopped by user")
                self.log_action("watcher_stop", "Stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in watcher loop: {e}")
                self.log_action("watcher_error", str(e), result="error")
            time.sleep(self.check_interval)
