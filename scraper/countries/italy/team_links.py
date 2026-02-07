import json
import os
import time
from scraper.base import BaseScraper

class ItalyTeamLinksScraper(BaseScraper):
    def scrape(self, url):
        # Default to Serie A Standings
        if not url or "mackolik" not in url:
            url = "https://www.mackolik.com/puan-durumu/italya-serie-a/2025-2026/1r097lpxe0xn03ihb7wi98kao"
            
        print(f"Scraping Italy team links from: {url}")
        team_links = []
        
        try:
            self.start_browser()
            self.navigate(url)
            
            # Increased initial sleep
            time.sleep(5)
            
            # Anti-popup
            try:
                self.page.add_style_tag(content="iframe, .ads-footer, div[class*='sticky'] { display: none !important; }")
                self.page.evaluate("document.querySelectorAll('.fc-consent-root').forEach(e => e.remove())")
            except:
                pass

            # Increased timeout to 30 seconds
            self.page.wait_for_selector("table", timeout=30000)
            
            # Select rows - containing '/takim/'
            links = self.page.locator("table tbody tr td a[href*='/takim/']").all()
            
            print(f"Found {len(links)} potential team links.")
            
            seen_slugs = set()
            base_domain = "https://www.mackolik.com"

            for link_el in links:
                try:
                    raw_href = link_el.get_attribute("href")
                    team_name = link_el.inner_text().strip()
                    
                    if not raw_href or not team_name:
                        continue

                    # raw_href: /takim/inter/3...
                    parts = raw_href.split('/')
                    
                    if 'takim' in parts:
                        takim_idx = parts.index('takim')
                        if len(parts) > takim_idx + 1:
                            slug = parts[takim_idx + 1]
                            team_id = parts[-1]
                            
                            if slug not in seen_slugs and team_id:
                                seen_slugs.add(slug)
                                
                                kadro_href = f"/takim/{slug}/kadro/{team_id}"
                                kadro_full_url = base_domain + kadro_href
                                
                                team_links.append({
                                    "team": team_name,
                                    "url": kadro_full_url
                                })
                                print(f"   + {team_name}: {kadro_full_url}")

                except Exception as loop_e:
                    print(f"Error parsing link: {loop_e}")

            self.save_json(team_links)
            return team_links

        except Exception as e:
            print(f"Error extracting Italy team links: {e}")
            return []
        finally:
            self.close_browser()

    def save_json(self, data):
        folder = "c:/Code/web_scraper_0/data"
        if not os.path.exists(folder):
            os.makedirs(folder)
            
        path = os.path.join(folder, "italy_team_links.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Saved {len(data)} Italy team links to {path}")
