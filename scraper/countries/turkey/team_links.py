import json
import os
import time
import re
from scraper.base import BaseScraper

class TurkeyTeamLinksScraper(BaseScraper):
    def scrape(self, url="https://www.mackolik.com/puan-durumu/t%C3%BCrkiye-s%C3%BCper-lig/482ofyysbdbeoxauk19yg7tdt"):
        team_links = []
        try:
            print(f"Navigating to {url} to extract team links...")
            self.navigate(url)
            
            # Wait for table
            self.page.wait_for_selector("table tbody tr td", timeout=30000)

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
                print("Standings table not found!")
                return []

            rows = target_table.locator("tbody tr").all()
            print(f"Found {len(rows)} rows. Extracting links...")

            base_domain = "https://www.mackolik.com"

            for i, row in enumerate(rows):
                cells = row.locator("td").all()
                if len(cells) < 3: 
                    print(f"Row {i} skipped: not enough cells")
                    continue

                # Cell 2 has the team name and link
                team_cell = cells[2]
                team_name = team_cell.inner_text().strip()
                # print(f"Row {i} Team: {team_name}") # Debug
                
                # Find anchor - try multiple strategies
                link_el = team_cell.locator("a").first
                if link_el.count() == 0:
                     # Try searching in the whole row if cell index is wrong?
                     # No, sticking to cell 2 for now but printing debug
                     print(f"   -> No link found for {team_name}")
                     continue
                     
                raw_href = link_el.get_attribute("href")
                # print(f"   -> Raw Href: {raw_href}")
                
                if raw_href:
                    full_link = raw_href
                    if not full_link.startswith("http"):
                        full_link = base_domain + raw_href
                    
                    # Convert to Squad (Kadro) link
                    parts = raw_href.strip('/').split('/')
                    
                    # Find where 'takim' is
                    try:
                        takim_idx = parts.index('takim')
                    except ValueError:
                        print(f"   -> 'takim' not found in URL: {raw_href}")
                        continue
                        
                    # We need at least slug and ID after 'takim'
                    # Pattern: .../takim/{slug}/{id} OR .../takim/{slug}/section/{id}
                    if len(parts) > takim_idx + 1:
                        slug = parts[takim_idx + 1]
                        team_id = parts[-1] 
                        
                        # Construct: /takim/{slug}/kadro/{id}
                        kadro_href = f"/takim/{slug}/kadro/{team_id}"
                        kadro_full_url = base_domain + kadro_href
                        
                        print(f"Extracted: {team_name} -> {kadro_full_url}")
                        
                        team_links.append({
                            "team": team_name,
                            "url": kadro_full_url
                        })
                    else:
                        print(f"   -> URL too short: {raw_href}")
            
            # Save to JSON
            self.save_json(team_links)
            
            return team_links

        except Exception as e:
            print(f"Error extracting team links: {e}")
            return []
        finally:
            self.close_browser()

    def save_json(self, data):
        # Save to data/turkey_team_links.json
        folder = "c:/Code/web_scraper_0/data"
        if not os.path.exists(folder):
            os.makedirs(folder)
            
        path = os.path.join(folder, "turkey_team_links.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Saved {len(data)} team links to {path}")
