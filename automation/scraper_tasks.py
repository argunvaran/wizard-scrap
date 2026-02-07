import sys
import os
import django
from django.db import transaction

# Ensure scraper module is importable
# Assuming standard structure: c:/Code/web_scraper_0/web_app/automation/scraper_tasks.py
# Root is ../../../
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from scraper.engine import ScraperManager
from data_manager.models import Standing, Fixture, Player, CountryChoices

def _get_country_code(country_name):
    country_name = country_name.lower()
    if country_name == 'turkey': return CountryChoices.TURKEY
    if country_name == 'england': return CountryChoices.ENGLAND
    if country_name == 'spain': return CountryChoices.SPAIN
    if country_name == 'italy': return CountryChoices.ITALY
    return CountryChoices.TURKEY

# --- GENERIC FETCH FUNCTIONS ---

def fetch_standings(country, **kwargs):
    engine = ScraperManager()
    data = []
    try:
        url = kwargs.get('url') # Can be None
        # Other potential kwargs
        
        if country == 'turkey': data = engine.scrape_turkey_standings(url)
        elif country == 'england': data = engine.scrape_england_standings(url)
        elif country == 'spain': data = engine.scrape_spain_standings(url)
        elif country == 'italy': data = engine.scrape_italy_standings(url)
        return data
    except Exception as e:
        print(f"Error fetching standings for {country}: {e}")
        return []
    finally:
        engine.close()

def fetch_fixtures(country, **kwargs):
    engine = ScraperManager()
    data = []
    try:
        url = kwargs.get('url')
        season = kwargs.get('season')
        
        # Pass both url and season if applicable
        # Only Turkey supports season explicitly so far, others just take URL
        if country == 'turkey': 
            data = engine.scrape_turkey_fixtures(url=url, season=season)
        elif country == 'england': data = engine.scrape_england_fixtures(url)
        elif country == 'spain': data = engine.scrape_spain_fixtures(url)
        elif country == 'italy': data = engine.scrape_italy_fixtures(url)
        return data
    except Exception as e:
        print(f"Error fetching fixtures for {country}: {e}")
        return []
    finally:
        engine.close()

def fetch_squads(country, **kwargs):
    engine = ScraperManager()
    data = []
    try:
        url = kwargs.get('url')
        if country == 'turkey': data = engine.scrape_turkey_squads(url)
        elif country == 'england': data = engine.scrape_england_squads(url)
        elif country == 'spain': data = engine.scrape_spain_squads(url)
        elif country == 'italy': data = engine.scrape_italy_squads(url)
        return data
    except Exception as e:
        print(f"Error fetching squads for {country}: {e}")
        return []
    finally:
        engine.close()

# --- GENERIC SAVE FUNCTIONS ---

def save_standings(country, data):
    if not data: return False, "No data to save."
    country_code = _get_country_code(country)
    
    try:
        with transaction.atomic():
            Standing.objects.filter(country=country_code).delete()
            objects = []
            for row in data:
                def safe_int(v):
                    try: return int(v)
                    except: return 0
                
                objects.append(Standing(
                    country=country_code,
                    rank=safe_int(row.get('rank')),
                    team=row.get('team', 'Unknown'),
                    played=safe_int(row.get('played')),
                    won=safe_int(row.get('won')),
                    drawn=safe_int(row.get('drawn')),
                    lost=safe_int(row.get('lost')),
                    goals_for=safe_int(row.get('goals_for')),
                    goals_against=safe_int(row.get('goals_against')),
                    average=safe_int(row.get('average')),
                    points=safe_int(row.get('points'))
                ))
            Standing.objects.bulk_create(objects)
        return True, f"Saved {len(objects)} standings for {country}."
    except Exception as e:
        return False, str(e)

def save_fixtures(country, data):
    if not data: return False, "No data to save."
    country_code = _get_country_code(country)
    
    try:
        with transaction.atomic():
            Fixture.objects.filter(country=country_code).delete()
            objects = []
            for row in data:
                # Handle possible key variations (Turkish vs English)
                # Turkey, England, Spain scrapers return Turkish keys: Hafta, Tarih, Saat, Ev Sahibi, Skor, Misafir
                # Italy might be English or Turkish depending on implementation.
                
                week_val = row.get('week') or row.get('Hafta') or ''
                date_val = row.get('date') or row.get('Tarih') or ''
                time_val = row.get('time') or row.get('Saat') or ''
                home_val = row.get('home_team') or row.get('Ev Sahibi') or ''
                score_val = row.get('score') or row.get('Skor') or ''
                away_val = row.get('away_team') or row.get('Misafir') or ''

                objects.append(Fixture(
                    country=country_code,
                    week=str(week_val),
                    date=str(date_val),
                    time=str(time_val),
                    home_team=str(home_val),
                    score=str(score_val),
                    away_team=str(away_val)
                ))
            Fixture.objects.bulk_create(objects)
        return True, f"Saved {len(objects)} fixtures for {country}."
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"CRITICAL SAVE ERROR: {e}")
        return False, str(e)

def save_squads(country, data):
    if not data: return False, "No data to save."
    country_code = _get_country_code(country)
    
    try:
        with transaction.atomic():
            # For squads, we might want to be careful about deleting everything?
            # For now, full replace is safer for sync
            Player.objects.filter(country=country_code).delete()
            objects = []
            for row in data:
                def safe_int(v):
                    try: return int(v)
                    except: return 0
                
                objects.append(Player(
                    country=country_code,
                    team_name=row.get('team_name', row.get('team', '')),
                    jersey_number=safe_int(row.get('jersey_number', row.get('number', 0))),
                    player_name=row.get('player_name', row.get('name', 'Unknown')),
                    profile_url=row.get('profile_url', ''),
                    position=row.get('position', ''),
                    age=safe_int(row.get('age', 0)),
                    matches_played=safe_int(row.get('matches_played', row.get('matches', 0))),
                    starts=safe_int(row.get('starts', 0)),
                    goals=safe_int(row.get('goals', 0)),
                    assists=safe_int(row.get('assists', 0)),
                    yellow_cards=safe_int(row.get('yellow_cards', row.get('yellow', 0))),
                    red_cards=safe_int(row.get('red_cards', row.get('red', 0)))
                ))
            Player.objects.bulk_create(objects)
        return True, f"Saved {len(objects)} players for {country}."
    except Exception as e:
        return False, str(e)

# --- SYNC WRAPPERS (Backward Compatibility) ---

def sync_standings(country):
    data = fetch_standings(country)
    if not data: return False, f"No standings found for {country}"
    return save_standings(country, data)

def sync_fixtures(country):
    data = fetch_fixtures(country)
    if not data: return False, f"No fixtures found for {country}"
    return save_fixtures(country, data)

def sync_squads(country):
    data = fetch_squads(country)
    if not data: return False, f"No squads found for {country}"
    return save_squads(country, data)

# --- WRAPPERS FOR TASK REGISTRY ---

def sync_turkey_standings(): return sync_standings('turkey')
def sync_turkey_fixtures(): return sync_fixtures('turkey')
def sync_turkey_squads(): return sync_squads('turkey')

def sync_england_standings(): return sync_standings('england')
def sync_england_fixtures(): return sync_fixtures('england')
def sync_england_squads(): return sync_squads('england')

def sync_spain_standings(): return sync_standings('spain')
def sync_spain_fixtures(): return sync_fixtures('spain')
def sync_spain_squads(): return sync_squads('spain')

def sync_italy_standings(): return sync_standings('italy')
def sync_italy_fixtures(): return sync_fixtures('italy')
def sync_italy_squads(): return sync_squads('italy')
