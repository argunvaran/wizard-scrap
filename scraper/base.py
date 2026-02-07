import os
import logging
from playwright.sync_api import sync_playwright

logger = logging.getLogger('scraper')

class BaseScraper:
    def __init__(self):
        self.browser = None
        self.page = None
        self.playwright = None

    def start_browser(self):
        if not self.playwright:
            logger.info("Initializing Playwright (BaseScraper)...")
            self.playwright = sync_playwright().start()
            
            args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--disable-gpu",
                "--disable-setuid-sandbox",
                "--no-zygote",
                "--single-process",
                "--window-size=1920,1080",
            ]
            
            # Default to HEADLESS=True for server stability
            is_headless = os.getenv('HEADLESS', 'True').lower() == 'true'
            
            logger.info(f"Launching Browser (Headless: {is_headless})...")
            self.browser = self.playwright.chromium.launch(
                headless=is_headless,
                args=args
            )
            context = self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="tr-TR",
                timezone_id="Europe/Istanbul"
            )
            self.page = context.new_page()

    def close_browser(self):
        if self.browser:
            logger.info("Closing browser...")
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None

    def navigate(self, url, timeout=60000):
        if not self.page:
            self.start_browser()
        logger.info(f"Navigating to {url}...")
        try:
            self.page.goto(url, timeout=timeout)
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            raise
