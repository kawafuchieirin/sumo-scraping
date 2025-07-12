#!/usr/bin/env python3
import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Playwrightのセットアップを行う"""
    try:
        logger.info("Installing Playwright browsers...")
        result = subprocess.run([
            sys.executable, "-m", "playwright", "install", "chromium"
        ], check=True, capture_output=True, text=True)
        
        logger.info("Playwright setup completed successfully!")
        logger.info(result.stdout)
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error setting up Playwright: {e}")
        logger.error(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    if main():
        print("Playwright setup completed. You can now run the scraper.")
    else:
        print("Failed to setup Playwright. Please check the logs.")