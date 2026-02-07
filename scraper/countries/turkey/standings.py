from scraper.base import BaseScraper
import time

class TurkeyStandingsScraper(BaseScraper):
    def scrape(self, url="https://www.mackolik.com/puan-durumu/t%C3%BCrkiye-s%C3%BCper-lig/482ofyysbdbeoxauk19yg7tdt"):
        data = []
        try:
            self.navigate(url)
            
            # Wait for any table cell
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
                print("Standings table not found!")
                return []

            rows = target_table.locator("tbody tr").all()

            for i, row in enumerate(rows):
                cells = row.locator("td").all()
                text_cells = [c.inner_text().strip() for c in cells]
                
                try:
                    rank = text_cells[0]
                    # Team idx logic
                    team_idx = 2
                    if len(text_cells) > 1 and (not text_cells[1] or text_cells[1].isdigit()): 
                        team_idx = 2
                    else:
                        team_idx = 1
                        
                    team_name = text_cells[team_idx]
                    
                    if len(text_cells) == 12:
                        played = text_cells[3]
                        won = text_cells[5]
                        drawn = text_cells[6]
                        lost = text_cells[7]
                        goals_for = text_cells[8]
                        goals_against = text_cells[9]
                        average = text_cells[10]
                        points = text_cells[11]

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
                        continue

                    if len(text_cells) > team_idx + 8:
                        data_cells = text_cells[team_idx+1:]
                        if len(data_cells) == 9: 
                            played = data_cells[0]
                            won = data_cells[2]
                            drawn = data_cells[3]
                            lost = data_cells[4]
                            goals_for = data_cells[5]
                            goals_against = data_cells[6]
                            average = data_cells[7]
                            points = data_cells[8]
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

                except Exception as row_e:
                    print(f"Row {i} parse error: {row_e}")
        
        except Exception as e:
            print(f"Error in TurkeyStandingsScraper: {str(e)}")
        finally:
            self.close_browser()

        return data
