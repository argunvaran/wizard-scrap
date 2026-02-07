from scraper.countries.turkey.standings import TurkeyStandingsScraper
from scraper.countries.turkey.fixtures import TurkeyFixturesScraper
from scraper.countries.turkey.teams import TurkeyTeamsScraper
from scraper.countries.turkey.team_links import TurkeyTeamLinksScraper
from scraper.countries.turkey.squads import TurkeySquadsScraper

from scraper.countries.england.standings import EnglandStandingsScraper
from scraper.countries.england.fixtures import EnglandFixturesScraper
from scraper.countries.england.teams import EnglandTeamsScraper
from scraper.countries.england.team_links import EnglandTeamLinksScraper
from scraper.countries.england.squads import EnglandSquadsScraper

from scraper.countries.spain.standings import SpainStandingsScraper
from scraper.countries.spain.fixtures import SpainFixturesScraper
from scraper.countries.spain.team_links import SpainTeamLinksScraper
from scraper.countries.spain.squads import SpainSquadsScraper

class ScraperManager:
    """
    Pure Scraper Manager.
    No longer interacts with SQLite DB directly.
    Returns data lists to be saved by the Web App.
    """
    def __init__(self):
        pass

    # --- TURKEY ---
    def scrape_turkey_standings(self, url=None):
        scraper = TurkeyStandingsScraper()
        return scraper.scrape(url) if url else scraper.scrape()

    def scrape_turkey_fixtures(self, url=None):
        scraper = TurkeyFixturesScraper()
        return scraper.scrape(url) if url else scraper.scrape()

    def scrape_turkey_teams(self, url=None):
        scraper = TurkeyTeamsScraper()
        return scraper.scrape(url) if url else scraper.scrape()

    def scrape_turkey_team_links(self, url=None):
        scraper = TurkeyTeamLinksScraper()
        return scraper.scrape(url) if url else scraper.scrape()

    def scrape_turkey_squads(self, url=None):
        return TurkeySquadsScraper().scrape()

    # --- ENGLAND ---
    def scrape_england_standings(self, url=None):
        scraper = EnglandStandingsScraper()
        return scraper.scrape(url) if url else scraper.scrape()

    def scrape_england_fixtures(self, url=None):
        scraper = EnglandFixturesScraper()
        return scraper.scrape(url) if url else scraper.scrape()

    def scrape_england_teams(self, url=None):
        scraper = EnglandTeamsScraper()
        return scraper.scrape(url) if url else scraper.scrape()

    def scrape_england_team_links(self, url=None):
        scraper = EnglandTeamLinksScraper()
        return scraper.scrape(url) if url else scraper.scrape()

    def scrape_england_squads(self, url=None):
        return EnglandSquadsScraper().scrape()

    # --- SPAIN ---
    def scrape_spain_standings(self, url=None):
        scraper = SpainStandingsScraper()
        return scraper.scrape(url) if url else scraper.scrape()

    def scrape_spain_fixtures(self, url=None):
        scraper = SpainFixturesScraper()
        return scraper.scrape(url) if url else scraper.scrape()
        
    def scrape_spain_squads(self, url=None):
        # Auto-run link extractor first for reliability
        print("Ensuring Spain team links exist...")
        try:
            SpainTeamLinksScraper().scrape()
        except Exception as e:
            print(f"Warning: Link extraction failed: {e}")
        
        return SpainSquadsScraper().scrape()

    # --- ITALY ---
    def scrape_italy_standings(self, url=None):
        from scraper.countries.italy.standings import ItalyStandingsScraper
        scraper = ItalyStandingsScraper()
        return scraper.scrape(url) if url else scraper.scrape()

    def scrape_italy_fixtures(self, url=None):
        from scraper.countries.italy.fixtures import ItalyFixturesScraper
        scraper = ItalyFixturesScraper()
        return scraper.scrape(url) if url else scraper.scrape()
        
    def scrape_italy_squads(self, url=None):
        from scraper.countries.italy.team_links import ItalyTeamLinksScraper
        from scraper.countries.italy.squads import ItalySquadsScraper
        
        print("Ensuring Italy team links exist...")
        try:
            ItalyTeamLinksScraper().scrape()
        except Exception as e:
            print(f"Warning: Link extraction failed: {e}")
        
        return ItalySquadsScraper().scrape()

    def scrape_bilyoner(self, url=None):
        from scraper.bilyoner import BilyonerScraper
        return BilyonerScraper().scrape()
        
    def close(self):
        pass

