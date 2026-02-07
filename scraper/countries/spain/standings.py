from scraper.base import BaseScraper
import time

class SpainStandingsScraper(BaseScraper):
    def scrape(self, url="https://www.mackolik.com/puan-durumu/ispanya-laliga/34pl8szyvrbwcmfkuocjm3r6t"):
        data = []
        try:
            self.start_browser()
            self.navigate(url)
            
            # Additional waits for ads/dynamic
            time.sleep(3)
            
            # Wait for any table
            self.page.wait_for_selector("table tbody tr td", timeout=30000)

            # Locate all tables
            tables = self.page.locator("table").all()
            target_table = None

            for table in tables:
                headers = table.locator("thead th").all_inner_texts()
                cleaned_headers = [h.strip() for h in headers]
                if 'O' in cleaned_headers and 'P' in cleaned_headers:
                    target_table = table
                    break
            
            if not target_table:
                # Fallback to first table if specific headers not match
                target_table = tables[0] if tables else None

            if not target_table:
                print("Standings table not found!")
                return []

            rows = target_table.locator("tbody tr").all()

            for i, row in enumerate(rows):
                cells = row.locator("td").all()
                text_cells = [c.inner_text().strip() for c in cells]
                
                # Check column count
                if len(text_cells) < 8:
                    continue

                # Mackolik columns can vary slightly by view (Genel/İç Saha/Dış Saha)
                # But typically: Rank, ?, Team, Played, Won, Drawn, Lost, GF, GA, Avg, Points
                # Let's try to map dynamically or use fixed indices from Turkey logic if layout is same
                
                # Turkey Logic was: 0:Rank, 2:Team, 3:Played, 7:Won, 8:Drawn, 9:Lost...
                # Let's use a safer extract based on index 0 for Rank and last for Points
                
                try:
                    rank = text_cells[0]
                    # Team idx logic
                    team_idx = 2
                    if len(text_cells) > 1 and (not text_cells[1] or text_cells[1].isdigit()): 
                        team_idx = 2
                    else:
                        team_idx = 1
                        
                    team_name = text_cells[team_idx]
                    
                    if i == 0:
                        print(f"DEBUG ROW 0 CELLS: {text_cells}")
                        print(f"Team Idx: {team_idx}")
                    
                    if len(text_cells) > team_idx + 8:
                        # Extract all cells after team name
                        data_cells = text_cells[team_idx+1:]
                        
                        # Handle Mackolik "Ghost Column" Case
                        # Sometimes structure is: O(Played), Ghost(Av), G(Won), B, M, A, Y, Av, P
                        # Total 9 data columns.
                        if len(data_cells) == 9: 
                            played = data_cells[0]
                            # Skip index 1 (Ghost Av)
                            won = data_cells[2]
                            drawn = data_cells[3]
                            lost = data_cells[4]
                            goals_for = data_cells[5]
                            goals_against = data_cells[6]
                            average = data_cells[7]
                            points = data_cells[8]
                        # Standard Case: O, G, B, M, A, Y, Av, P (8 cols)
                        elif len(data_cells) >= 8:
                            played = data_cells[0]
                            won = data_cells[1]
                            drawn = data_cells[2]
                            lost = data_cells[3]
                            goals_for = data_cells[4]
                            goals_against = data_cells[5]
                            average = data_cells[6]
                            points = data_cells[7]
                        else:
                             print(f"Skipping row {i}: Unexpected col count {len(data_cells)}")
                             continue
    
                        row_data = {
                            "rank": rank,
                            "team": team_name,
                            "played": played,
                            "won": won,
                            "drawn": drawn,
                            "lost": lost,
                            "goals_for": goals_for,
                            "goals_against": goals_against,
                            "average": average,
                            "points": points
                        }
                        data.append(row_data)
                    else:
                        print(f"Skipping row {i}: Not enough columns ({len(text_cells)})")

                except Exception as row_e:
                    print(f"Row {i} parse error: {row_e}")

        except Exception as e:
            print(f"Error in SpainStandingsScraper: {str(e)}")
        finally:
            self.close_browser()

        return data
