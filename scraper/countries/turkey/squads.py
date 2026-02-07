import json
import os
import time
from scraper.base import BaseScraper

class TurkeySquadsScraper(BaseScraper):
    def scrape(self):
        links_path = "c:/Code/web_scraper_0/data/turkey_team_links.json"
        
        if not os.path.exists(links_path):
            # Try generic path if absolute fails
            links_path = os.path.join(os.getcwd(), "data", "turkey_team_links.json")
            if not os.path.exists(links_path):
                print("No team links file found. Please run the link extractor first.")
                return []
            
        with open(links_path, "r", encoding="utf-8") as f:
            teams = json.load(f)
            
        print(f"Loaded {len(teams)} teams. Starting squad scrape...")
        
        flat_data = [] # List of dicts for DB and UI
        
        try:
            self.start_browser()
            
            for i, team in enumerate(teams):
                team_name = team.get("team")
                url = team.get("url")
                
                if not url: 
                    continue
                    
                print(f"[{i+1}/{len(teams)}] Scraping squad for {team_name}...")
                self.navigate(url)
                
                # Wait for table
                try:
                    self.page.wait_for_selector("table", timeout=5000)
                except:
                    print(f"   -> No table found for {team_name}")
                    continue
                
                tables = self.page.locator("table").all()
                
                for table in tables:
                    # Attempt to get headers
                    headers = []
                    header_cells = table.locator("thead tr th").all()
                    if not header_cells:
                        header_cells = table.locator("thead tr td").all()
                        
                    if header_cells:
                        for h in header_cells:
                            text = h.inner_text().strip()
                            if not text:
                                # Safe check for icons/images in header if text is missing
                                try:
                                    html = h.inner_html().lower()
                                    if "sari" in html or "yellow" in html or "card-yellow" in html:
                                        text = "Sarı Kart"
                                    elif "kirmizi" in html or "red" in html or "card-red" in html:
                                        text = "Kırmızı Kart"
                                    elif "shirt" in html or "forma" in html or "t-shirt" in html or "jersey" in html:
                                        text = "Maç" 
                                    elif "ball" in html or "top" in html or "futbol" in html or "soccer" in html or "goal" in html or "icon-ball" in html:
                                        text = "Gol"
                                except:
                                    pass
                            headers.append(text)
                    
                    rows = table.locator("tbody tr").all()
                    
                    for row in rows:
                        cells = row.locator("td").all()
                        if not cells: continue
                        
                        # Find player link to confirm this is a player row
                        link_el = row.locator("a[href*='/futbolcu/']").first
                        if link_el.count() > 0:
                            p_name = link_el.inner_text().strip()
                            p_href = link_el.get_attribute("href")
                            full_url = p_href if p_href.startswith("http") else "https://www.mackolik.com" + p_href
                            
                            row_data = {
                                "Team": team_name,
                                "Player": p_name,
                                "Profile_URL": full_url,
                                "_col_count": len(cells) 
                            }
                            
                            # Map other cells
                            cell_texts = [c.inner_text().strip() for c in cells]
                            
                            # Hybrid Mapping: Use mapped headers if available, otherwise fallback to Col_X
                            # We populate Col_X keys regardless, to ensure fallback logic works
                            for c_idx, txt in enumerate(cell_texts):
                                col_key = f"Col_{c_idx+1}"
                                row_data[col_key] = txt
                                
                                # If we have a matching header for this index, use it too
                                if c_idx < len(headers):
                                    h_text = headers[c_idx]
                                    if h_text:
                                        row_data[h_text] = txt
                            
                            # PARSE DATA HERE
                            clean_row = self._parse_row(row_data)
                            flat_data.append(clean_row)

        except Exception as e:
            print(f"Critical error during scrape: {e}")
        finally:
            self.close_browser()
            self.save_json(flat_data)
            
        return flat_data

    def _parse_row(self, row):
        """
        Cleans and standardizes the row data.
        Maps Turkish headers to English DB-friendly keys.
        """
        parsed = {}
        col_count = row.get("_col_count", 0)
        
        # Mapping Dictionary (Header Name -> DB Key)
        key_map = {
            "Team": "team_name",
            "Player": "player_name",
            "Ad": "player_name",
            "Profile_URL": "profile_url",
            "Forma": "jersey_number",
            "Forma No": "jersey_number",
            "No": "jersey_number",
            "Pozisyon": "position",
            "POZ": "position",
            "Yaş": "age",
            "Maç": "matches_played",
            "Maçlar": "matches_played",
            "İlk 11": "starts",
            "Gol": "goals",
            "Goller": "goals",
            "Asist": "assists",
            "A": "assists",
            "Sarı Kart": "yellow_cards",
            "Kırmızı Kart": "red_cards"
        }

        # 1. First Pass: Map known keys from Headers
        for k, v in row.items():
            clean_k = k.strip()
            if clean_k in key_map:
                new_key = key_map[clean_k]
                parsed[new_key] = v
            elif not k.startswith("Col_") and not k.startswith("_"):
                parsed[clean_k.lower().replace(" ", "_")] = v


        # 2. Second Pass: Fallback to Column Indices (Col_X) if keys are missing
        
        # Scenario 1: 12 Columns (Avatar + No + Ad + Flag + POZ + Yas + Mac + 11 + Gol + Asist + Sari + Kirmizi)
        if col_count == 12:
            if "jersey_number" not in parsed: parsed["jersey_number"] = row.get("Col_2")
            if "position" not in parsed: parsed["position"] = row.get("Col_5")
            if "age" not in parsed: parsed["age"] = row.get("Col_6")
            if "matches_played" not in parsed: parsed["matches_played"] = row.get("Col_7")
            if "starts" not in parsed: parsed["starts"] = row.get("Col_8")
            if "goals" not in parsed: parsed["goals"] = row.get("Col_9")
            if "assists" not in parsed: parsed["assists"] = row.get("Col_10")
            if "yellow_cards" not in parsed: parsed["yellow_cards"] = row.get("Col_11")
            if "red_cards" not in parsed: parsed["red_cards"] = row.get("Col_12")

        # Scenario 2: 11 Columns (Avatar + No + Ad + POZ + Yas + Mac + 11 + Gol + Asist + Sari + Kirmizi) - No Flag?
        elif col_count == 11:
            if "jersey_number" not in parsed: parsed["jersey_number"] = row.get("Col_2")
            if "position" not in parsed: parsed["position"] = row.get("Col_4")
            if "age" not in parsed: parsed["age"] = row.get("Col_5")
            if "matches_played" not in parsed: parsed["matches_played"] = row.get("Col_6")
            if "starts" not in parsed: parsed["starts"] = row.get("Col_7")
            if "goals" not in parsed: parsed["goals"] = row.get("Col_8")
            if "assists" not in parsed: parsed["assists"] = row.get("Col_9")
            if "yellow_cards" not in parsed: parsed["yellow_cards"] = row.get("Col_10")
            if "red_cards" not in parsed: parsed["red_cards"] = row.get("Col_11")
            
        elif col_count == 10:
            # 10 Cols: No Avatar, maybe No Flag
            if "jersey_number" not in parsed: parsed["jersey_number"] = row.get("Col_1")
            if "position" not in parsed: parsed["position"] = row.get("Col_3")
            if "age" not in parsed: parsed["age"] = row.get("Col_4")
            if "matches_played" not in parsed: parsed["matches_played"] = row.get("Col_5")
            if "starts" not in parsed: parsed["starts"] = row.get("Col_6")
            if "goals" not in parsed: parsed["goals"] = row.get("Col_7")
            if "assists" not in parsed: parsed["assists"] = row.get("Col_8")
            if "yellow_cards" not in parsed: parsed["yellow_cards"] = row.get("Col_9")
            if "red_cards" not in parsed: parsed["red_cards"] = row.get("Col_10")

        else:
            # Fallback (logic based on observed image)
            # Try to grab what we can from standard indices if exact count unknown
            if "jersey_number" not in parsed: parsed["jersey_number"] = row.get("Col_1")
            if "position" not in parsed: parsed["position"] = row.get("Col_4")
            if "matches_played" not in parsed: parsed["matches_played"] = row.get("Col_6")
            if "goals" not in parsed: parsed["goals"] = row.get("Col_8")

        # 3. Clean Values
        for k, v in parsed.items():
            if isinstance(v, str):
                v = v.strip()
                if v == "-" or v == "": 
                    v = "0"
            parsed[k] = v

        return parsed

    def save_json(self, data):
        folder = "c:/Code/web_scraper_0/data"
        if not os.path.exists(folder):
            os.makedirs(folder)
        path = os.path.join(folder, "turkey_squads_flat.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Saved {len(data)} player records to {path}")
