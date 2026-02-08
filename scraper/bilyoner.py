import json
import os
import time
import re
from scraper.base import BaseScraper
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

import logging

logger = logging.getLogger('scraper')

class BilyonerScraper(BaseScraper):
    def start_browser(self):
        if not self.playwright:
            logger.info("Initializing Playwright and Browser...")
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
            # Force HEADLESS
            # Add anti-detection args
            args.extend([
                "--disable-blink-features",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--allow-running-insecure-content"
            ])
            
            self.browser = self.playwright.chromium.launch(
                headless=True, 
                args=args
            )
            logger.info("Browser launched in HEADLESS mode.")
            context = self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                locale="tr-TR",
                timezone_id="Europe/Istanbul"
            )
            
            # Stealth script injection
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.page = context.new_page()
            
            # Allow longer timeouts for AWS (limited resources)
            self.page.set_default_timeout(120000)
            self.page.set_default_navigation_timeout(120000)
            
    def scrape(self, custom_url=None):
        # User specified filtered URL for Multiple Leagues (Turkey, England, Italy, Spain)
        # UPDATED: Using the exact link provided by user: /iddaa instead of /iddaa/futbol
        url = custom_url or "https://www.bilyoner.com/iddaa?lig[]=1%3AT%C3%BCrkiye%20S%C3%BCper%20Lig&lig[]=1%3A%C4%B0ngiltere%20Premier%20Lig&lig[]=1%3A%C4%B0talya%20Serie%20A&lig[]=1%3A%C4%B0spanya%20La%20Liga"
        logger.info(f"Connecting to {url}...")
        self.start_browser()
        
        try:
            # 1. Load Page with Fallback
            loaded = False
            current_url = url
            
            for attempt in range(3):
                try:
                    logger.debug(f"Page load attempt {attempt + 1} ({current_url})")
                    
                    # ENABLE RESOURCES: Removing the block logic to ensure full SPA hydration
                    # self.page.route("**/*.{png,jpg,jpeg,svg,woff,woff2,gif,webp}", lambda route: route.abort())
                    
                    try:
                        self.page.goto(current_url, wait_until="networkidle", timeout=90000)
                    except Exception as nav_e:
                        logger.warning(f"Navigation Timeout for {current_url}: {nav_e}. Trying to proceed anyway...")

                    time.sleep(10) # 10s Wait for full hydration (AWS might be slow)
                    
                    # Try to accept cookies
                    try: 
                        self.page.locator("text=Kabul Et").first.click(timeout=3000)
                    except: pass
                    try:
                         self.page.locator("#onetrust-accept-btn-handler").click(timeout=3000)
                    except: pass
                    
                    # Check for Success Indicator
                    if self.page.locator("div:has-text('MS 1')").count() > 0:
                        loaded = True
                        logger.info("Page loaded successfully (content found).")
                        break
                    
                    # Fallback Logic: Try Base URL on failure
                    logger.warning(f"Content missing on {current_url}. Page Title: {self.page.title()}")
                    if not loaded and attempt == 1:
                        logger.info("Switching to BASE URL as fallback...")
                        current_url = "https://www.bilyoner.com/iddaa/futbol"
                        
                    self.page.reload()
                    
                except Exception as e:
                    logger.error(f"Page load error (attempt {attempt+1}): {e}")
            
            if not loaded:
                logger.error(f"Failed to load page content after retries. Final Title: {self.page.title()}")
                return []

            # 2. STREAM BASED SCRAPING (Capture All, Filter Later)
            global_events = [] 
            
            # Find Scroller and Position Mouse
            # Strategy: Click center of screen to focus the main content area, then use Keyboard PageDown
            # This avoids needing to know the exact class name of the scroller div.
            try:
                # Click center of viewport to focus
                vp = self.page.viewport_size
                if vp:
                    center_x = vp['width'] / 2
                    center_y = vp['height'] / 2
                    self.page.mouse.click(center_x, center_y)
                    logger.debug(f"Clicked center at ({center_x}, {center_y}) to focus.")
                    
                    # Optional: specific click on a match row if reachable to ensure focus matches
                    # self.page.click("div:has-text('MS 1')") 
            except Exception as e:
                logger.warning(f"Focus warning: {e}")

            # SCROLL LOOP - Deep scan
            max_scrolls = 200 # PageDown covers more ground, so fewer steps needed
            logger.info("Starting scroll capture (Keyboard PageDown)...")
            
            for i in range(max_scrolls):
                # Grab visible text blocks
                chunk = self.page.evaluate("""() => {
                    const items = [];
                    const divs = document.querySelectorAll('div');
                    for (let d of divs) {
                        const t = d.innerText.trim().replace(/\\n/g, " ");
                        if (t.length > 3 && t.length < 300) {
                            // Capture match rows (look for odds float OR Missing Odd Pattern)
                            // We need to capture rows like "Barcelona Mallorca — MS 1" even if they have no floats yet
                            if ((t.match(/\\d+\\.\\d{2}/) || t.includes("MS 1")) && t.includes("-")) { 
                                items.push({type: 'match', text: t});
                            } else if (
                                t.match(/premier|lig|serie|la liga/i) || 
                                t.match(/^(bugün|yarın|paz|pzt|sal|çar|per|cum|cmt)/i)
                            ) {
                                items.push({type: 'header', text: t});
                            }
                        }
                    }
                    return items;
                }""")
                
                for item in chunk:
                    global_events.append(item)
                
                # Scroll down using Keyboard, which triggers virtual scrollers better
                self.page.keyboard.press("PageDown")
                time.sleep(0.5)
                
                if i % 20 == 0:
                    logger.debug(f"Scroll step {i}/{max_scrolls}, events captured so far: {len(global_events)}")
                
            logger.info(f"Captured {len(global_events)} raw events. Processing stream...")
            
            # 3. PYTHON STREAM PROCESSING
            # Candidates keyed by Away Team (Last Write Wins if Cleaner)
            candidates = {} 
            
            # Default to Turkey if nothing found
            current_country = "TURKEY" 
            current_league = "Süper Lig"
            current_date_str = "Yarın 18:00" # Default fallback
            
            unique_events = []
            seen_texts = set()
            for e in global_events:
                if e['text'] not in seen_texts:
                    unique_events.append(e)
                    seen_texts.add(e['text'])
            
            for event in unique_events:
                txt = event['text']
                lower_txt = txt.lower()
                
                # HEADER
                if event['type'] == 'header':
                    if "ingiltere" in lower_txt or "premier" in lower_txt:
                        current_country = "ENGLAND"; current_league = "Premier League"
                    elif "ispanya" in lower_txt or "la liga" in lower_txt:
                        current_country = "SPAIN"; current_league = "La Liga"
                    elif "italya" in lower_txt or "serie a" in lower_txt:
                        current_country = "ITALY"; current_league = "Serie A"
                    elif "türkiye" in lower_txt or "süper lig" in lower_txt:
                        current_country = "TURKEY"; current_league = "Süper Lig"
                    
                    date_match = re.search(r'(Bugün|Yarın|Paz|Pzt|Sal|Çar|Per|Cum|Cmt)\s*(\d{2}:\d{2})', txt, re.IGNORECASE)
                    if date_match:
                         current_date_str = f"{date_match.group(1)} {date_match.group(2)}"
                         
                # MATCH
                elif event['type'] == 'match':
                    row_country = current_country
                    row_league = current_league
                    
                    if "ingiltere" in lower_txt or "premier" in lower_txt: row_country = "ENGLAND"; row_league = "Premier League"
                    elif "ispanya" in lower_txt or "la liga" in lower_txt: row_country = "SPAIN"; row_league = "La Liga"
                    elif "italya" in lower_txt or "serie a" in lower_txt: row_country = "ITALY"; row_league = "Serie A"
                    elif "türkiye" in lower_txt or "süper lig" in lower_txt: row_country = "TURKEY"; row_league = "Süper Lig"
                    
                    clean_txt = re.sub(r'İngiltere Premier Lig|Premier League|İtalya Serie A|İspanya La Liga|Türkiye Süper Lig', "", txt, flags=re.IGNORECASE).strip()
                    final_date_str = current_date_str

                    # Check for explicit date "07.02.2026 14:30"
                    explicit_date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})\s*(\d{2}:\d{2})?', clean_txt)
                    if explicit_date_match:
                        date_val = explicit_date_match.group(1)
                        time_val = explicit_date_match.group(2) if explicit_date_match.group(2) else "00:00"
                        final_date_str = f"{date_val} {time_val}"
                        # Remove date from text
                        clean_txt = re.sub(r'\d{2}\.\d{2}\.\d{4}\s*(\d{2}:\d{2})?', '', clean_txt).strip()

                    # Split Teams/Odds Logic (Robust to Missing "MS 1")
                    ms1_missing = False
                    
                    # 1. Check for "Missing MS 1" pattern (e.g. "Mallorca — MS 1")
                    missing_match = re.search(r'\s[-—–]+\s*(MS\s*1)', clean_txt, re.IGNORECASE)
                    
                    if missing_match:
                        split_idx = missing_match.start()
                        teams_part = clean_txt[:split_idx].strip()
                        odds_part = clean_txt[split_idx:].strip()
                        ms1_missing = True
                    else:
                        # 2. Check for Standard First Float (e.g. " 1.45")
                        float_match = re.search(r'\s(\d+\.\d{2})', clean_txt)
                        if float_match:
                            split_idx = float_match.start()
                            teams_part = clean_txt[:split_idx].strip()
                            odds_part = clean_txt[split_idx:].strip()
                        else:
                            teams_part = clean_txt; odds_part = ""

                    # CLEAN PREFIXES (Iterative)
                    # 1. 20:00 
                    teams_part = re.sub(r'^\d{2}:\d{2}\s+', '', teams_part)
                    # 2. Paz 1 
                    teams_part = re.sub(r'^(Bugün|Yarın|Paz|Pzt|Sal|Çar|Per|Cum|Cmt|Pazar|Pazartesi|Salı|Çarşamba|Perşembe|Cuma|Cumartesi)?\s*\d*\s+', '', teams_part, flags=re.IGNORECASE).strip()
                    # 3. 1.
                    teams_part = re.sub(r'^\d+[\.\s]+', '', teams_part)
                    # 4. Trailing sep
                    teams_part = re.sub(r'\s+[-—–]+\s*$', '', teams_part)

                    # Split Home/Away
                    sep = "-"
                    if " - " in teams_part: sep = " - "
                    elif " – " in teams_part: sep = " – " 
                    
                    team_tokens = teams_part.split(sep)
                    if len(team_tokens) >= 2:
                        home = team_tokens[0].strip()
                        away = team_tokens[1].strip()
                        
                        home = re.sub(r'\d+$', '', home).strip()
                        away = re.sub(r'^\d+', '', away).strip()
                        
                        # Odds extraction
                        ms1, msx, ms2, u25, o25 = "-", "-", "-", "-", "-"
                        floats = re.findall(r'(\d+\.\d{2})', odds_part)
                        
                        if ms1_missing:
                            # MS1 is dashed. Floats start from X.
                            ms1 = "-"
                            if len(floats) >= 1: msx = floats[0]
                            if len(floats) >= 2: ms2 = floats[1]
                            if len(floats) >= 4: u25, o25 = floats[2], floats[3]
                        else:
                            # Standard
                            if len(floats) >= 1: ms1 = floats[0]
                            if len(floats) >= 2: msx = floats[1]
                            if len(floats) >= 3: ms2 = floats[2]
                            if len(floats) >= 5: u25, o25 = floats[3], floats[4]
                        
                        parsed_dt = self.parse_date_str(final_date_str)
                        
                        match_obj = {
                            'unique_key': f"{home}-{away}",
                            'country': row_country,
                            'league': row_league,
                            'home_team': home,
                            'away_team': away,
                            'match_date': parsed_dt['date'],
                            'match_time': parsed_dt['time'],
                            'ms_1': ms1, 'ms_x': msx, 'ms_2': ms2,
                            'under_2_5': u25, 'over_2_5': o25    
                        }
                        
                        # Deduplication Logic
                        if away not in candidates:
                            candidates[away] = match_obj
                        else:
                            existing = candidates[away]
                            if len(home) < len(existing['home_team']):
                                candidates[away] = match_obj

            matches = list(candidates.values())
            logger.info(f"Total Matches Extracted: {len(matches)}")
            return matches

        except Exception as e:
            logger.error(f"Fatal Scraper Error: {e}", exc_info=True)
            return []
        finally:
            if self.playwright: self.playwright.stop()
            
    def parse_date_str(self, date_str):
        if not date_str: return {'date': datetime.now().strftime('%d.%m.%Y'), 'time': '00:00'}
        
        try:
            parts = date_str.strip().split()
            day_token = parts[0].lower()
            time_token = parts[1] if len(parts) > 1 else "00:00"
            
            # Check for direct date format (dd.mm.yyyy)
            if re.match(r'\d{2}\.\d{2}\.\d{4}', day_token):
                return {'date': day_token, 'time': time_token}
                
            now = datetime.now()
            target_date = now.date()
            
            if "yarın" in day_token:
                target_date += timedelta(days=1)
            elif "bugün" in day_token:
                target_date = target_date # Today
            else:
                map_days = {"pzt":0, "sal":1, "çar":2, "car":2, "per":3, "cum":4, "cmt":5, "paz":6}
                key = day_token[:3]
                if key in map_days:
                    target_day_idx = map_days[key]
                    current_day_idx = now.weekday()
                    diff = target_day_idx - current_day_idx
                    if diff < 0: diff += 7
                    target_date += timedelta(days=diff)
            
            return {'date': target_date.strftime('%d.%m.%Y'), 'time': time_token}
        except Exception as e:
            print(f"Date Parse Error: {e}")
            return {'date': datetime.now().strftime('%d.%m.%Y'), 'time': '00:00'}
