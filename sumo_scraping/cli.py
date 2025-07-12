#!/usr/bin/env python3
"""Command line interface for sumo-scraping."""

import asyncio
import sys

def main():
    """Entry point for suumo-scraper command."""
    from .suumo_scraper import main as scraper_main
    scraper_main()

def main_playwright():
    """Entry point for suumo-playwright command."""
    from .suumo_playwright_scraper import main as playwright_main
    asyncio.run(playwright_main())

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "playwright":
        main_playwright()
    else:
        main()