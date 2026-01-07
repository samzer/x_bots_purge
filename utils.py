"""
Utility functions for Twitter Follower Cleanup Tool.
Includes bot detection, logging, and reporting helpers.
"""

from __future__ import annotations

import re
import json
import csv
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field

from config import BOT_DETECTION, OUTPUT


# =============================================================================
# DATA CLASSES
# =============================================================================
@dataclass
class FollowerInfo:
    """Represents a Twitter follower."""
    username: str
    display_name: str = ""
    is_bot: bool = False
    bot_reason: str = ""
    removed: bool = False
    removal_error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class CleanupReport:
    """Summary report of cleanup operation."""
    session_start: str
    session_end: str = ""
    user_id: str = ""
    total_followers_scanned: int = 0
    bot_accounts_identified: int = 0
    successfully_removed: int = 0
    failed_removals: int = 0
    dry_run: bool = False
    followers: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# =============================================================================
# LOGGING SETUP
# =============================================================================
def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging with both file and console handlers."""
    # Create logs directory if needed
    log_dir = os.path.dirname(OUTPUT["log_file"])
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Configure logging level
    level = logging.DEBUG if verbose else logging.INFO
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup root logger
    logger = logging.getLogger('twitter_cleaner')
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler with colors
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(ColoredFormatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    ))
    logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(OUTPUT["log_file"], encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for terminal output."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m',
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        record.levelname = f"{color}{record.levelname}{reset}"
        return super().format(record)


# =============================================================================
# BOT DETECTION
# =============================================================================
def is_bot_username(username: str) -> tuple[bool, str]:
    """
    Check if a username matches bot patterns.
    
    Args:
        username: Twitter username to check (without @)
        
    Returns:
        Tuple of (is_bot, reason)
    """
    # Primary check: 3+ digits at end
    if re.match(BOT_DETECTION["digit_suffix_pattern"], username):
        return True, "Username ends with 3+ consecutive digits"
    
    # Additional suspicious patterns
    for pattern in BOT_DETECTION.get("suspicious_patterns", []):
        if re.match(pattern, username):
            return True, f"Matches suspicious pattern: {pattern}"
    
    return False, ""


def extract_username_from_text(text: str) -> Optional[str]:
    """
    Extract username from text that may contain @ prefix.
    
    Args:
        text: Text containing username
        
    Returns:
        Clean username without @ prefix, or None
    """
    if not text:
        return None
    
    # Remove @ prefix if present
    username = text.strip().lstrip('@')
    
    # Validate it looks like a username (alphanumeric + underscore)
    if re.match(r'^[a-zA-Z0-9_]+$', username):
        return username
    
    return None


# =============================================================================
# REPORTING
# =============================================================================
def ensure_directories():
    """Create necessary output directories."""
    for dir_path in [OUTPUT["reports_dir"], OUTPUT["screenshots_dir"], OUTPUT["backup_dir"]]:
        os.makedirs(dir_path, exist_ok=True)


def save_report(report: CleanupReport, format: str = "both") -> Dict[str, str]:
    """
    Save cleanup report to file.
    
    Args:
        report: CleanupReport instance
        format: "json", "csv", or "both"
        
    Returns:
        Dict with file paths
    """
    ensure_directories()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"cleanup_report_{report.user_id}_{timestamp}"
    saved_files = {}
    
    # Convert report to dict
    report_dict = asdict(report)
    
    # Save JSON
    if format in ("json", "both"):
        json_path = os.path.join(OUTPUT["reports_dir"], f"{base_name}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False)
        saved_files["json"] = json_path
    
    # Save CSV (followers list)
    if format in ("csv", "both") and report.followers:
        csv_path = os.path.join(OUTPUT["reports_dir"], f"{base_name}_followers.csv")
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=report.followers[0].keys())
            writer.writeheader()
            writer.writerows(report.followers)
        saved_files["csv"] = csv_path
    
    return saved_files


def save_backup(followers: List[FollowerInfo], user_id: str) -> str:
    """
    Save backup of removed followers for potential restoration.
    
    Args:
        followers: List of removed followers
        user_id: Twitter user ID
        
    Returns:
        Path to backup file
    """
    ensure_directories()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(
        OUTPUT["backup_dir"], 
        f"removed_followers_{user_id}_{timestamp}.json"
    )
    
    backup_data = {
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        "followers": [asdict(f) for f in followers if f.removed]
    }
    
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False)
    
    return backup_path


# =============================================================================
# DISPLAY HELPERS
# =============================================================================
def print_banner():
    """Display application banner."""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║          🧹 Twitter Follower Cleanup Tool 🧹                  ║
║                                                               ║
║    Automatically remove suspected bot followers from your     ║
║    Twitter/X account based on username patterns.              ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_summary(report: CleanupReport):
    """Print formatted summary of cleanup operation."""
    mode = "DRY RUN" if report.dry_run else "LIVE"
    
    summary = f"""
┌───────────────────────────────────────────────────────────────┐
│                    CLEANUP SUMMARY ({mode})                   
├───────────────────────────────────────────────────────────────┤
│  User ID:                    @{report.user_id:<28}│
│  Total Followers Scanned:    {report.total_followers_scanned:<30}│
│  Bot Accounts Identified:    {report.bot_accounts_identified:<30}│
│  Successfully Removed:       {report.successfully_removed:<30}│
│  Failed Removals:            {report.failed_removals:<30}│
│  Session Duration:           {calculate_duration(report.session_start, report.session_end):<30}│
└───────────────────────────────────────────────────────────────┘
"""
    print(summary)


def calculate_duration(start: str, end: str) -> str:
    """Calculate human-readable duration between two ISO timestamps."""
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end) if end else datetime.now()
        delta = end_dt - start_dt
        
        minutes, seconds = divmod(int(delta.total_seconds()), 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except Exception:
        return "N/A"


def format_progress(current: int, total: int, width: int = 30) -> str:
    """Create a text-based progress bar."""
    if total == 0:
        return "[" + "=" * width + "] 100%"
    
    percent = current / total
    filled = int(width * percent)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {percent*100:.1f}%"


def confirm_action(message: str, default: bool = False) -> bool:
    """
    Prompt user for confirmation.
    
    Args:
        message: Confirmation message to display
        default: Default response if user just presses Enter
        
    Returns:
        True if confirmed, False otherwise
    """
    suffix = " [Y/n]: " if default else " [y/N]: "
    response = input(message + suffix).strip().lower()
    
    if not response:
        return default
    
    return response in ('y', 'yes')

