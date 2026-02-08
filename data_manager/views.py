from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from .models import Player, Standing, Fixture, CountryChoices, BilyonerBulletin
from .forms import CountryFilterForm
import sqlite3
import os

# SAFETY: Allow synchronous DB access even if an async loop (Playwright) is detected in the thread.
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

# --- AUTHENTICATION ---
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def index(request):
    return render(request, 'index.html')

# --- DASHBOARD & BROWSING ---
@login_required
def dashboard(request):
    stats = {
        'turkey': {
            'players': Player.objects.filter(country=CountryChoices.TURKEY).count(),
            'standing': Standing.objects.filter(country=CountryChoices.TURKEY).exists(),
            'fixtures': Fixture.objects.filter(country=CountryChoices.TURKEY).count()
        },
        'england': {
            'players': Player.objects.filter(country=CountryChoices.ENGLAND).count(),
            'standing': Standing.objects.filter(country=CountryChoices.ENGLAND).exists(),
            'fixtures': Fixture.objects.filter(country=CountryChoices.ENGLAND).count()
        },
        'spain': {
            'players': Player.objects.filter(country=CountryChoices.SPAIN).count(),
            'standing': Standing.objects.filter(country=CountryChoices.SPAIN).exists(),
            'fixtures': Fixture.objects.filter(country=CountryChoices.SPAIN).count()
        },
        'italy': {
            'players': Player.objects.filter(country=CountryChoices.ITALY).count(),
            'standing': Standing.objects.filter(country=CountryChoices.ITALY).exists(),
            'fixtures': Fixture.objects.filter(country=CountryChoices.ITALY).count()
        }
    }
    return render(request, 'dashboard.html', {'stats': stats})

@login_required
def listings(request, data_type):
    """
    Generic view for Standings, Fixtures, and Players.
    data_type: 'standings', 'fixtures', 'players'
    """
    form = CountryFilterForm(request.GET)
    selected_country = request.GET.get('country', 'ALL')
    
    queryset = None
    model_class = None
    template_name = ""

    if data_type == 'standings':
        model_class = Standing
        template_name = 'standings.html'
    elif data_type == 'fixtures':
        model_class = Fixture
        template_name = 'fixtures.html'
    elif data_type == 'players':
        model_class = Player
        template_name = 'players.html'
    else:
        return redirect('dashboard')

    if selected_country and selected_country != 'ALL':
        queryset = model_class.objects.filter(country=selected_country)
    else:
        queryset = model_class.objects.all()

    # Optimization
    if data_type == 'standings':
        queryset = queryset.order_by('country', 'rank')
    elif data_type == 'fixtures':
        queryset = queryset.order_by('country', '-id') # or week
    elif data_type == 'players':
        queryset = queryset.order_by('country', 'team_name', 'jersey_number')[:200] # Limit for performance

    context = {
        'form': form,
        'data_type': data_type,
        'items': queryset,
        'selected_country': selected_country,
        'user': request.user  # Explicitly pass user
    }
    return render(request, template_name, context)

@login_required
def bulletin(request):
    """
    View to display Bilyoner betting bulletin.
    """
    form = CountryFilterForm(request.GET)
    selected_country = request.GET.get('country', 'ALL')
    
    queryset = BilyonerBulletin.objects.all()
    
    if selected_country and selected_country != 'ALL':
        queryset = queryset.filter(country=selected_country)
        
    # Order by country then time
    queryset = queryset.order_by('country', 'match_time')
    
    context = {
        'form': form,
        'matches': queryset,
        'selected_country': selected_country
    }
    return render(request, 'bulletin.html', context)

# --- IMPORT HUB ---
@login_required
def import_hub(request):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(base_dir)
    scraper_db_path = os.path.join(project_root, "scraper_data.db")
    
    available_tables = []
    
    if os.path.exists(scraper_db_path):
        try:
            conn = sqlite3.connect(scraper_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]
            
            for t in tables:
                # Basic categorization based on name
                cat = "Diğer"
                country = "Bilinmiyor"
                
                lower_t = t.lower()
                if "turkey" in lower_t or "tr_" in lower_t: country = "Türkiye"
                elif "england" in lower_t: country = "İngiltere"
                elif "spain" in lower_t: country = "İspanya"
                elif "italy" in lower_t: country = "İtalya"
                
                if "standings" in lower_t or "puan" in lower_t or "lig" in lower_t: cat = "Puan Durumu"
                elif "fixtures" in lower_t or "fikstur" in lower_t: cat = "Fikstür"
                elif "squads" in lower_t or "kadro" in lower_t: cat = "Kadro"
                elif "bulletin" in lower_t: cat = "Bülten"
                
                # Get Row Count
                cursor.execute(f"SELECT COUNT(*) FROM {t}")
                count = cursor.fetchone()[0]
                
                available_tables.append({
                    'name': t,
                    'country': country,
                    'category': cat,
                    'count': count
                })
            conn.close()
        except Exception as e:
            messages.error(request, f"DB Error: {e}")

    return render(request, 'import_hub.html', {'tables': available_tables})

