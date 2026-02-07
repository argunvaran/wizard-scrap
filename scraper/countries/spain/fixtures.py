from scraper.base import BaseScraper
import time
import re

class SpainFixturesScraper(BaseScraper):
    def scrape(self, url="https://www.transfermarkt.com.tr/laliga/gesamtspielplan/wettbewerb/ES1?saison_id=2024"):
        print(f"Scraping Spain fixtures from {url}...")
        results = []
        
        try:
            self.start_browser()
            page = self.browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            )
            
            # 1. Navigate
            print("Navigating to URL...") 
            page.goto(url, timeout=60000)
            
            # --- Anti-Popup Shield ---
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
            except: pass

            # 3. Slow & Deep Scroll
            print("Scrolling slowly to ensure ALL data loads...")
            for i in range(30): 
                page.mouse.wheel(0, 800)
                time.sleep(1.2)
            
            # 4. Parse content
            print("Parsing fixture tables...")
            
            boxes = page.query_selector_all("div.box")
            print(f"Found {len(boxes)} potential boxes.")

            for box in boxes:
                headline = box.query_selector(".content-box-headline")
                if not headline: continue
                
                header_text = headline.inner_text().strip().upper()
                
                # Check Turkish "HAFTA" or English "MATCHDAY" depending on site lang
                # If Transfermarkt.com.tr is used, it is HAFTA
                if "HAFTA" not in header_text and "MATCHDAY" not in header_text: continue
                
                week_num = ""
                if "HAFTA" in header_text:
                    week_match = re.search(r'(\d+)\.\s*HAFTA', header_text)
                    week_num = week_match.group(1) if week_match else header_text.replace("HAFTA", "").strip()
                elif "MATCHDAY" in header_text:
                    week_match = re.search(r'MATCHDAY\s*(\d+)', header_text)
                    week_num = week_match.group(1) if week_match else header_text.replace("MATCHDAY", "").strip()
                
                print(f"Processing Week: {week_num}")

                table = box.query_selector("table")
                if not table: continue

                rows = table.query_selector_all("tbody tr")
                
                for row in rows:
                    try:
                        cells = row.query_selector_all("td")
                        if len(cells) < 2: continue 
                        
                        texts = [c.inner_text().strip() for c in cells]
                        
                        date_val = texts[0] if len(texts) > 0 else ""
                        time_val = texts[1] if len(texts) > 1 else ""
                        home_val = ""
                        away_val = ""
                        score_val = ""

                        h_node = row.query_selector(".heim") 
                        a_node = row.query_selector(".gast")
                        
                        if h_node: home_val = h_node.inner_text().strip()
                        if a_node: away_val = a_node.inner_text().strip()

                        # Score Pivot
                        score_idx = -1
                        for i in range(2, len(texts)):
                            if re.search(r'^\d+:\d+$', texts[i]) or texts[i] == "-:-":
                                score_idx = i
                                score_val = texts[i]
                                break
                        
                        if not home_val and score_idx > 0:
                             for k in range(score_idx-1, 1, -1):
                                 if texts[k]: 
                                     home_val = texts[k]
                                     break
                        
                        if not away_val and score_idx != -1:
                             for k in range(score_idx+1, len(texts)):
                                 if texts[k]:
                                     away_val = texts[k]
                                     break
                        
                        if not away_val and len(texts) > 4:
                            if len(texts) >= 7: away_val = texts[6]
                            elif len(texts) >= 5: away_val = texts[4]

                        # Cleanup
                        home_val = re.sub(r'^\(\d+\.\)\s*', '', home_val).strip()
                        away_val = re.sub(r'^\(\d+\.\)\s*', '', away_val).strip()
                        away_val = re.sub(r'\s*\(\d+\.\)$', '', away_val).strip()

                        if score_val == "-:-": score_val = ""
                        
                        if score_val and re.match(r'^\d{1,2}:\d{2}$', score_val):
                             if score_val == time_val:
                                 score_val = ""
                             elif not row.query_selector(".matchresult"):
                                 score_val = ""

                        if home_val and away_val and "???" not in home_val and "???" not in away_val:
                             results.append({
                                "Hafta": f"{week_num}. Hafta",
                                "Tarih": date_val,
                                "Saat": time_val,
                                "Ev Sahibi": home_val,
                                "Skor": score_val,
                                "Misafir": away_val
                            })
                            
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
