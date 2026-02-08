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
            logger.info("Initializing Playwright and Browser (AWS Optimized)...")
            self.playwright = sync_playwright().start()
            
            # Minimal, Stealthy Args
            args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1920,1080",
                "--window-position=0,0",
                "--mute-audio",
            ]
            
            self.browser = self.playwright.chromium.launch(
                headless=True, 
            # MINIMAL ARGS - Reduce "Hacker" flags
            # We remove --disable-web-security as it can trigger WAFs
            
            self.browser = self.playwright.chromium.launch(
                headless=True, 
                args=args
            )
            
            # Natural Context - No forced mismatching headers
            context = self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36", 
                locale="tr-TR",
                timezone_id="Europe/Istanbul",
                # ignore_https_errors=True # Removed to be standard
            )
            
            # Basic Stealth only
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)
            
            self.page = context.new_page()
            
            # ENABLE RESOURCES: Real users load images. WAFs invoke 400 if assets aren't requested.
            # self.page.route("**/*.{png,jpg...}", lambda route: route.abort()) 
            
            # Default Timeouts
            self.page.set_default_timeout(60000)
            self.page.set_default_navigation_timeout(60000)
            
            logger.info("Browser launched in NATURAL mode (Full Loading).")

    def scrape(self, custom_url=None):
        # Simplify URL to basics to avoid Query String encoding 400s
        target_url = "https://www.bilyoner.com/iddaa"
        # We will filter the data in Python instead of URL if URL fails
        
        self.start_browser()
        
        try:
            # STEP 1: Warm-up (Visit Home Page First)
            logger.info("Step 1: Visiting Homepage...")
            try:
                self.page.goto("https://www.bilyoner.com/", wait_until="domcontentloaded", timeout=45000)
                time.sleep(5)
            except Exception as e:
                logger.warning(f"Homepage warm-up warning: {e}")

            # STEP 2: Navigate to Target
            logger.info(f"Step 2: Navigating to Target URL: {target_url}")
            try:
                # Load fully to trigger all WAF checks legitimately
                response = self.page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                logger.warning(f"Target navigation failed: {e}")
                response = None

            # Check Status
            if not response or response.status >= 400:
                errors = response.status if response else "Error"
                logger.error(f"Main URL failed with {errors}. Trying simple fallback...")
                
                # Try just base domain if subpath fails
                self.page.goto("https://www.bilyoner.com", wait_until="networkidle", timeout=60000)

            # STEP 3: Wait for Content & Simulate Human
            logger.info("Step 3: Waiting for content hydration...")
            
            # Force a mouse move to trigger any lazy-load or activity sensors
            try:
                self.page.mouse.move(100, 100)
                self.page.mouse.move(500, 500)
            except: pass

            # Wait for specific marker OR generous sleep
            # We look for *any* event row or odds.
            try:
                # Wait for at least one odds button or row
                self.page.wait_for_selector("div", state="attached", timeout=10000)
                time.sleep(5) # Give it 5s raw time for JS execution
            except:
                logger.warning("Selector wait timed out, proceeding with raw dump...")

            # Scroll trigger
            try:
                self.page.evaluate("window.scrollTo(0, 300)")
                time.sleep(1)
            except: pass

            # FINAL CHECK: content presence
            content = self.page.content()
            if "MS 1" not in content and "Oran" not in content:
                title = self.page.title()
                logger.error(f"CRITICAL: No betting content found! Page Title: {title}")
                # Log a snippet of body to see what *is* there (Login screen? access denied?)
                body_text = self.page.inner_text("body")[:500].replace('\n', ' ')
                logger.error(f"Page Preview: {body_text}...")
                return []
            
            logger.info("Content verified (MS 1/Oran found). Starting extraction...")

            # 4. STREAM BASED SCRAPING (Capture All)
            global_events = [] 
            
            # Focus
            try:
                self.page.click("body", position={"x": 100, "y": 100}, force=True)
            except: pass
            
            max_scrolls = 200
            no_change_count = 0
            last_count = 0
            
            logger.info("Starting scroll loop...")
            
            for i in range(max_scrolls):
                # Grab visible text blocks EFFICIENTLY
                chunk = self.page.evaluate("""() => {
                    const items = [];
                    // Target specific rows if possible, else generic divs with constraints
                    const divs = document.querySelectorAll('div');
                    for (let d of divs) {
                        // Only leaf nodes or specific text containers
                        if (d.childElementCount > 2) continue; // Skip containers, get leaves
                        
                        const t = d.innerText;
                        if (!t) continue;
                        const cleanT = t.trim().replace(/\\n/g, " ");
                        
                        if (cleanT.length > 3 && cleanT.length < 300) {
                             if ((cleanT.match(/\\d+\\.\\d{2}/) || cleanT.includes("MS 1")) && cleanT.includes("-")) { 
                                items.push({type: 'match', text: cleanT});
                            } else if (
                                cleanT.match(/premier|lig|serie|la liga/i) || 
                                cleanT.match(/^(bugün|yarın|paz|pzt|sal|çar|per|cum|cmt)/i)
                            ) {
                                items.push({type: 'header', text: cleanT});
                            }
                        }
                    }
                    return items;
                }""")
                
                if chunk:
                    global_events.extend(chunk)
                
                # Intelligent Scroll
                self.page.keyboard.press("PageDown")
                time.sleep(0.3) # Fast scroll
                
                # Log progress periodically
                if i % 50 == 0:
                    current_len = len(global_events)
                    logger.debug(f"Scroll {i}: {current_len} raw items.")
                    if current_len == last_count:
                        no_change_count += 1
                        if no_change_count > 5: # Stop if stuck
                            logger.info("No new data found for 5 checks, stopping scroll.")
                            break
                    else:
                        no_change_count = 0
                    last_count = current_len

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
