from scraper.base import BaseScraper
import time
import re

class TurkeyFixturesScraper(BaseScraper):
    def scrape(self, url="https://www.transfermarkt.com.tr/super-lig/gesamtspielplan/wettbewerb/TR1?saison_id=2024"):
        print(f"Scraping fixtures from {url}...")
        results = []
        
        try:
            self.start_browser()
            page = self.browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            )
            
            # 1. Navigate
            print("Navigating to URL...") 
            page.goto(url, timeout=60000)
            
            # --- CRITICAL: INJECT CSS TO KILL POPUPS aka "Sherlock Mode V2" ---
            print("Injecting Anti-Popup Shield...")
            page.add_style_tag(content="""
                iframe, .sticky-video, #check_video_sticky_mobile, .fc-consent-root, #cmpwrapper, 
                .ads-footer, div[class*="sticky"], div[id*="stick"], div[class*="popup"], 
                div[id*="overlay"], div[id*="modal"], [id*="google_ads"], .adsbygoogle, 
                .banner, div[class*="advertising"], #supersite, [aria-label="Reklam"], 
                [id^="ad-"], div[class*="bottom-bar"], #onetrust-consent-sdk
                { display: none !important; opacity: 0 !important; pointer-events: none !important; width: 0 !important; height: 0 !important; }
            """)
            
            # 2. Cookie Handling (Backup)
            try:
                time.sleep(2)
                # Try specific button if it survived CSS (some consent is needed solely for js execution?)
                # Usually better to let CSS hide it.
            except: pass

            # 3. Slow & Deep Scroll (Increased for full league)
            print("Scrolling slowly to ensure ALL data loads...")
            for i in range(30): # Increased to 30 to cover full season
                page.mouse.wheel(0, 800)
                time.sleep(1.2) # Faster but more steps
            
            # 4. Parse content
            print("Parsing fixture tables...")
            
            boxes = page.query_selector_all("div.box")
            print(f"Found {len(boxes)} potential boxes.")

            for box in boxes:
                headline = box.query_selector(".content-box-headline")
                if not headline: continue
                
                header_text = headline.inner_text().strip().upper()
                if "HAFTA" not in header_text: continue
                
                week_match = re.search(r'(\d+)\.\s*HAFTA', header_text)
                week_num = week_match.group(1) if week_match else header_text.replace("HAFTA", "").strip()
                
                print(f"Processing Week: {week_num}")

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
                        # This skips the empty separator <td> cells automatically
                        h_node = row.query_selector(".heim") 
                        a_node = row.query_selector(".gast")
                        
                        if h_node: home_val = h_node.inner_text().strip()
                        if a_node: away_val = a_node.inner_text().strip()

                        # 2. SCORE PIVOT (To find score and fallback teams)
                        # We still need score
                        score_idx = -1
                        for i in range(2, len(texts)):
                            if re.search(r'^\d+:\d+$', texts[i]) or texts[i] == "-:-":
                                score_idx = i
                                score_val = texts[i]
                                break
                        
                        # Fallback Team Extraction (if selectors failed)
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
                        
                        # Fallback if no score pivot (Standard Position with jump)
                        if not away_val and len(texts) > 4:
                            # usually index 4, but if 4 is empty, index 6?
                            if len(texts) >= 7: away_val = texts[6]
                            elif len(texts) >= 5: away_val = texts[4]

                        # 3. CLEANUP
                        home_val = re.sub(r'^\(\d+\.\)\s*', '', home_val).strip()
                        away_val = re.sub(r'^\(\d+\.\)\s*', '', away_val).strip()
                        away_val = re.sub(r'\s*\(\d+\.\)$', '', away_val).strip()

                        if score_val == "-:-": score_val = ""
                        
                        # Time vs Score Logic
                        if score_val and re.match(r'^\d{1,2}:\d{2}$', score_val):
                             if score_val == time_val:
                                 score_val = ""
                             elif not row.query_selector(".matchresult"):
                                 score_val = ""

                        # FILTER CHECK
                        if home_val and away_val and "???" not in home_val and "???" not in away_val:
                             print(f"   -> Match: {home_val} {score_val if score_val else 'vs'} {away_val}")
                             results.append({
                                "Hafta": f"{week_num}. Hafta",
                                "Tarih": date_val,
                                "Saat": time_val,
                                "Ev Sahibi": home_val,
                                "Skor": score_val,
                                "Misafir": away_val
                            })
                        else:
                             print(f"   [SKIP] H:'{home_val}' A:'{away_val}' S:'{score_val}' Raw: {texts}")
                            
                    except Exception as row_e:
                        print(f"Row Error: {row_e}")
                        continue


            print(f"Scraping complete. Found {len(results)} matches.")
            page.close()
            return results

        except Exception as e:
            print(f"General Error: {e}")
            return []
        finally:
            self.close_browser()
