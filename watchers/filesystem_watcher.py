"""File System Watcher — Monitors a Drop Folder for new files.

When files are dropped into the Drop_Folder, this watcher:
1. Detects the new file via watchdog
2. Copies it to /Needs_Action with a metadata .md file
3. Logs the action for audit

Usage:
    py watchers/filesystem_watcher.py
    py watchers/filesystem_watcher.py --vault D:/path/to/vault --drop D:/path/to/drop
"""

import argparse
import logging
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add parent to path for base_watcher import
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher


class DropFolderHandler(FileSystemEventHandler):
    """Watchdog event handler — reacts to new files in the Drop Folder."""

    def __init__(self, watcher: "FileSystemWatcher"):
        super().__init__()
        self.watcher = watcher
        self.logger = logging.getLogger("DropFolderHandler")

    def on_created(self, event):
        if event.is_directory:
            return

        source = Path(event.src_path)

        # Ignore hidden files and .gitkeep
        if source.name.startswith("."):
            return

        self.logger.info(f"New file detected: {source.name}")
        self.watcher.pending_files.append(source)


class FileSystemWatcher(BaseWatcher):
    """Watches a Drop Folder and creates action files in Needs_Action."""

    def __init__(self, vault_path: str, drop_folder: str, check_interval: int = 10):
        super().__init__(vault_path, check_interval)
        self.drop_folder = Path(drop_folder)
        self.drop_folder.mkdir(parents=True, exist_ok=True)
        self.pending_files: list[Path] = []
        self.processed_files: set[str] = set()

        # Set up watchdog observer
        self.handler = DropFolderHandler(self)
        self.observer = Observer()
        self.observer.schedule(self.handler, str(self.drop_folder), recursive=False)

    def check_for_updates(self) -> list:
        """Return list of new files from the pending queue."""
        new_items = []
        while self.pending_files:
            filepath = self.pending_files.pop(0)
            if filepath.name not in self.processed_files and filepath.exists():
                new_items.append(filepath)
        return new_items

    def create_action_file(self, item: Path) -> Path:
        """Copy file to Needs_Action and create a metadata .md file."""
        timestamp = datetime.now(timezone.utc)
        safe_name = item.stem.replace(" ", "_")
        file_id = f"FILE_{safe_name}_{timestamp.strftime('%Y%m%d_%H%M%S')}"

        # Copy the original file
        dest_file = self.needs_action / f"{file_id}{item.suffix}"
        shutil.copy2(item, dest_file)

        # Determine file type category
        ext = item.suffix.lower()
        type_map = {
            ".pdf": "document",
            ".doc": "document",
            ".docx": "document",
            ".txt": "text",
            ".md": "markdown",
            ".csv": "data",
            ".xlsx": "spreadsheet",
            ".xls": "spreadsheet",
            ".jpg": "image",
            ".jpeg": "image",
            ".png": "image",
            ".gif": "image",
        }
        file_type = type_map.get(ext, "file")

        # Create metadata markdown file
        meta_content = f"""---
type: file_drop
source: drop_folder
original_name: "{item.name}"
file_type: {file_type}
size_bytes: {item.stat().st_size}
received: {timestamp.isoformat()}
priority: medium
status: pending
---

## Dropped File

**File:** `{item.name}`
**Type:** {file_type} ({ext})
**Size:** {self._human_size(item.stat().st_size)}
**Received:** {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

## Suggested Actions
- [ ] Review file contents
- [ ] Categorize and file appropriately
- [ ] Process any actionable items
- [ ] Move to /Done when complete
"""
        meta_path = self.needs_action / f"{file_id}.md"
        meta_path.write_text(meta_content, encoding="utf-8")

        self.processed_files.add(item.name)
        self.logger.info(f"Action file created: {meta_path.name}")
        return meta_path

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        """Convert bytes to human-readable size."""
        for unit in ("B", "KB", "MB", "GB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def run(self):
        """Start the watchdog observer and main loop."""
        self.observer.start()
        self.logger.info(f"Watching Drop Folder: {self.drop_folder}")
        self.log_action("watcher_start", f"Monitoring {self.drop_folder}")

        print(f"\n--- File System Watcher Active ---")
        print(f"  Vault:       {self.vault_path}")
        print(f"  Drop Folder: {self.drop_folder}")
        print(f"  Output:      {self.needs_action}")
        print(f"  Interval:    {self.check_interval}s")
        print(f"  Press Ctrl+C to stop\n")

        try:
            while True:
                items = self.check_for_updates()
                for item in items:
                    filepath = self.create_action_file(item)
                    self.log_action("action_file_created", f"Created {filepath.name}")
                    print(f"  [+] Processed: {item.name} -> {filepath.name}")
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            print("\n--- Watcher stopped ---")
            self.log_action("watcher_stop", "Stopped by user")
        finally:
            self.observer.stop()
            self.observer.join()


def main():
    parser = argparse.ArgumentParser(description="AI Employee File System Watcher")
    parser.add_argument(
        "--vault",
        default="D:/hackathon-0-PersonalAI-Employee/AI_Employee_Vault",
        help="Path to Obsidian vault",
    )
    parser.add_argument(
        "--drop",
        default=None,
        help="Path to Drop Folder (defaults to vault/Drop_Folder)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Check interval in seconds (default: 10)",
    )
    args = parser.parse_args()

    drop_folder = args.drop or str(Path(args.vault) / "Drop_Folder")

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    watcher = FileSystemWatcher(
        vault_path=args.vault,
        drop_folder=drop_folder,
        check_interval=args.interval,
    )
    watcher.run()


if __name__ == "__main__":
    main()
