from playwright.sync_api import sync_playwright

class BaseScraper:
    def __init__(self):
        self.browser = None
        self.page = None
        self.playwright = None

    def start_browser(self):
        if not self.playwright:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=False)
            self.page = self.browser.new_page()

    def close_browser(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
            self.playwright = None

    def navigate(self, url, timeout=60000):
        if not self.page:
            self.start_browser()
        print(f"Navigating to {url}...")
        self.page.goto(url, timeout=timeout)
