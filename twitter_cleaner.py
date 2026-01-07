"""
Twitter Follower Cleanup - Main cleaner class.
Handles browser automation for removing bot followers.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Set
from dataclasses import asdict

from playwright.async_api import async_playwright, Page, Browser, BrowserContext, TimeoutError as PlaywrightTimeout

from config import BROWSER_CONFIG, DELAYS, LIMITS, SELECTORS, TEXT_PATTERNS, URLS
from utils import (
    FollowerInfo, CleanupReport, 
    is_bot_username, extract_username_from_text,
    save_report, save_backup, print_summary, format_progress, confirm_action
)


class TwitterCleaner:
    """
    Main class for cleaning bot followers from Twitter/X account.
    
    Usage:
        async with TwitterCleaner(user_id="samirmadhavan") as cleaner:
            await cleaner.run(dry_run=True, limit=50)
    """
    
    def __init__(
        self, 
        user_id: str,
        headless: bool = False,
        verbose: bool = False
    ):
        self.user_id = user_id
        self.headless_after_login = headless
        self.verbose = verbose
        
        self.logger = logging.getLogger('twitter_cleaner')
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Tracking
        self.scanned_usernames: Set[str] = set()
        self.followers: List[FollowerInfo] = []
        self.removed_count = 0
        self.failed_count = 0
        
        # Report
        self.report = CleanupReport(
            session_start=datetime.now().isoformat(),
            user_id=user_id
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
    
    async def initialize_browser(self):
        """Initialize Playwright browser with persistent context."""
        self.logger.info("Initializing browser...")
        
        self.playwright = await async_playwright().start()
        
        # Use persistent context to maintain login session
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=BROWSER_CONFIG["user_data_dir"],
            headless=False,  # Always start non-headless for login
            slow_mo=BROWSER_CONFIG["slow_mo"],
            viewport=BROWSER_CONFIG["viewport"],
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
            ]
        )
        
        # Get or create page
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()
        
        self.logger.info("Browser initialized successfully")
    
    async def cleanup(self):
        """Clean up browser resources."""
        self.logger.info("Cleaning up browser resources...")
        
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def wait_for_login(self) -> bool:
        """
        Navigate to Twitter and wait for user to log in manually.
        
        Returns:
            True if login detected, False otherwise
        """
        self.logger.info("Navigating to Twitter/X...")
        # Use domcontentloaded - networkidle is too strict for Twitter's constant activity
        try:
            await self.page.goto(URLS["base"], wait_until="domcontentloaded", timeout=60000)
        except PlaywrightTimeout:
            self.logger.warning("Initial page load slow, continuing anyway...")
        
        # Give page a moment to render
        await asyncio.sleep(3)
        
        # Check if already logged in
        if await self._is_logged_in():
            self.logger.info("✓ Already logged in!")
            return True
        
        # Prompt user to log in
        print("\n" + "=" * 60)
        print("  🔐 MANUAL LOGIN REQUIRED")
        print("=" * 60)
        print("\n  Please log in to your Twitter/X account in the browser.")
        print("  The script will continue automatically once login is detected.")
        print("\n" + "=" * 60 + "\n")
        
        # Wait for login with periodic checks
        max_wait_time = 300  # 5 minutes
        elapsed = 0
        
        while elapsed < max_wait_time:
            await asyncio.sleep(DELAYS["login_check_interval"])
            elapsed += DELAYS["login_check_interval"]
            
            if await self._is_logged_in():
                self.logger.info("✓ Login detected!")
                return True
            
            if elapsed % 30 == 0:
                self.logger.info(f"Still waiting for login... ({int(max_wait_time - elapsed)}s remaining)")
        
        self.logger.error("Login timeout - please try again")
        return False
    
    async def _is_logged_in(self) -> bool:
        """Check if user is currently logged in."""
        try:
            # Look for profile button in sidebar (indicates logged in)
            profile_btn = await self.page.query_selector(SELECTORS["profile_button"])
            if profile_btn:
                return True
            
            # Alternative: Check for home timeline
            timeline = await self.page.query_selector(SELECTORS["home_timeline"])
            if timeline:
                return True
            
            return False
        except Exception:
            return False
    
    async def navigate_to_followers(self) -> bool:
        """
        Navigate to the followers page for the specified user.
        
        Returns:
            True if navigation successful, False otherwise
        """
        url = URLS["followers_template"].format(user_id=self.user_id)
        self.logger.info(f"Navigating to followers page: {url}")
        
        for attempt in range(LIMITS["max_retry_attempts"]):
            try:
                # Use domcontentloaded - networkidle is too strict for Twitter
                await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(DELAYS["page_load"])
                
                # Check for error state and retry
                if await self._handle_page_error():
                    self.logger.info("Handled page error, waiting for content...")
                    await asyncio.sleep(3)
                
                # Wait for follower cells to appear
                await self.page.wait_for_selector(
                    SELECTORS["follower_cell"], 
                    timeout=15000
                )
                
                self.logger.info("✓ Followers page loaded successfully")
                return True
                
            except PlaywrightTimeout:
                self.logger.warning(f"Timeout loading followers (attempt {attempt + 1})")
                if attempt < LIMITS["max_retry_attempts"] - 1:
                    await self._handle_page_error()
                    await asyncio.sleep(2)
            except Exception as e:
                self.logger.error(f"Failed to navigate to followers: {e}")
                if attempt < LIMITS["max_retry_attempts"] - 1:
                    await asyncio.sleep(2)
        
        self.logger.error("Failed to load followers page after retries")
        return False
    
    async def _handle_page_error(self) -> bool:
        """
        Check for and handle Twitter page errors like 'Something went wrong'.
        
        Returns:
            True if error was found and retry clicked, False otherwise
        """
        try:
            # Look for retry button
            retry_btn = await self.page.query_selector('button:has-text("Retry")')
            if retry_btn:
                self.logger.info("Found 'Retry' button - clicking...")
                await retry_btn.click()
                await asyncio.sleep(3)
                return True
            
            # Alternative: look for error text
            error_text = await self.page.query_selector('text="Something went wrong"')
            if error_text:
                # Try to find and click any retry-like button
                retry = await self.page.query_selector('[role="button"]:has-text("Retry")')
                if retry:
                    await retry.click()
                    await asyncio.sleep(3)
                    return True
                # Otherwise just reload
                self.logger.info("Error detected - reloading page...")
                await self.page.reload()
                await asyncio.sleep(3)
                return True
                
            return False
        except Exception as e:
            self.logger.debug(f"Error handling page error: {e}")
            return False
    
    async def scroll_and_collect_followers(self, limit: Optional[int] = None) -> List[FollowerInfo]:
        """
        Scroll through followers list and collect follower information (scan-only mode).
        
        Args:
            limit: Maximum number of followers to collect
            
        Returns:
            List of FollowerInfo objects
        """
        self.logger.info("Starting to scan followers...")
        
        scroll_count = 0
        no_new_followers_count = 0
        collected_limit = limit or float('inf')
        
        while scroll_count < LIMITS["max_scroll_attempts"]:
            # Get all visible follower cells
            cells = await self.page.query_selector_all(SELECTORS["follower_cell"])
            
            new_followers_found = 0
            
            for cell in cells:
                if len(self.followers) >= collected_limit:
                    break
                
                follower = await self._extract_follower_info(cell)
                
                if follower and follower.username not in self.scanned_usernames:
                    self.scanned_usernames.add(follower.username)
                    self.followers.append(follower)
                    new_followers_found += 1
                    
                    if follower.is_bot:
                        self.logger.info(f"  🤖 Bot detected: @{follower.username} - {follower.bot_reason}")
                    elif self.verbose:
                        self.logger.debug(f"  ✓ Scanned: @{follower.username}")
            
            # Update progress
            bot_count = sum(1 for f in self.followers if f.is_bot)
            self.logger.info(
                f"Progress: {len(self.followers)} scanned, {bot_count} bots found "
                f"{format_progress(len(self.followers), collected_limit if limit else len(self.followers) + 50)}"
            )
            
            # Check if we've reached limit
            if len(self.followers) >= collected_limit:
                self.logger.info(f"Reached scan limit of {limit}")
                break
            
            # Check if we found any new followers
            if new_followers_found == 0:
                no_new_followers_count += 1
                if no_new_followers_count >= 3:
                    self.logger.info("No more followers to load")
                    break
            else:
                no_new_followers_count = 0
            
            # Scroll down to load more
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(DELAYS["after_scroll"])
            
            # Wait for new content to load
            try:
                await self.page.wait_for_selector(
                    SELECTORS["loading_spinner"],
                    state="hidden",
                    timeout=5000
                )
            except PlaywrightTimeout:
                pass  # Spinner might not appear
            
            scroll_count += 1
        
        self.logger.info(f"✓ Scan complete: {len(self.followers)} followers, {sum(1 for f in self.followers if f.is_bot)} bots identified")
        return self.followers

    async def scan_and_remove_in_batches(
        self, 
        dry_run: bool = False,
        limit: Optional[int] = None,
        require_confirmation: bool = True,
        from_end: bool = False
    ) -> int:
        """
        Scan followers and remove bots in batches as they're found.
        This is more efficient as bots are removed while still visible.
        
        Args:
            dry_run: If True, only identify bots without removing
            limit: Maximum number of removals
            require_confirmation: If True, ask before first removal
            from_end: If True, start from the end of the followers list
            
        Returns:
            Number of successfully removed followers
        """
        if from_end:
            self.logger.info("Starting batch scan and remove process (FROM END)...")
            self.logger.info("Scrolling to end of followers list first...")
            await self._scroll_to_end_of_list()
        else:
            self.logger.info("Starting batch scan and remove process...")
        
        scroll_count = 0
        no_new_followers_count = 0
        removal_limit = limit or LIMITS["max_removals_per_session"]
        first_removal = True
        
        while scroll_count < LIMITS["max_scroll_attempts"]:
            # Check for page errors
            if await self._handle_page_error():
                await asyncio.sleep(2)
            
            # Get all visible follower cells
            cells = await self.page.query_selector_all(SELECTORS["follower_cell"])
            
            # If from_end, process cells in reverse order
            if from_end:
                cells = list(reversed(cells))
            
            new_followers_found = 0
            batch_bots = []
            
            # Scan visible cells
            for cell in cells:
                follower = await self._extract_follower_info(cell)
                
                if follower and follower.username not in self.scanned_usernames:
                    self.scanned_usernames.add(follower.username)
                    self.followers.append(follower)
                    new_followers_found += 1
                    
                    if follower.is_bot:
                        self.logger.info(f"  🤖 Bot detected: @{follower.username} - {follower.bot_reason}")
                        batch_bots.append((follower, cell))
                    elif self.verbose:
                        self.logger.debug(f"  ✓ Scanned: @{follower.username}")
            
            # Process bot removals for this batch
            if batch_bots and not dry_run:
                # First time confirmation
                if first_removal and require_confirmation:
                    bot_count = len([f for f in self.followers if f.is_bot])
                    print(f"\n  Found {bot_count} bots so far. First batch has {len(batch_bots)} bots.")
                    if not confirm_action("Start removing bots as they're found?"):
                        self.logger.info("Removal cancelled - continuing in dry-run mode")
                        dry_run = True
                    else:
                        first_removal = False
                
                if not dry_run:
                    for follower, cell in batch_bots:
                        if self.removed_count >= removal_limit:
                            self.logger.info(f"Reached removal limit of {removal_limit}")
                            break
                        
                        self.logger.info(f"  Removing @{follower.username}...")
                        success = await self._remove_follower_from_cell(cell, follower.username)
                        
                        if success:
                            follower.removed = True
                            self.removed_count += 1
                            self.logger.info(f"  ✓ Removed @{follower.username} ({self.removed_count}/{removal_limit})")
                        else:
                            follower.removal_error = "Failed to remove"
                            self.failed_count += 1
                            self.logger.warning(f"  ✗ Failed to remove @{follower.username}")
                        
                        await asyncio.sleep(DELAYS["between_removals"])
            
            # Check if reached removal limit
            if self.removed_count >= removal_limit:
                self.logger.info(f"Reached removal limit of {removal_limit}")
                break
            
            # Update progress
            bot_count = sum(1 for f in self.followers if f.is_bot)
            self.logger.info(
                f"Progress: {len(self.followers)} scanned, {bot_count} bots, "
                f"{self.removed_count} removed, {self.failed_count} failed"
            )
            
            # Check if we found any new followers
            if new_followers_found == 0:
                no_new_followers_count += 1
                if no_new_followers_count >= 3:
                    self.logger.info("No more followers to load")
                    break
            else:
                no_new_followers_count = 0
            
            # Scroll to load more (direction depends on from_end)
            if from_end:
                # Scroll up to load older followers (toward beginning)
                await self.page.evaluate("window.scrollBy(0, -600)")
            else:
                # Scroll down to load more recent followers
                await self.page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(DELAYS["after_scroll"])
            
            scroll_count += 1
        
        self.logger.info(
            f"✓ Complete: {len(self.followers)} scanned, "
            f"{sum(1 for f in self.followers if f.is_bot)} bots identified, "
            f"{self.removed_count} removed, {self.failed_count} failed"
        )
        
        return self.removed_count

    async def _scroll_to_end_of_list(self):
        """Scroll to the end of the followers list."""
        self.logger.info("Scrolling to end of list...")
        
        last_height = 0
        same_height_count = 0
        
        while same_height_count < 5:
            # Scroll to bottom
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.5)
            
            # Check for page errors
            if await self._handle_page_error():
                await asyncio.sleep(2)
            
            # Get new height
            new_height = await self.page.evaluate("document.body.scrollHeight")
            
            if new_height == last_height:
                same_height_count += 1
            else:
                same_height_count = 0
                last_height = new_height
                self.logger.debug(f"  Scrolling... (height: {new_height})")
        
        self.logger.info("✓ Reached end of followers list")

    async def _remove_follower_from_cell(self, cell, username: str) -> bool:
        """
        Remove a follower directly from their cell element (while visible).
        
        Args:
            cell: The UserCell element handle
            username: Username for logging
            
        Returns:
            True if removal successful, False otherwise
        """
        try:
            # Scroll cell into view
            await cell.scroll_into_view_if_needed()
            await asyncio.sleep(0.3)
            
            # Try multiple selectors for the menu button
            more_btn = None
            menu_selectors = [
                '[data-testid="caret"]',
                '[aria-label="More"]',
                '[data-testid="userActions"]',
                'button[aria-haspopup="menu"]',
            ]
            
            for selector in menu_selectors:
                more_btn = await cell.query_selector(selector)
                if more_btn:
                    break
            
            # Fallback: find any button with "more" in aria-label
            if not more_btn:
                buttons = await cell.query_selector_all('button')
                for btn in buttons:
                    aria_label = await btn.get_attribute('aria-label')
                    if aria_label and 'more' in aria_label.lower():
                        more_btn = btn
                        break
            
            if not more_btn:
                self.logger.debug(f"Could not find menu button for @{username}")
                return False
            
            await more_btn.click()
            await asyncio.sleep(DELAYS["menu_animation"])
            
            # Find and click "Remove follower" option
            remove_btn = await self._find_remove_button()
            if not remove_btn:
                await self.page.keyboard.press("Escape")
                self.logger.debug(f"Could not find remove option for @{username}")
                return False
            
            await remove_btn.click()
            await asyncio.sleep(DELAYS["menu_animation"])
            
            # Handle confirmation dialog
            await self._handle_confirmation_dialog()
            
            return True
            
        except Exception as e:
            self.logger.debug(f"Error removing @{username}: {e}")
            try:
                await self.page.keyboard.press("Escape")
            except:
                pass
            return False
    
    async def _extract_follower_info(self, cell) -> Optional[FollowerInfo]:
        """
        Extract follower information from a UserCell element.
        
        Args:
            cell: Playwright element handle for the follower cell
            
        Returns:
            FollowerInfo object or None if extraction fails
        """
        try:
            # Try to find username from the profile link
            link = await cell.query_selector(SELECTORS["user_name_link"])
            if not link:
                return None
            
            href = await link.get_attribute("href")
            if not href or href == "/":
                return None
            
            # Extract username from href (format: /{username})
            username = href.strip("/").split("/")[0]
            if not username or username in ("home", "explore", "notifications", "messages"):
                return None
            
            # Try to get display name
            display_name = ""
            name_span = await cell.query_selector(SELECTORS["user_name_span"])
            if name_span:
                display_name = await name_span.inner_text()
            
            # Check if bot
            is_bot, reason = is_bot_username(username)
            
            return FollowerInfo(
                username=username,
                display_name=display_name,
                is_bot=is_bot,
                bot_reason=reason
            )
            
        except Exception as e:
            self.logger.debug(f"Failed to extract follower info: {e}")
            return None
    
    async def _find_user_cell(self, username: str, max_scrolls: int = 15) -> Optional[any]:
        """
        Find a user cell by scrolling through the page.
        
        Args:
            username: Twitter username to find
            max_scrolls: Maximum scroll attempts
            
        Returns:
            Element handle for the user cell, or None
        """
        username_lower = username.lower()
        
        # First scroll to top
        await self.page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.5)
        
        for scroll_attempt in range(max_scrolls):
            # Check for page errors first
            if await self._handle_page_error():
                await asyncio.sleep(2)
            
            cells = await self.page.query_selector_all(SELECTORS["follower_cell"])
            
            if not cells:
                # No cells found - might be loading or error
                await asyncio.sleep(1)
                continue
            
            for cell in cells:
                try:
                    link = await cell.query_selector(SELECTORS["user_name_link"])
                    if link:
                        href = await link.get_attribute("href")
                        if href and href.strip("/").split("/")[0].lower() == username_lower:
                            # Scroll element into view
                            await cell.scroll_into_view_if_needed()
                            await asyncio.sleep(0.5)
                            return cell
                except Exception:
                    continue
            
            # Scroll down to load more
            await self.page.evaluate("window.scrollBy(0, 400)")
            await asyncio.sleep(0.8)
        
        return None

    async def remove_follower(self, username: str) -> bool:
        """
        Remove a specific follower.
        
        Args:
            username: Twitter username to remove
            
        Returns:
            True if removal successful, False otherwise
        """
        self.logger.info(f"Attempting to remove @{username}...")
        
        for attempt in range(LIMITS["max_retry_attempts"]):
            try:
                # Find the user cell (with scrolling)
                target_cell = await self._find_user_cell(username)
                
                if not target_cell:
                    self.logger.warning(f"Could not find @{username} after scrolling")
                    return False
                
                # Try multiple selectors for the menu button
                more_btn = None
                menu_selectors = [
                    '[data-testid="caret"]',
                    '[aria-label="More"]',
                    '[data-testid="userActions"]',
                    'button[aria-haspopup="menu"]',
                    '[role="button"][aria-haspopup="menu"]',
                ]
                
                for selector in menu_selectors:
                    more_btn = await target_cell.query_selector(selector)
                    if more_btn:
                        self.logger.debug(f"Found menu button with selector: {selector}")
                        break
                
                if not more_btn:
                    # Try finding any button in the cell
                    buttons = await target_cell.query_selector_all('button')
                    for btn in buttons:
                        aria_label = await btn.get_attribute('aria-label')
                        if aria_label and 'more' in aria_label.lower():
                            more_btn = btn
                            break
                
                if not more_btn:
                    self.logger.warning(f"Could not find menu button for @{username}")
                    if attempt < LIMITS["max_retry_attempts"] - 1:
                        await asyncio.sleep(1)
                        continue
                    return False
                
                await more_btn.click()
                await asyncio.sleep(DELAYS["menu_animation"])
                
                # Find and click "Remove follower" option
                remove_btn = await self._find_remove_button()
                if not remove_btn:
                    # Close menu if open
                    await self.page.keyboard.press("Escape")
                    self.logger.warning(f"Could not find remove option for @{username}")
                    return False
                
                await remove_btn.click()
                await asyncio.sleep(DELAYS["menu_animation"])
                
                # Handle confirmation dialog if present
                await self._handle_confirmation_dialog()
                
                self.logger.info(f"✓ Successfully removed @{username}")
                return True
                
            except PlaywrightTimeout:
                self.logger.warning(f"Timeout on attempt {attempt + 1} for @{username}")
                if attempt < LIMITS["max_retry_attempts"] - 1:
                    await asyncio.sleep(DELAYS["rate_limit_backoff"] / 10)
                    
            except Exception as e:
                self.logger.error(f"Error removing @{username}: {e}")
                if attempt < LIMITS["max_retry_attempts"] - 1:
                    await asyncio.sleep(1)
        
        return False
    
    async def _find_remove_button(self):
        """Find the 'Remove follower' button in the dropdown menu."""
        try:
            # Wait for menu to appear
            await self.page.wait_for_selector(SELECTORS["menu_item"], timeout=3000)
            
            # Get all menu items
            menu_items = await self.page.query_selector_all(SELECTORS["menu_item"])
            
            for item in menu_items:
                text = await item.inner_text()
                text_lower = text.lower()
                
                if any(pattern.lower() in text_lower for pattern in [
                    TEXT_PATTERNS["remove_follower"],
                    TEXT_PATTERNS["remove_follower_alt"],
                    "remove this follower",
                    "remove follower"
                ]):
                    return item
            
            return None
            
        except Exception:
            return None
    
    async def _handle_confirmation_dialog(self):
        """Handle any confirmation dialog that appears."""
        try:
            # Check for confirmation dialog
            confirm_btn = await self.page.wait_for_selector(
                SELECTORS["confirm_button"],
                timeout=2000
            )
            if confirm_btn:
                await confirm_btn.click()
                await asyncio.sleep(DELAYS["menu_animation"])
                
        except PlaywrightTimeout:
            # No confirmation dialog - that's fine
            pass
        except Exception as e:
            self.logger.debug(f"Confirmation dialog handling: {e}")
    
    async def process_bot_removals(
        self, 
        dry_run: bool = False,
        limit: Optional[int] = None,
        require_confirmation: bool = True
    ) -> int:
        """
        Process removal of identified bot accounts.
        
        Args:
            dry_run: If True, only report bots without removing
            limit: Maximum number of bots to remove
            require_confirmation: If True, ask for confirmation before removal
            
        Returns:
            Number of successfully removed followers
        """
        bot_followers = [f for f in self.followers if f.is_bot]
        
        if not bot_followers:
            self.logger.info("No bot accounts identified - nothing to remove")
            return 0
        
        # Apply limit
        removal_limit = min(
            limit or LIMITS["max_removals_per_session"],
            LIMITS["max_removals_per_session"],
            len(bot_followers)
        )
        
        bots_to_process = bot_followers[:removal_limit]
        
        # Display bot list
        print("\n" + "=" * 60)
        print(f"  📋 BOT ACCOUNTS IDENTIFIED ({len(bot_followers)} total)")
        print("=" * 60)
        
        for i, bot in enumerate(bots_to_process[:20], 1):  # Show first 20
            print(f"  {i:3}. @{bot.username:<20} - {bot.bot_reason}")
        
        if len(bots_to_process) > 20:
            print(f"  ... and {len(bots_to_process) - 20} more")
        
        print("=" * 60)
        
        if dry_run:
            self.logger.info("DRY RUN mode - no followers will be removed")
            return 0
        
        # Confirmation
        if require_confirmation:
            if not confirm_action(f"\nProceed with removing {len(bots_to_process)} bot followers?"):
                self.logger.info("Removal cancelled by user")
                return 0
        
        # Re-navigate to followers page and scroll to top to start fresh
        self.logger.info("Refreshing followers page before removal...")
        if not await self.navigate_to_followers():
            self.logger.error("Could not load followers page for removal")
            return 0
        await self.page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1)
        
        # Process removals
        self.logger.info(f"Starting removal of {len(bots_to_process)} bot followers...")
        
        removed = 0
        failed = 0
        consecutive_failures = 0
        
        for i, bot in enumerate(bots_to_process, 1):
            self.logger.info(f"[{i}/{len(bots_to_process)}] Processing @{bot.username}")
            
            # Check for page errors before each removal
            if await self._handle_page_error():
                self.logger.info("Recovered from page error, continuing...")
                await asyncio.sleep(2)
            
            success = await self.remove_follower(bot.username)
            
            if success:
                bot.removed = True
                removed += 1
                self.removed_count += 1
                consecutive_failures = 0
            else:
                bot.removal_error = "Failed to remove"
                failed += 1
                self.failed_count += 1
                consecutive_failures += 1
                
                # If too many consecutive failures, refresh the page
                if consecutive_failures >= 5:
                    self.logger.warning("Multiple consecutive failures - refreshing page...")
                    await self.navigate_to_followers()
                    consecutive_failures = 0
            
            # Progress update
            if i % LIMITS["batch_size"] == 0:
                self.logger.info(
                    f"Batch progress: {removed} removed, {failed} failed "
                    f"{format_progress(i, len(bots_to_process))}"
                )
            
            # Delay between removals
            if i < len(bots_to_process):
                await asyncio.sleep(DELAYS["between_removals"])
        
        self.logger.info(f"✓ Removal complete: {removed} removed, {failed} failed")
        return removed
    
    async def take_screenshot(self, name: str) -> str:
        """
        Take a screenshot for debugging.
        
        Args:
            name: Screenshot name (without extension)
            
        Returns:
            Path to saved screenshot
        """
        from config import OUTPUT
        import os
        
        os.makedirs(OUTPUT["screenshots_dir"], exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(OUTPUT["screenshots_dir"], f"{name}_{timestamp}.png")
        
        await self.page.screenshot(path=path, full_page=True)
        self.logger.info(f"Screenshot saved: {path}")
        
        return path
    
    async def run(
        self,
        dry_run: bool = False,
        limit: Optional[int] = None,
        skip_confirmation: bool = False,
        from_end: bool = False
    ) -> CleanupReport:
        """
        Run the full cleanup process using batch scan-and-remove approach.
        
        Args:
            dry_run: If True, identify bots without removing them
            limit: Maximum number of followers to process/remove
            skip_confirmation: If True, skip confirmation prompts
            from_end: If True, start from the end of the followers list
            
        Returns:
            CleanupReport with results
        """
        self.report.dry_run = dry_run
        
        try:
            # Step 1: Login
            if not await self.wait_for_login():
                raise RuntimeError("Login failed or timed out")
            
            # Confirmation before proceeding
            if not skip_confirmation:
                if not confirm_action(f"Proceed with scanning followers for @{self.user_id}?", default=True):
                    self.logger.info("Operation cancelled by user")
                    self.report.session_end = datetime.now().isoformat()
                    return self.report
            
            # Step 2: Navigate to followers
            if not await self.navigate_to_followers():
                raise RuntimeError("Failed to navigate to followers page")
            
            # Step 3: Scan and remove in batches (more efficient!)
            # This scans visible followers and removes bots while they're still on screen
            await self.scan_and_remove_in_batches(
                dry_run=dry_run,
                limit=limit,
                require_confirmation=not skip_confirmation,
                from_end=from_end
            )
            
            # Update final stats
            self.report.total_followers_scanned = len(self.followers)
            self.report.bot_accounts_identified = sum(1 for f in self.followers if f.is_bot)
            self.report.successfully_removed = self.removed_count
            self.report.failed_removals = self.failed_count
            self.report.followers = [asdict(f) for f in self.followers]
            self.report.session_end = datetime.now().isoformat()
            
            # Save report and backup
            saved_files = save_report(self.report)
            self.logger.info(f"Report saved: {saved_files}")
            
            if self.removed_count > 0:
                backup_path = save_backup(self.followers, self.user_id)
                self.logger.info(f"Backup saved: {backup_path}")
            
            # Print summary
            print_summary(self.report)
            
            return self.report
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            self.report.errors.append(str(e))
            self.report.session_end = datetime.now().isoformat()
            
            # Take error screenshot
            try:
                await self.take_screenshot("error")
            except Exception:
                pass
            
            raise

