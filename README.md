# 🧹 Twitter Follower Cleanup Tool

Automate the removal of suspected bot followers from your Twitter/X account. The tool identifies potential bot accounts (usernames ending with 5+ consecutive digits) and removes them as followers.

## 📺 Demo Video

[![Watch the demo](https://img.youtube.com/vi/cpUto_9b8Pg/maxresdefault.jpg)](https://www.youtube.com/watch?v=cpUto_9b8Pg)

> 👆 Click the image above to watch the tool in action!

## Features

- **Bot Detection**: Identifies accounts with usernames ending in 3+ digits (common bot pattern)
- **Dry Run Mode**: Preview detected bots before removing
- **Progress Tracking**: Real-time progress indicators and logging
- **Safety First**: Confirmation prompts, daily limits, and backup creation
- **Detailed Reports**: JSON/CSV reports saved with timestamps
- **Persistent Sessions**: Browser login sessions are saved for convenience

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Setup

1. **Clone or navigate to the project directory:**
   ```bash
   cd x_bots_purge
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers:**
   ```bash
   playwright install chromium
   ```

## Usage

### Basic Commands

```bash
# Dry run - identify bots without removing them (RECOMMENDED FIRST)
python main.py --user-id YOUR_USERNAME --dry-run

# Remove up to 50 bot followers
python main.py --user-id YOUR_USERNAME --limit 50

# Verbose mode with detailed logging
python main.py --user-id YOUR_USERNAME --limit 20 --verbose

# Skip confirmation prompts (use with caution)
python main.py --user-id YOUR_USERNAME --limit 10 --yes
```

### Command Line Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--user-id` | `-u` | Twitter username to clean (required) | - |
| `--dry-run` | `-n` | Identify bots without removing | False |
| `--limit` | `-l` | Max followers to process | 100 |
| `--verbose` | `-v` | Enable detailed logging | False |
| `--yes` | `-y` | Skip confirmation prompts | False |
| `--headless` | - | Run headless after login | False |

### Workflow

1. **First Run**: The browser will open and prompt you to log in manually
2. **Login**: Enter your Twitter credentials in the browser
3. **Scanning**: The tool scrolls through your followers list
4. **Detection**: Bot accounts are identified and displayed
5. **Confirmation**: Review the list and confirm removal
6. **Removal**: Bots are removed one by one with delays
7. **Report**: Summary and backup files are saved

## Bot Detection

The tool identifies potential bots using these patterns:

- **Primary Pattern**: Usernames ending with 3+ consecutive digits (e.g., `user123456`)
- **Additional Patterns**: Configurable in `config.py`

### Examples of Detected Bot Usernames

```
✅ Detected as bot:
  - john_smith12345
  - randomuser789
  - crypto_bot99999

❌ NOT detected (legitimate):
  - john_smith
  - user_2024
  - alice99
```

## Output Files

### Reports (`./reports/`)

- `cleanup_report_USERNAME_TIMESTAMP.json` - Full report with all data
- `cleanup_report_USERNAME_TIMESTAMP_followers.csv` - Follower list

### Backups (`./backups/`)

- `removed_followers_USERNAME_TIMESTAMP.json` - List of removed followers

### Logs

- `twitter_cleaner.log` - Detailed operation logs

## Configuration

Edit `config.py` to customize:

```python
# Adjust delays between actions
DELAYS = {
    "between_removals": 2.0,  # seconds
    "after_scroll": 1.5,
    # ...
}

# Set limits
LIMITS = {
    "max_removals_per_session": 100,
    "max_retry_attempts": 3,
    # ...
}

# Update selectors if Twitter changes their DOM
SELECTORS = {
    "follower_cell": '[data-testid="UserCell"]',
    # ...
}
```

## Safety Features

1. **Confirmation Prompts**: Ask before scanning and removing
2. **Daily Limits**: Max 100 removals per session by default
3. **Rate Limiting**: Built-in delays to avoid Twitter blocks
4. **Backup Files**: All removed followers are logged for reference
5. **Dry Run Mode**: Always test first!

## Troubleshooting

### "Element not found" errors

Twitter frequently changes their DOM. Update selectors in `config.py`:

```python
SELECTORS = {
    "follower_cell": '[data-testid="UserCell"]',  # Update if changed
    # ...
}
```

### Rate limiting / Account restrictions

- Reduce `--limit` to smaller batches (5-10)
- Increase delays in `config.py`
- Wait 24 hours between sessions

### Login not detected

- Ensure you complete the full login flow
- Wait for the home timeline to load
- Check for 2FA prompts

### Browser crashes

- Clear `./browser_data/` directory
- Reinstall Playwright: `playwright install chromium`

## Project Structure

```
x_bots_purge/
├── main.py              # Entry point, CLI argument parsing
├── twitter_cleaner.py   # Main TwitterCleaner class
├── config.py            # Configuration constants
├── utils.py             # Helper functions
├── requirements.txt     # Python dependencies
├── README.md            # This file
├── browser_data/        # Persistent browser session (auto-created)
├── reports/             # Generated reports (auto-created)
├── backups/             # Removed followers backup (auto-created)
└── screenshots/         # Debug screenshots (auto-created)
```

## Disclaimer

⚠️ **Use at your own risk.** This tool automates browser actions on Twitter/X. While it includes safety features, automated actions may violate Twitter's Terms of Service. The authors are not responsible for any account restrictions or other consequences.

## License

MIT License - Feel free to modify and distribute.

