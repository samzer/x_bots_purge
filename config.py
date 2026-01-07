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
    "viewport": None,  # None = use full screen size
    "user_data_dir": "./browser_data",  # Persistent session storage
    "start_maximized": True,  # Start browser maximized
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
    "max_removals_per_session": 1000,
    "max_retry_attempts": 3,
    "max_scroll_attempts": 150,  # prevent infinite scrolling
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
    "digit_suffix_pattern": r".*\d{5,}$",
    # Optional: Additional patterns can be added here
    "suspicious_patterns": [
        r"^[a-z]+\d{8}$",                  # lowercase letters followed by 8 digits
        r"^\w+_\d{5,}$",                   # word characters, underscore, 5+ digits
        r"\d{6,}$",                        # ends with 6+ digits
        r"^\d{8,}$",                       # all digits, length 8+
        r"^(?=[0-9a-f]*[0-9])(?=[0-9a-f]*[a-f])[0-9a-f]{12,}$",  # 12+ hex chars with at least one letter and digit
        r"(\d{2,})\1{2,}",                 # a digit group (2+ digits) immediately repeated 2+ times (chunk repetition)
        r"(\d)\1{4,}",                     # same digit 5+ times in a row
        r"^(?=(?:.*\d){6,}).*$",           # 6+ digits anywhere
        r"^[a-zA-Z]\d{6,}$",               # letter then 6+ digits
        r"_[12]\d{3}$",                    # underscore, year-like suffix
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

