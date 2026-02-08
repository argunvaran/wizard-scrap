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
            # Create context with ad-blocking
            context = self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="tr-TR",
                timezone_id="Europe/Istanbul"
            )
            
            # Block resources to speed up
            context.route("**/*", lambda route: self._handle_route(route))
            
            self.page = context.new_page()

    def _handle_route(self, route):
        # Block aggressively
        resource_type = route.request.resource_type
        if resource_type in ["image", "media", "font", "websocket", "manifest", "other"]:
            route.abort()
        elif "google-analytics" in route.request.url or "doubleclick" in route.request.url:
            route.abort()
        else:
            route.continue_()

    def close_browser(self):
        if self.browser:
            try:
                self.browser.close()
            except: pass
            self.browser = None
        if self.playwright:
            try:
                self.playwright.stop()
            except: pass
            self.playwright = None

    def navigate(self, url, timeout=90000):
        if not self.page:
            self.start_browser()
        
        logger.info(f"Navigating to {url}...")
        for attempt in range(2):
            try:
                # Use domcontentloaded for faster "ready" state
                self.page.goto(url, timeout=timeout, wait_until="domcontentloaded")
                return
            except Exception as e:
                logger.warning(f"Navigation attempt {attempt+1} failed: {e}")
                if attempt == 1:
                    logger.error(f"Final navigation failure for {url}")
                    raise
