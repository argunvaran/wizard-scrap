import json
import os
import time
from scraper.base import BaseScraper
from scraper.countries.england.team_links import EnglandTeamLinksScraper

class EnglandTeamsScraper(BaseScraper):
    def scrape(self, url):
        # 1. Check/Generate Links
        json_path = "c:/Code/web_scraper_0/data/england_team_links.json"
        
        if not os.path.exists(json_path):
            print("Team links not found. Extracting from Standings first...")
            standings_url = "https://www.mackolik.com/puan-durumu/ingiltere-premier-lig/2kwbbcootiqqgmrzs6o5inle5"
            link_scraper = EnglandTeamLinksScraper()
            link_scraper.scrape(standings_url) 
        
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
                    try:
                        self.page.wait_for_selector("table tbody tr", timeout=10000)
                    except:
                        print(f"   -> Timeout waiting for table: {team_name}")
                        continue
                    
                    # Find Squad Table
                    tables = self.page.locator("table").all()
                    squad_table = None
                    
                    for table in tables:
                        headers = table.locator("thead th").all_inner_texts()
                        if any("Oyuncu" in h for h in headers) or any("Yaş" in h for h in headers):
                            squad_table = table
                            break
                    
                    if not squad_table:
                        squad_table = tables[0] if tables else None

                    if not squad_table:
                        print(f"   -> No table found for {team_name}")
                        continue

                    # Extract Players
                    rows = squad_table.locator("tbody tr").all()
                    print(f"   -> Found {len(rows)} players.")

                    for row in rows:
                        cells = row.locator("td").all()
                        texts = [c.inner_text().strip() for c in cells]
                        
                        if len(texts) < 3: continue
                        
                        # Initialize fields
                        p_name = ""
                        p_link = ""
                        
                        # Try to find Name by Bold text or Link
                        link_el = row.locator("a[href*='/futbolcu/']").first
                        if link_el.count() > 0:
                            p_name = link_el.inner_text().strip()
                            p_href = link_el.get_attribute("href")
                            p_link = p_href if p_href.startswith("http") else "https://www.mackolik.com" + p_href
                        
                        if not p_name: 
                            p_name = texts[1] if len(texts) > 1 else texts[0]

                        # Column Mapping based on Mackolik England Squad Table
                        # Usually: [0]No, [1]Name, [2]Country, [3]Pos, [4]Age, [5]Matches, [6]Starts, [7]Goals, [8]Assists, [9]Yellow, [10]Red
                        # We use safe retrieval
                        
                        jersey = texts[0] if len(texts) > 0 else ""
                        # texts[1] is name
                        # texts[2] is country
                        pos = texts[3] if len(texts) > 3 else ""
                        age = texts[4] if len(texts) > 4 else ""
                        matches = texts[5] if len(texts) > 5 else "0"
                        starts = texts[6] if len(texts) > 6 else "0"
                        goals = texts[7] if len(texts) > 7 else "0"
                        assists = texts[8] if len(texts) > 8 else "0"
                        yellow = texts[9] if len(texts) > 9 else "0"
                        red = texts[10] if len(texts) > 10 else "0"

                        # Add to list with consistent keys for the Parser
                        all_players.append({
                            "team_name": team_name,
                            "player_name": p_name,
                            "profile_url": p_link,
                            "jersey_number": jersey,
                            "position": pos,
                            "age": age,
                            "matches_played": matches,
                            "starts": starts,
                            "goals": goals,
                            "assists": assists,
                            "yellow_cards": yellow,
                            "red_cards": red
                        })
                        
                except Exception as team_e:
                    print(f"   -> Error scraping {team_name}: {team_e}")
                    continue

            return all_players
            
        except Exception as e:
             print(f"General Error in EnglandTeamsScraper: {str(e)}")
             return []
        finally:
            self.close_browser()
