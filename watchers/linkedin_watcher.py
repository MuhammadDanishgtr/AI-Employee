"""LinkedIn Watcher / Poster — Posts approved LinkedIn content via Playwright.

Workflow:
1. Scan /Approved for files with type: linkedin_post
2. For each approved post, launch a headless browser via Playwright
3. Log in to LinkedIn (or reuse saved session)
4. Publish the post content
5. Move approval file to /Done and log the action

This is NOT a polling watcher — it is triggered by the orchestrator
when items appear in /Approved.

Usage:
    py watchers/linkedin_watcher.py
    py watchers/linkedin_watcher.py --vault D:/path/to/vault --once

Environment variables (from .env):
    LINKEDIN_SESSION_PATH   Directory to save/load browser session state
    LINKEDIN_EMAIL          LinkedIn login email
    LINKEDIN_PASSWORD       LinkedIn login password
    VAULT_PATH              Path to Obsidian vault
"""

import argparse
import logging
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Add parent to path for base_watcher import
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher

load_dotenv()

logger = logging.getLogger("LinkedInWatcher")


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from a markdown file."""
    metadata = {}
    if not content.startswith("---"):
        return metadata
    parts = content.split("---", 2)
    if len(parts) < 3:
        return metadata
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata


def _extract_post_body(content: str) -> str:
    """Extract the post body section from an approved LinkedIn post file."""
    lines = content.splitlines()
    in_body = False
    body_lines = []
    for line in lines:
        if line.strip().lower() in ("## post content", "## content", "## post body"):
            in_body = True
            continue
        if in_body:
            if line.startswith("##"):
                break
            body_lines.append(line)
    return "\n".join(body_lines).strip()


class LinkedInPoster(BaseWatcher):
    """Reads approved LinkedIn posts from /Approved and publishes them via Playwright."""

    def __init__(
        self,
        vault_path: str,
        session_path: str,
        linkedin_email: str = "",
        linkedin_password: str = "",
        check_interval: int = 900,
    ):
        super().__init__(vault_path, check_interval)
        self.approved_dir = self.vault_path / "Approved"
        self.done_dir = self.vault_path / "Done"
        self.session_path = Path(session_path)
        self.linkedin_email = linkedin_email
        self.linkedin_password = linkedin_password

        self.approved_dir.mkdir(parents=True, exist_ok=True)
        self.done_dir.mkdir(parents=True, exist_ok=True)

    def check_for_updates(self) -> list:
        """Scan /Approved for pending linkedin_post files."""
        pending = []
        for md_file in sorted(self.approved_dir.glob("LINKEDIN_*.md")):
            if md_file.name == ".gitkeep":
                continue
            content = md_file.read_text(encoding="utf-8")
            meta = _parse_frontmatter(content)
            if meta.get("type") == "linkedin_post" and meta.get("status") != "posted":
                pending.append(md_file)
        return pending

    def create_action_file(self, item: Path) -> Path:
        """Post to LinkedIn and archive the approval file."""
        content = item.read_text(encoding="utf-8")
        post_body = _extract_post_body(content)

        if not post_body:
            self.logger.warning(f"No post body found in {item.name}, skipping.")
            self._archive(item, status="skipped_empty_body")
            return item

        success = self._post_to_linkedin(post_body, item.stem)

        if success:
            self._archive(item, status="posted")
            self.log_action("linkedin_post", f"Posted: {item.name}", result="success")
        else:
            self._archive(item, status="post_failed")
            self.log_action("linkedin_post", f"Failed: {item.name}", result="error")

        return item

    def _post_to_linkedin(self, post_text: str, post_id: str) -> bool:
        """Use Playwright to publish a post on LinkedIn."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )
            return False

        logger.info(f"Launching browser for LinkedIn post: {post_id}")

        with sync_playwright() as p:
            # Use persistent context to reuse session cookies
            self.session_path.mkdir(parents=True, exist_ok=True)
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(self.session_path),
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = context.new_page()

            try:
                # Navigate to LinkedIn feed
                page.goto("https://www.linkedin.com/feed/", timeout=30000)
                page.wait_for_load_state("networkidle", timeout=15000)

                # Check if we need to log in
                if "login" in page.url or "authwall" in page.url:
                    logger.info("Not logged in, attempting login...")
                    if not self._login(page):
                        logger.error("LinkedIn login failed")
                        context.close()
                        return False

                # Click "Start a post" button
                page.wait_for_selector(
                    'button[aria-label*="Start a post"], button.share-box-feed-entry__trigger',
                    timeout=10000,
                )
                page.click('button[aria-label*="Start a post"], button.share-box-feed-entry__trigger')
                page.wait_for_timeout(1500)

                # Find the post text editor and type content
                editor = page.wait_for_selector(
                    'div.ql-editor, div[contenteditable="true"][data-placeholder]',
                    timeout=10000,
                )
                editor.click()
                editor.type(post_text, delay=20)
                page.wait_for_timeout(1000)

                # Click the Post button
                post_button = page.wait_for_selector(
                    'button[aria-label="Post"], button.share-actions__primary-action',
                    timeout=10000,
                )
                post_button.click()
                page.wait_for_timeout(3000)

                logger.info(f"Successfully posted to LinkedIn: {post_id}")
                context.close()
                return True

            except Exception as exc:
                logger.error(f"Playwright error during LinkedIn post: {exc}")
                # Save a screenshot for debugging
                try:
                    screenshot_path = self.vault_path / "Logs" / f"linkedin_error_{post_id}.png"
                    page.screenshot(path=str(screenshot_path))
                    logger.info(f"Error screenshot saved: {screenshot_path}")
                except Exception:
                    pass
                context.close()
                return False

    def _login(self, page) -> bool:
        """Perform LinkedIn login with saved credentials."""
        if not self.linkedin_email or not self.linkedin_password:
            logger.error("LINKEDIN_EMAIL and LINKEDIN_PASSWORD env vars required for login")
            return False

        try:
            page.goto("https://www.linkedin.com/login", timeout=20000)
            page.wait_for_selector("#username", timeout=10000)
            page.fill("#username", self.linkedin_email)
            page.fill("#password", self.linkedin_password)
            page.click('button[type="submit"]')
            page.wait_for_url("**/feed/**", timeout=20000)
            logger.info("LinkedIn login successful")
            return True
        except Exception as exc:
            logger.error(f"Login failed: {exc}")
            return False

    def _archive(self, source: Path, status: str):
        """Move processed approval file to /Done with status suffix."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest_name = f"{source.stem}_{status}_{timestamp}.md"
        dest = self.done_dir / dest_name
        shutil.move(str(source), str(dest))
        logger.info(f"Archived {source.name} -> {dest.name}")

    def run(self):
        """Override base run() to print a banner."""
        self.log_action(
            "watcher_start",
            f"LinkedInPoster started (interval: {self.check_interval}s)",
        )

        print(f"\n--- LinkedIn Poster Active ---")
        print(f"  Vault:      {self.vault_path}")
        print(f"  Approved:   {self.approved_dir}")
        print(f"  Session:    {self.session_path}")
        print(f"  Interval:   {self.check_interval}s")
        print(f"  Press Ctrl+C to stop\n")

        super().run()


def main():
    parser = argparse.ArgumentParser(description="AI Employee LinkedIn Poster")
    parser.add_argument(
        "--vault",
        default=os.getenv("VAULT_PATH", "D:/hackathon-0-PersonalAI-Employee/AI_Employee_Vault"),
        help="Path to Obsidian vault",
    )
    parser.add_argument(
        "--session",
        default=os.getenv("LINKEDIN_SESSION_PATH", "./credentials/linkedin_session"),
        help="Directory for Playwright browser session state",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("SCHEDULE_LINKEDIN_INTERVAL", "900")),
        help="Check interval in seconds (default: 900)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process once and exit (no loop)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    poster = LinkedInPoster(
        vault_path=args.vault,
        session_path=args.session,
        linkedin_email=os.getenv("LINKEDIN_EMAIL", ""),
        linkedin_password=os.getenv("LINKEDIN_PASSWORD", ""),
        check_interval=args.interval,
    )

    if args.once:
        items = poster.check_for_updates()
        for item in items:
            poster.create_action_file(item)
        print(f"Processed {len(items)} LinkedIn post(s).")
    else:
        poster.run()


if __name__ == "__main__":
    main()
