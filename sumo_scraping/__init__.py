"""SUUMO Scraping Package

A Python web scraper for SUUMO real estate listings using Playwright and BeautifulSoup.
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .models import PropertyInfo, RoomInfo, ScrapingResult

__all__ = ["PropertyInfo", "RoomInfo", "ScrapingResult"]