@login_required
def sync_data(request):
    if request.method != 'POST':
        return redirect('import_hub')
        
    selected_tables = request.POST.getlist('selected_tables')
    if not selected_tables:
        messages.warning(request, "Tablo seçilmedi.")
        return redirect('import_hub')

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(base_dir)
    scraper_db_path = os.path.join(project_root, "scraper_data.db")
    
    try:
        conn = sqlite3.connect(scraper_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        imported_count = 0
        
        def get_val(row, keys, default=None):
            # Helper to find first matching key in row (case-insensitive)
            # row.keys() handles sqlite3.Row if iterated properly
            available_keys = row.keys()
            for k in keys:
                for ak in available_keys:
                    if k.lower() == ak.lower():
                        return row[ak]
            return default

        for table_name in selected_tables:
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            # Auto-detect Country and Type
            t_lower = table_name.lower()
            
            target_country = CountryChoices.TURKEY
            if "england" in t_lower: target_country = CountryChoices.ENGLAND
            elif "spain" in t_lower: target_country = CountryChoices.SPAIN
            elif "italy" in t_lower: target_country = CountryChoices.ITALY
            
            # 1. STANDINGS
            if "standings" in t_lower or "_lig" in t_lower:
                Standing.objects.filter(country=target_country).delete()
                
                for row in rows:
                    Standing.objects.create(
                        country=target_country,
                        rank=get_val(row, ['rank', '#'], 0),
                        team=get_val(row, ['team', 'takım', 'Takım', 'Team'], 'Unknown'),
                        played=get_val(row, ['played', 'O', 'Oynadığı'], 0),
                        won=get_val(row, ['won', 'G', 'Galibiyet'], 0),
                        drawn=get_val(row, ['drawn', 'B', 'Beraberlik'], 0),
                        lost=get_val(row, ['lost', 'M', 'Mağlubiyet'], 0),
                        goals_for=get_val(row, ['goals_for', 'A', 'Atılan'], 0),
                        goals_against=get_val(row, ['goals_against', 'Y', 'Yenen'], 0),
                        average=get_val(row, ['average', 'AV', 'Av', 'Averaj'], 0),
                        points=get_val(row, ['points', 'P', 'Puan'], 0)
                    )
                    imported_count += 1
                    
            # 2. FIXTURES
            elif "fixtures" in t_lower or "fikstur" in t_lower:
                Fixture.objects.filter(country=target_country).delete()
                for row in rows:
                    Fixture.objects.create(
                        country=target_country,
                        week=get_val(row, ['week', 'Hafta'], ''),
                        date=get_val(row, ['date', 'Tarih'], ''),
                        time=get_val(row, ['time', 'Saat'], ''),
                        home_team=get_val(row, ['home_team', 'Ev Sahibi', 'Ev'], ''),
                        score=get_val(row, ['score', 'Skor'], ''),
                        away_team=get_val(row, ['away_team', 'Misafir', 'Deplasman'], '')
                    )
                    imported_count += 1
                    
            # 3. SQUADS
            elif "squads" in t_lower or "kadro" in t_lower:
                Player.objects.filter(country=target_country).delete()
                for row in rows:
                    Player.objects.create(
                        country=target_country,
                        team_name=get_val(row, ['team_name', 'team', 'Takım'], 'Unknown'),
                        jersey_number=get_val(row, ['jersey_number', 'No', 'Numara'], 0),
                        player_name=get_val(row, ['player_name', 'player', 'Ad', 'Oyuncu'], 'Unknown'),
                        profile_url=get_val(row, ['profile_url', 'url'], ''),
                        position=get_val(row, ['position', 'POZ', 'Pozisyon'], ''),
                        age=get_val(row, ['age', 'Yaş'], 0),
                        matches_played=get_val(row, ['matches_played', 'Maç'], 0),
                        starts=get_val(row, ['starts', 'ilk 11', '11'], 0),
                        goals=get_val(row, ['goals', 'Gol'], 0), 
                        assists=get_val(row, ['assists', 'Asist'], 0),
                        yellow_cards=get_val(row, ['yellow_cards', 'Sarı'], 0),
                        red_cards=get_val(row, ['red_cards', 'Kırmızı'], 0)
                    )
                    imported_count += 1
            
            # 4. BILYONER BULLETIN (New)
            elif "bulletin" in t_lower:
                # We use update_or_create to avoid duplicates, or delete all first?
                # Let's clean up old bulletins to keep it fresh
                BilyonerBulletin.objects.all().delete()
                
                for row in rows:
                    # Map source country string to Choice
                    c_str = get_val(row, ['country'], 'TURKEY')
                    
                    # Normalize country
                    c_choice = CountryChoices.TURKEY
                    if "england" in c_str.upper(): c_choice = CountryChoices.ENGLAND
                    elif "spain" in c_str.upper(): c_choice = CountryChoices.SPAIN
                    elif "italy" in c_str.upper(): c_choice = CountryChoices.ITALY
                    elif "germany" in c_str.upper(): c_choice = "GERMANY" # If added to model choices
                    
                    BilyonerBulletin.objects.create(
                        unique_key=get_val(row, ['unique_key'], f"unknown_{imported_count}"),
                        country=c_choice,
                        league=get_val(row, ['league'], ''),
                        match_time=get_val(row, ['date', 'time', 'match_time'], '00:00'),
                        home_team=get_val(row, ['home_team'], 'Unknown'),
                        away_team=get_val(row, ['away_team'], 'Unknown'),
                        ms_1=get_val(row, ['ms_1'], '-'),
                        ms_x=get_val(row, ['ms_x'], '-'),
                        ms_2=get_val(row, ['ms_2'], '-'),
                        under_2_5=get_val(row, ['under_2_5'], '-'),
                        over_2_5=get_val(row, ['over_2_5'], '-')
                    )
                    imported_count += 1

            else:
                 messages.warning(request, f"Skipped unknown table type: {table_name}")

        conn.close()
        messages.success(request, f"Başarıyla {imported_count} kayıt aktarıldı.")
        
    except Exception as e:
        messages.error(request, f"Hata: {e}")
        
    return redirect('dashboard')

@login_required
def scrape_hub(request):
    """
    Interface to trigger Bilyoner scraping directly from Web App.
    """
    return render(request, 'scrape_hub.html')

@login_required
def run_web_scraper(request):
    """
    Executes the Bilyoner scraper management command (Writing to Staging).
    """
    if request.method == "POST":
        from django.core.management import call_command
        import sys
        from io import StringIO
        
        out = StringIO()
        try:
             # Redirect stdout to capture output
             sys.stdout = out
             call_command('update_bilyoner_bulletin')
             result = out.getvalue()
             messages.success(request, f"Scraping Tamamlandı! Lütfen verileri inceleyip onaylayın.\nSonuç: {result}")
        except Exception as e:
             messages.error(request, f"Hata Oluştu: {e}")
        finally:
             # Restore stdout
             sys.stdout = sys.__stdout__
             
    return redirect('scrape_review')

@login_required
def scrape_review(request):
    """
    Shows the staged data for user approval.
    """
    from .models import BilyonerBulletinStaging
    staging_data = BilyonerBulletinStaging.objects.all().order_by('match_time')
    return render(request, 'scrape_review.html', {'staging_data': staging_data})

@login_required
def publish_scraped_data(request):
    """
    Moves data from Staging to Live.
    """
    if request.method == "POST":
        from .models import BilyonerBulletinStaging
        
        # 1. Clear Live
        BilyonerBulletin.objects.all().delete()
        
        # 2. Move Staging to Live
        staging_items = BilyonerBulletinStaging.objects.all()
        count = 0
        for s in staging_items:
            BilyonerBulletin.objects.create(
                unique_key=s.unique_key,
                country=s.country,
                league=s.league,
                match_time=s.match_time,
                home_team=s.home_team,
                away_team=s.away_team,
                ms_1=s.ms_1,
                ms_x=s.ms_x,
                ms_2=s.ms_2,
                under_2_5=s.under_2_5,
                over_2_5=s.over_2_5
            )
            count += 1
            
        # 3. Clear Staging
        staging_items.delete()
        
        messages.success(request, f"{count} Maç Canlı Bültäne Aktarıldı.")
        return redirect('bulletin')
        
    return redirect('scrape_review')
