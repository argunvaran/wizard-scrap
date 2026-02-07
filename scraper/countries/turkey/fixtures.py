import logging
import time
import re
from scraper.base import BaseScraper

logger = logging.getLogger('scraper')

class TurkeyFixturesScraper(BaseScraper):
    def scrape(self, url=None, season=2024):
        # Default URL structure if URL is not provided
        if not url:
            url = f"https://www.transfermarkt.com.tr/super-lig/gesamtspielplan/wettbewerb/TR1?saison_id={season}"
            
        logger.info(f"Target URL: {url} (Season: {season})")
        logger.info(f"Scraping fixtures from {url}...")
        results = []
        
        try:
            self.start_browser()
            # Use existing context if possible, or create new page
            page = self.page or self.browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            )
            
            # 1. Navigate
            logger.info("Navigating to URL...") 
            page.goto(url, timeout=60000)
            
            # --- CRITICAL: INJECT CSS TO KILL POPUPS aka "Sherlock Mode V2" ---
            logger.info("Injecting Anti-Popup Shield...")
            page.add_style_tag(content="""
                iframe, .sticky-video, #check_video_sticky_mobile, .fc-consent-root, #cmpwrapper, 
                .ads-footer, div[class*="sticky"], div[id*="stick"], div[class*="popup"], 
                div[id*="overlay"], div[id*="modal"], [id*="google_ads"], .adsbygoogle, 
                .banner, div[class*="advertising"], #supersite, [aria-label="Reklam"], 
                [id^="ad-"], div[class*="bottom-bar"], #onetrust-consent-sdk
                { display: none !important; opacity: 0 !important; pointer-events: none !important; width: 0 !important; height: 0 !important; }
            """)
            
            # 3. Slow & Deep Scroll (Increased for full league)
            logger.info("Scrolling slowly to ensure ALL data loads...")
            for i in range(30): # Increased to 30 to cover full season
                page.mouse.wheel(0, 800)
                time.sleep(1.2) # Faster but more steps
            
            # 4. Parse content
            logger.info("Parsing fixture tables...")
            
            # Wait for content to confirm load
            try:
                page.wait_for_selector("div.box", timeout=10000)
            except:
                logger.warning("Timeout waiting for 'div.box'. Page might be empty or blocked.")

            boxes = page.query_selector_all("div.box")
            logger.info(f"Found {len(boxes)} potential boxes.")

            for box in boxes:
                headline = box.query_selector(".content-box-headline")
                if not headline: continue
                
                header_text = headline.inner_text().strip().upper()
                if "HAFTA" not in header_text: continue
                
                week_match = re.search(r'(\d+)\.\s*HAFTA', header_text)
                week_num = week_match.group(1) if week_match else header_text.replace("HAFTA", "").strip()
                
                logger.debug(f"Processing Week: {week_num}")

                table = box.query_selector("table")
                if not table: continue

                rows = table.query_selector_all("tbody tr")
                
                for row in rows:
                    try:
                        cells = row.query_selector_all("td")
                        if len(cells) < 2: continue 
                        
                        # Get full text list for Fallback
                        texts = [c.inner_text().strip() for c in cells]
                        
                        # Data placeholders
                        date_val = texts[0] if len(texts) > 0 else ""
                        time_val = texts[1] if len(texts) > 1 else ""
                        home_val = ""
                        away_val = ""
                        score_val = ""

                        # 1. TEAMS VIA SELECTORS (Robust Method)
                        h_node = row.query_selector("td.heim") 
                        a_node = row.query_selector("td.gast")
                        
                        if h_node: home_val = h_node.inner_text().strip()
                        if a_node: away_val = a_node.inner_text().strip()

                        # 2. SCORE PIVOT (To find score and fallback teams)
                        score_idx = -1
                        for i in range(2, len(texts)):
                            # Check for score like 1:0, 2:1 or placeholder -:-
                            if re.search(r'^\d+:\d+$', texts[i]) or texts[i] == "-:-":
                                score_idx = i
                                score_val = texts[i]
                                break
                        
                        # Fallback Team Extraction
                        if not home_val and score_idx > 0:
                             # Look left of score, skipping empty
                             for k in range(score_idx-1, 1, -1):
                                 if texts[k]: 
                                     home_val = texts[k]
                                     break
                        
                        if not away_val and score_idx != -1:
                             # Look right of score, skipping empty
                             for k in range(score_idx+1, len(texts)):
                                 if texts[k]:
                                     away_val = texts[k]
                                     break
                        
                        # Fallback if no score pivot
                        if not away_val and len(texts) > 4:
                            if len(texts) >= 7 and texts[6]: away_val = texts[6]
                            elif len(texts) >= 5 and texts[4]: away_val = texts[4]

                        # 3. CLEANUP
                        home_val = re.sub(r'^\(\d+\.\)\s*', '', home_val).strip()
                        away_val = re.sub(r'^\(\d+\.\)\s*', '', away_val).strip()
                        away_val = re.sub(r'\s*\(\d+\.\)$', '', away_val).strip()

                        if score_val == "-:-": score_val = ""
                        
                        # Time vs Score Logic
                        if score_val and re.match(r'^\d{1,2}:\d{2}$', score_val):
                             if score_val == time_val:
                                 score_val = ""
                             # If it looks like time but is in score column, verify against class
                             elif not row.query_selector(".matchresult"):
                                 score_val = ""

                        # FILTER CHECK
                        if home_val and away_val and "???" not in home_val and "???" not in away_val:
                             results.append({
                                "Hafta": f"{week_num}. Hafta",
                                "Tarih": date_val,
                                "Saat": time_val,
                                "Ev Sahibi": home_val,
                                "Skor": score_val,
                                "Misafir": away_val
                            })
                        else:
                             # logger.debug(f"Row skipped: H:'{home_val}' A:'{away_val}' S:'{score_val}'")
                             pass
                            
                    except Exception as row_e:
                        logger.error(f"Row Error: {row_e}")
                        continue


            logger.info(f"Scraping complete. Found {len(results)} matches.")
            page.close()
            return results

        except Exception as e:
            logger.error(f"General Error in Fixtures Scraper: {e}", exc_info=True)
            return []
        finally:
            self.close_browser()
