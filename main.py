#!/usr/bin/env python3
"""
Twitter Follower Cleanup Tool - Entry Point

Automates the removal of suspected bot followers from a Twitter/X account.
Identifies potential bot accounts (usernames ending with 3+ digits) and removes them.

Usage:
    python main.py --user-id <username> [options]

Examples:
    python main.py --user-id samirmadhavan --dry-run
    python main.py --user-id samirmadhavan --limit 50 --verbose
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent))

from utils import setup_logging, print_banner
from twitter_cleaner import TwitterCleaner


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Twitter Follower Cleanup Tool - Remove suspected bot followers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --user-id samirmadhavan --dry-run
      Scan followers and identify bots without removing them

  %(prog)s --user-id samirmadhavan --limit 50 --verbose
      Remove up to 50 bot followers with detailed logging

  %(prog)s --user-id samirmadhavan --limit 10 --yes
      Remove up to 10 bots without confirmation prompts

Safety Notes:
  - Always test with --dry-run first to review detected bots
  - Use small --limit values initially (5-10) to verify behavior
  - Reports are saved to ./reports/ directory
  - Backups of removed followers are saved to ./backups/
        """,
    )
    
    # Required arguments
    parser.add_argument(
        "--user-id",
        "-u",
        required=True,
        help="Twitter username to clean followers from (without @)",
    )
    
    # Optional arguments
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Identify bot accounts without removing them",
    )
    
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=100,
        help="Maximum number of followers to process/remove (default: 100)",
    )
    
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode after login (not recommended)",
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable detailed debug logging",
    )
    
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompts (use with caution)",
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )
    
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> int:
    """
    Async main function.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    # Setup logging
    logger = setup_logging(verbose=args.verbose)
    
    # Print banner
    print_banner()
    
    # Log configuration
    logger.info("=" * 50)
    logger.info("Configuration:")
    logger.info(f"  User ID:     @{args.user_id}")
    logger.info(f"  Mode:        {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info(f"  Limit:       {args.limit} followers")
    logger.info(f"  Verbose:     {args.verbose}")
    logger.info(f"  Auto-confirm:{args.yes}")
    logger.info("=" * 50)
    
    if not args.dry_run and not args.yes:
        logger.warning("⚠️  LIVE MODE: Followers will be permanently removed!")
        print()
    
    try:
        async with TwitterCleaner(
            user_id=args.user_id,
            headless=args.headless,
            verbose=args.verbose
        ) as cleaner:
            
            report = await cleaner.run(
                dry_run=args.dry_run,
                limit=args.limit,
                skip_confirmation=args.yes
            )
            
            # Return success if no errors
            return 0 if not report.errors else 1
            
    except KeyboardInterrupt:
        logger.info("\n\nOperation cancelled by user (Ctrl+C)")
        return 130
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Run async main
    try:
        exit_code = asyncio.run(main_async(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(130)


if __name__ == "__main__":
    main()

