"""
Configuration constants for Twitter Follower Cleanup Tool.
Update selectors here as Twitter's DOM structure changes.
"""

# =============================================================================
# BROWSER CONFIGURATION
# =============================================================================
BROWSER_CONFIG = {
    "headless": False,
    "slow_mo": 100,  # milliseconds between actions
    "viewport": {"width": 1280, "height": 720},
    "user_data_dir": "./browser_data",  # Persistent session storage
}

# =============================================================================
# TIMING CONFIGURATION
# =============================================================================
DELAYS = {
    "between_removals": 2.0,  # seconds between follower removals
    "after_scroll": 1.5,  # seconds to wait after scrolling
    "menu_animation": 0.5,  # seconds for menu to render
    "page_load": 3.0,  # seconds for page to load
    "rate_limit_backoff": 60,  # seconds to wait on rate limit
    "login_check_interval": 2.0,  # seconds between login status checks
}

# =============================================================================
# LIMITS & SAFETY
# =============================================================================
LIMITS = {
    "max_removals_per_session": 100,
    "max_retry_attempts": 3,
    "max_scroll_attempts": 50,  # prevent infinite scrolling
    "batch_size": 10,  # followers to process before brief pause
}

# =============================================================================
# TWITTER/X SELECTORS
# Note: These may need updating as Twitter changes their DOM
# =============================================================================
SELECTORS = {
    # Page elements
    "follower_cell": '[data-testid="UserCell"]',
    "user_name_link": 'a[role="link"][href^="/"]',
    "user_name_span": '[dir="ltr"] > span',
    
    # Menu elements
    "more_menu_button": '[data-testid="caret"]',
    "menu_item": '[role="menuitem"]',
    
    # Login detection
    "profile_button": '[data-testid="SideNav_AccountSwitcher_Button"]',
    "login_form": '[data-testid="loginButton"]',
    "home_timeline": '[data-testid="primaryColumn"]',
    
    # Dialog elements
    "confirm_button": '[data-testid="confirmationSheetConfirm"]',
    "dialog": '[role="dialog"]',
    
    # Loading indicators
    "loading_spinner": '[role="progressbar"]',
}

# =============================================================================
# TEXT PATTERNS (for locating elements by text)
# =============================================================================
TEXT_PATTERNS = {
    "remove_follower": "Remove this follower",
    "remove_follower_alt": "Remove follower",
    "confirm_remove": "Remove",
}

# =============================================================================
# URLS
# =============================================================================
URLS = {
    "base": "https://x.com",
    "login": "https://x.com/login",
    "followers_template": "https://x.com/{user_id}/followers",
}

# =============================================================================
# BOT DETECTION PATTERNS
# =============================================================================
BOT_DETECTION = {
    # Usernames ending with 3+ consecutive digits
    "digit_suffix_pattern": r".*\d{3,}$",
    # Optional: Additional patterns can be added here
    "suspicious_patterns": [
        r"^[a-z]+\d{8}$",  # lowercase letters followed by 8 digits
        r"^\w+_\d{5,}$",   # word characters, underscore, 5+ digits
    ],
}

# =============================================================================
# OUTPUT CONFIGURATION
# =============================================================================
OUTPUT = {
    "reports_dir": "./reports",
    "screenshots_dir": "./screenshots",
    "backup_dir": "./backups",
    "log_file": "./twitter_cleaner.log",
}

