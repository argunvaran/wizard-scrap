import json
import os
import time
from scraper.base import BaseScraper

class SpainTeamLinksScraper(BaseScraper):
    def scrape(self, url):
        # Default to La Liga Standings if generic URL provided or used generally
        if not url or "mackolik" not in url:
            url = "https://www.mackolik.com/puan-durumu/ispanya-laliga/34pl8szyvrbwcmfkuocjm3r6t"
            
        print(f"Scraping Spain team links from: {url}")
        team_links = []
        
        try:
            self.start_browser()
            self.navigate(url)
            
            # Additional wait for dynamic content
            time.sleep(3)
            
            # Handle popups
            try:
                self.page.add_style_tag(content="iframe, .ads-footer, div[class*='sticky'] { display: none !important; }")
                self.page.evaluate("document.querySelectorAll('.fc-consent-root').forEach(e => e.remove())")
            except:
                pass

            # Locate Standings Table
            # Mackolik standings usually in a specific container
            self.page.wait_for_selector("table", timeout=10000)
            
            # Select rows - typically inside tbody
            # We look for links containing '/takim/'
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

                    # raw_href looks like: /takim/real-madrid/bes6q0...
                    # We want: /takim/real-madrid/kadro/bes6q0...
                    
                    # Logic to construct 'kadro' URL
                    parts = raw_href.split('/')
                    # parts -> ['', 'takim', 'real-madrid', 'id']
                    
                    if 'takim' in parts:
                        takim_idx = parts.index('takim')
                        if len(parts) > takim_idx + 1:
                            slug = parts[takim_idx + 1]
                            # Sometimes ID is next, sometimes not. Let's rely on standard structure.
                            # Standard: /takim/{slug}/{id}
                            # Target: /takim/{slug}/kadro/{id}
                            
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

            # Save to JSON
            self.save_json(team_links)
            
            return team_links

        except Exception as e:
            print(f"Error extracting Spain team links: {e}")
            return []
        finally:
            self.close_browser()

    def save_json(self, data):
        folder = "c:/Code/web_scraper_0/data"
        if not os.path.exists(folder):
            os.makedirs(folder)
            
        path = os.path.join(folder, "spain_team_links.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Saved {len(data)} Spain team links to {path}")
