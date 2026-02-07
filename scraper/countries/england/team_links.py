import json
import os
import time
import re
import traceback
from scraper.base import BaseScraper

class EnglandTeamLinksScraper(BaseScraper):
    def scrape(self, url="https://www.mackolik.com/puan-durumu/ingiltere-premier-lig/2kwbbcootiqqgmrzs6o5inle5"):
        team_links = []
        try:
            print(f"Navigating to {url} to extract team links...")
            self.start_browser()
            self.navigate(url)
            
            # Anti-popup
            try:
                self.page.add_style_tag(content="iframe, .ads-footer, div[class*='sticky'] { display: none !important; }")
            except: pass

            # Wait for table
            print("Waiting for standings table...")
            try:
                self.page.wait_for_selector("table tbody tr td", timeout=20000)
            except:
                print("Table load timed out.")
                return []

            # Locate the standings table
            tables = self.page.locator("table").all()
            target_table = None
            for table in tables:
                headers = table.locator("thead th").all_inner_texts()
                cleaned = [h.strip() for h in headers]
                if 'O' in cleaned and 'P' in cleaned:
                    target_table = table
                    break
            
            if not target_table:
                if len(tables) > 0:
                    print("Exact header match failed, using first table...")
                    target_table = tables[0]
                else:
                    print("Standings table not found!")
                    return []

            rows = target_table.locator("tbody tr").all()
            print(f"Found {len(rows)} rows. Extracting links...")

            base_domain = "https://www.mackolik.com"

            for i, row in enumerate(rows):
                cells = row.locator("td").all()
                if len(cells) < 3: 
                    continue

                # Cell 2 typically has the team name and link
                team_cell = cells[2]
                team_name = team_cell.inner_text().strip()
                
                # Find anchor
                link_el = team_cell.locator("a").first
                if link_el.count() == 0:
                     print(f"   -> No link found for {team_name}")
                     continue
                     
                raw_href = link_el.get_attribute("href")
                
                if raw_href:
                    # Convert to Squad (Kadro) link
                    parts = raw_href.strip('/').split('/')
                    
                    if 'takim' in parts:
                        try:
                            takim_idx = parts.index('takim')
                            if len(parts) > takim_idx + 1:
                                slug = parts[takim_idx + 1]
                                team_id = parts[-1] 
                                
                                kadro_href = f"/takim/{slug}/kadro/{team_id}"
                                kadro_full_url = base_domain + kadro_href
                                
                                print(f"   + {team_name} -> {kadro_full_url}")
                                
                                team_links.append({
                                    "team": team_name,
                                    "url": kadro_full_url
                                })
                        except Exception as parse_e:
                             print(f"Error parsing href {raw_href}: {parse_e}")
            
            # Save to JSON
            self.save_json(team_links)
            
            return team_links

        except Exception as e:
            print(f"Error extracting team links: {e}")
            traceback.print_exc()
            return []
        finally:
            self.close_browser()

    def save_json(self, data):
        # Save to data/england_team_links.json
        folder = "c:/Code/web_scraper_0/data"
        if not os.path.exists(folder):
            os.makedirs(folder)
            
        path = os.path.join(folder, "england_team_links.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Saved {len(data)} team links to {path}")
