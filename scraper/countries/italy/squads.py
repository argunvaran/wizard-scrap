import os
import json
import time
import logging
from django.conf import settings
from scraper.base import BaseScraper

logger = logging.getLogger('scraper')

class ItalySquadsScraper(BaseScraper):
    def scrape(self, custom_url=None):
        try:
            links_filename = "italy_team_links.json"
            links_path = os.path.join(settings.BASE_DIR, 'data', links_filename)
            
            logger.info(f"Looking for Italy team links at: {links_path}")
            
            if not os.path.exists(links_path):
                # Fallback CWD
                cwd_path = os.path.join(os.getcwd(), 'data', links_filename)
                logger.info(f"Checking CWD fallback: {cwd_path}")
                if os.path.exists(cwd_path):
                    links_path = cwd_path
                else:
                    logger.error(f"Team links file not found: {links_path}")
                    return []
        except Exception as e:
            logger.error(f"Path error: {e}")
            return []
            
        with open(links_path, "r", encoding="utf-8") as f:
            teams = json.load(f)
            
        logger.info(f"Loaded {len(teams)} teams. Starting Italy squad scrape...")
        
        flat_data = [] 
        
        try:
            self.start_browser()
            
            for i, team in enumerate(teams):
                team_name = team.get("team")
                url = team.get("url")
                
                if not url: continue
                    
                logger.info(f"[{i+1}/{len(teams)}] Scraping squad for {team_name}...")
                try:
                    self.page.goto(url, timeout=120000)
                except:
                    logger.warning(f"   -> Timeout loading {url}")
                    continue
                
                try:
                    self.page.wait_for_selector("table", timeout=10000)
                except:
                    logger.warning(f"   -> No table found for {team_name}")
                    continue
                
                tables = self.page.locator("table").all()
                
                for table in tables:
                    headers = []
                    header_cells = table.locator("thead tr th").all()
                    if not header_cells:
                        header_cells = table.locator("thead tr td").all()
                        
                    if header_cells:
                        for h in header_cells:
                            text = h.inner_text().strip()
                            if not text:
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
                    if not rows: continue
                    if len(rows) < 3: continue 
                    
                    for row in rows:
                        cells = row.locator("td").all()
                        if not cells: continue
                        
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
                            
                            cell_texts = [c.inner_text().strip() for c in cells]
                            
                            for c_idx, txt in enumerate(cell_texts):
                                col_key = f"Col_{c_idx+1}"
                                row_data[col_key] = txt
                                
                                if c_idx < len(headers):
                                    h_text = headers[c_idx]
                                    if h_text:
                                        row_data[h_text] = txt
                            
                            clean_row = self._parse_row(row_data)
                            flat_data.append(clean_row)

        except Exception as e:
            print(f"Critical error during scrape: {e}")
        finally:
            self.close_browser()
            self.save_json(flat_data)
            
        return flat_data

    def _parse_row(self, row):
        parsed = {}
        
        key_map = {
            "Team": "team_name",
            "Player": "player_name", "Ad": "player_name", "Nombre": "player_name", "Nome": "player_name",
            "Profile_URL": "profile_url",
            "Forma": "jersey_number", "No": "jersey_number", "Num": "jersey_number",
            "Pozisyon": "position", "POZ": "position", "Pos": "position",
            "Ülke": "nationality", "Uyruk": "nationality", "Naz.": "nationality",
            "Yaş": "age", "Age": "age", "Età": "age",
            "Maç": "matches_played", "Maçlar": "matches_played", "P.": "matches_played",
            "İlk 11": "starts", "11": "starts",
            "Gol": "goals", "Goller": "goals", "Gols": "goals",
            "Asist": "assists", "A": "assists", "Ast": "assists",
            "Sarı Kart": "yellow_cards",
            "Kırmızı Kart": "red_cards"
        }

        col_count = row.get("_col_count", 0)

        for k, v in row.items():
            clean_k = k.strip()
            if clean_k in key_map:
                new_key = key_map[clean_k]
                parsed[new_key] = v
            elif not k.startswith("Col_") and not k.startswith("_"):
                parsed[clean_k.lower().replace(" ", "_")] = v

        # Fallback to Indices based on col_count
        
        # Scenario 1: 12 Columns (Avatar + No + Ad + Flag + POZ + Yas + Maç + 11 + Gol + Asist + Sari + Kirmizi)
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

        # Scenario 2: 11 Columns (Avatar + No + Ad + POZ + Yas + Maç + 11 + Gol + Asist + Sari + Kirmizi)
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
             # Fallback
            if "jersey_number" not in parsed and "Col_1" in row: parsed["jersey_number"] = row["Col_1"]
            if "position" not in parsed and "Col_4" in row: parsed["position"] = row["Col_4"]
            if "age" not in parsed and "Col_5" in row: parsed["age"] = row["Col_5"]
            if "matches_played" not in parsed and "Col_6" in row: parsed["matches_played"] = row["Col_6"]
            
        for k, v in parsed.items():
            if isinstance(v, str):
                v = v.strip()
                if v == "-" or v == "": v = "0"
            parsed[k] = v

        return parsed

    def save_json(self, data):
        folder = "c:/Code/web_scraper_0/data"
        if not os.path.exists(folder):
            os.makedirs(folder)
        path = os.path.join(folder, "italy_squads_flat.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Saved {len(data)} Italy player records to {path}")
