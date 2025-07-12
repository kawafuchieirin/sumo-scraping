# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a SUUMO real estate scraping project that uses Python with Poetry for dependency management. The project provides both BeautifulSoup-based and Playwright-based scrapers for collecting rental property data from SUUMO.

## Project Status

- **Current State**: Fully implemented with Poetry dependency management
- **Repository**: https://github.com/kawafuchieirin/sumo-scraping.git
- **Technology Stack**: Python 3.8+, Poetry, Playwright, BeautifulSoup, Pydantic

## Development Setup

```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Setup Playwright browsers
poetry run setup-playwright

# Run the basic scraper
poetry run suumo-scraper

# Run the Playwright scraper (for Shibuya station)
poetry run suumo-playwright
```

## Commands

- `poetry run suumo-scraper`: Run BeautifulSoup-based scraper for Yamanote line
- `poetry run suumo-playwright`: Run Playwright-based scraper for Shibuya station (100 rooms target)
- `poetry run setup-playwright`: Setup Playwright browsers
- `python sumo_scraping/suumo_multi_scraper.py`: Run multi-station scraper with custom options

## Multi-Station Scraper Usage

```bash
# Basic usage - get 100 rooms from Shibuya
python sumo_scraping/suumo_multi_scraper.py --stations 渋谷 --count 100

# Multiple stations - get 200 rooms from Shibuya, Shinjuku, Ikebukuro
python sumo_scraping/suumo_multi_scraper.py --stations 渋谷 新宿 池袋 --count 200

# All Yamanote line stations - get 500 rooms
python sumo_scraping/suumo_multi_scraper.py --yamanote --count 500

# List supported stations
python sumo_scraping/suumo_multi_scraper.py --list-stations

# Custom output files
python sumo_scraping/suumo_multi_scraper.py --stations 渋谷 --count 50 --output-json my_data.json --output-csv my_data.csv
```

## Testing and Linting

```bash
# Run tests
poetry run pytest

# Format code
poetry run black .

# Type checking
poetry run mypy sumo_scraping/

# Linting
poetry run flake8 sumo_scraping/
```

## Notes

- Project uses Pydantic for data validation and type safety
- Rate limiting is implemented (2-3 seconds between requests)
- Data is saved in both JSON and CSV formats in the `data/` directory
- Validation errors are logged separately for debugging