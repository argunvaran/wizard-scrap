import json
import os
import time
from scraper.base import BaseScraper
from scraper.countries.turkey.team_links import TurkeyTeamLinksScraper

class TurkeyTeamsScraper(BaseScraper):
    def scrape(self, url):
        # 1. Check/Generate Links
        json_path = "c:/Code/web_scraper_0/data/turkey_team_links.json"
        
        if not os.path.exists(json_path):
            print("Team links not found. Extracting from Standings first...")
            # Use the correct Mackolik Standings URL for extraction
            standings_url = "https://www.mackolik.com/puan-durumu/t%C3%BCrkiye-s%C3%BCper-lig/482ofyysbdbeoxauk19yg7tdt"
            link_scraper = TurkeyTeamLinksScraper()
            link_scraper.scrape(standings_url) # This saves the JSON
        
        # 2. Load Links
        if not os.path.exists(json_path):
             print("Error: Failed to generate team links JSON.")
             return []

        with open(json_path, "r", encoding="utf-8") as f:
            team_links = json.load(f)

        print(f"Loaded {len(team_links)} teams. Starting detailed scrape...")
        
        all_players = []
        
        try:
            self.start_browser()
            
            for index, team in enumerate(team_links):
                team_name = team.get("team")
                team_url = team.get("url")
                
                print(f"[{index+1}/{len(team_links)}] Scraping {team_name} from {team_url}")
                
                try:
                    self.page.goto(team_url, timeout=60000)
                    # Handle popups if any
                    self.page.add_style_tag(content="iframe, .ads-footer, div[class*='sticky'] { display: none !important; }")
                    
                    # Wait for table
                    self.page.wait_for_selector("table tbody tr", timeout=10000)
                    
                    # Find Squad Table (usually the biggest one or has 'Oyuncu' header)
                    tables = self.page.locator("table").all()
                    squad_table = None
                    
                    for table in tables:
                        headers = table.locator("thead th").all_inner_texts()
                        if any("Oyuncu" in h for h in headers) or any("Yaş" in h for h in headers):
                            squad_table = table
                            break
                    
                    if not squad_table:
                        # Fallback: Just take the first substantial table
                        squad_table = tables[0] if tables else None

                    if not squad_table:
                        print(f"   -> No table found for {team_name}")
                        continue

                    # Extract Players
                    rows = squad_table.locator("tbody tr").all()
                    print(f"   -> Found {len(rows)} players.")

                    for row in rows:
                        cells = row.locator("td").all()
                        # Mackolik Format usually: [Num, Name(link), Pos, Age, Match, Goal, Assist...]
                        # But columns vary. Let's grab raw texts first.
                        texts = [c.inner_text().strip() for c in cells]
                        
                        if len(texts) < 3: continue
                        
                        # Heuristic Mapping
                        # Usually Name is in cell 1 or 2. 
                        # Let's try to be smart or generic.
                        
                        player_name = ""
                        position = ""
                        age = ""
                        country = ""
                        
                        # Try to find Name by Bold text or Link
                        name_el = row.locator("strong, a, span[class*='name']").first
                        if name_el.count() > 0:
                            player_name = name_el.inner_text().strip()
                        
                        if not player_name: player_name = texts[1] if len(texts)>1 else texts[0]

                        # Add to list
                        all_players.append({
                            "Takım": team_name,
                            "Oyuncu": player_name,
                            "Detaylar": " | ".join(texts) # Temp: Dump all for user inspection first
                        })
                        
                    # Be nice to the server
                    # time.sleep(1) 

                except Exception as team_e:
                    print(f"   -> Error scraping {team_name}: {team_e}")
                    continue

            return all_players
            
        except Exception as e:
             print(f"General Error in TurkeyTeamsScraper: {str(e)}")
             return []
        finally:
            self.close_browser()
