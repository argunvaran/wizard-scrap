from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from data_manager.models import BilyonerBulletin
from .engine import MatchAnalyzer
from .advanced_engine import AdvancedMatchAnalyzer
import requests
import json
from scraper.bilyoner import BilyonerScraper
from django.http import JsonResponse
from django.contrib.auth.decorators import user_passes_test

@login_required
def analysis_dashboard(request):
    """
    Shows the bulletin matches with a quick analysis overview.
    """
    matches = BilyonerBulletin.objects.all().order_by('match_time')
    analysis_results = []
    
    for match in matches:
        analyzer = MatchAnalyzer(match)
        res = analyzer.prediction
        
        # Determine Value Bet (Simple Logic)
        value_bet = False
        try:
            # Check if implied odd prob < calculated prob
            # Implied = 1 / Odd
            # Value = (Prob * Odd) > 1
            odd_1 = float(match.ms_1) if match.ms_1 != '-' else 0
            if odd_1 > 1 and (res['home_win_prob']/100 * odd_1) > 1.1: # 10% value margin
                 value_bet = "MS 1 Değerli"
        except:
            pass
            
        analysis_results.append({
            'match': match,
            'result': res,
            'value_bet': value_bet
        })
        
    context = {
        'analysis_results': analysis_results
    }
    return render(request, 'analysis/dashboard.html', context)

@login_required
def analyze_match(request, unique_key):
    match = get_object_or_404(BilyonerBulletin, unique_key=unique_key)
    analyzer = MatchAnalyzer(match)
    return render(request, 'analysis/detail.html', {'res': analyzer.prediction, 'match': match})

@login_required
def analyze_match_advanced(request, unique_key):
    match = get_object_or_404(BilyonerBulletin, unique_key=unique_key)
    analyzer = AdvancedMatchAnalyzer(match)
    report = analyzer.get_detailed_report()
    
    return render(request, 'analysis/detail_advanced.html', {
        'report': report,
        'match': match
    })

from django.http import JsonResponse
from .gemini_service import get_gemini_analysis

@login_required
def ask_gemini_analysis(request, unique_key):
    """
    AJAX Endpoint to get Gemini AI analysis
    """
    if request.method == 'POST':
        match = get_object_or_404(BilyonerBulletin, unique_key=unique_key)
        
        # Check cache first
        if match.gemini_analysis:
            return JsonResponse({"success": True, "analysis": match.gemini_analysis})
        
        # We need the report context to give to Gemini
        analyzer = AdvancedMatchAnalyzer(match)
        report = analyzer.get_detailed_report()

        # Prepare simpler data structure for Gemini function
        match_data = type('obj', (object,), {
            'home_team': match.home_team,
            'away_team': match.away_team,
            'league': match.league,
            'match_time': match.match_time,
            'ms_1': match.ms_1, 
            'ms_x': match.ms_x, 
            'ms_2': match.ms_2
        })
        
        # Call Service
        result = get_gemini_analysis(match_data, report)
        
        # Save to DB if successful
        if result.get("success"):
            match.gemini_analysis = result.get("analysis")
            match.save()
        
        return JsonResponse(result)
        
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=400)

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from data_manager.models import BilyonerBulletin

@csrf_exempt
def receive_external_bulletin(request):
    """
    API Endpoint to receive matches from a local scraper (Hybrid Mode).
    Bypasses AWS IP blocks by allowing the user to scrape locally and push here.
    """
    import logging
    import sys
    
    # Configure logger to output to stdout for Docker logs
    logger = logging.getLogger('api_receiver')
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    if request.method == 'POST':
        try:
            remote_ip = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR')
            logger.info(f"🚀 INCOMING PUSH REQUEST from {remote_ip}")
            
            data = json.loads(request.body)
            secret = data.get('secret')
            
            # Authenticate
            if secret != "WFM_PRO_2026_SECURE_SYNC":
                logger.warning(f"❌ UNAUTHORIZED ATTEMPT from {remote_ip}")
                return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)
                
            matches = data.get('matches', [])
            match_count = len(matches)
            logger.info(f"📦 Payload Contains: {match_count} matches")
            
            if not matches:
                logger.warning("⚠️ Empty matches list received.")
                return JsonResponse({"success": False, "error": "No matches provided"})
            
            # Log first match for verification
            first_match = matches[0]
            logger.info(f"🔍 Sample Data (First Match): {first_match.get('home_team')} vs {first_match.get('away_team')} @ {first_match.get('match_time')}")

            # Database Operation
            logger.info("🗑️ Clearing existing BilyonerBulletin table...")
            del_count, _ = BilyonerBulletin.objects.all().delete()
            logger.info(f"✅ Deleted {del_count} old records.")
            
            bulk_list = []
            for m in matches:
                bulk_list.append(BilyonerBulletin(
                    unique_key=m.get('unique_key'),
                    country=m.get('country', 'TURKEY'),
                    league=m.get('league', '-'),
                    match_date=m.get('match_date', ''),
                    match_time=m.get('match_time', '00:00'),
                    home_team=m.get('home_team', 'Unknown'),
                    away_team=m.get('away_team', 'Unknown'),
                    ms_1=m.get('ms_1', '-'),
                    ms_x=m.get('ms_x', '-'),
                    ms_2=m.get('ms_2', '-'),
                    under_2_5=m.get('under_2_5', '-'),
                    over_2_5=m.get('over_2_5', '-')
                ))
            
            logger.info(f"✍️ Bulk creating {len(bulk_list)} new records...")
            objs = BilyonerBulletin.objects.bulk_create(bulk_list)
            logger.info(f"✅ SUCCESSFULLY INSERTED {len(objs)} records into DB.")
            
            # Verify DB state immediately
            final_count = BilyonerBulletin.objects.count()
            logger.info(f"📊 Final DB Count: {final_count}")

            return JsonResponse({"success": True, "count": len(objs)})
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR: {str(e)}", exc_info=True)
            return JsonResponse({"success": False, "error": str(e)}, status=500)
            
    return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)

@login_required
@login_required
def sync_center_view(request):
    """
    Dedicated Page for Data Sync Operations.
    Detects Environment:
    - Local: 127.0.0.1, localhost
    - Cloud: Everything else (e.g. wfm-pro.com, AWS IP)
    """
    host = request.get_host().split(':')[0]
    is_cloud = host not in ['127.0.0.1', 'localhost']
    
    return render(request, 'analysis/sync.html', {
        'is_cloud': is_cloud
    })

@login_required
def scrape_local_and_push_view(request):
    """
    Unified Endpoint for Scraping.
    Auto-Detects Headless Mode based on Environment.
    """
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Yetkisiz Erişim'})
        
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action', 'push_to_aws') 
            target_url = data.get('target_url')
            
            # Detect Environment
            host = request.get_host().split(':')[0]
            is_cloud = host not in ['127.0.0.1', 'localhost']

            # --- ACTION 1: SCRAPE (Local or Server) ---
            if action == 'scrape_local':
                # If on SERVER (Cloud), force Headless (Invisible).
                # If on LOCAL, force Headful (Visible) for debugging and anti-detection.
                use_headless = True if is_cloud else False
                
                scraper = BilyonerScraper()
                # Run scraper with detected mode
                matches = scraper.scrape(headless=use_headless)

                if not matches:
                    return JsonResponse({'success': False, 'error': 'Bilyonerden veri çekilemedi (0 maç).'})
                
                # Save to DB (Local or Server DB, depending on where we are)
                BilyonerBulletin.objects.all().delete()
                bulk_list = []
                for m in matches:
                    bulk_list.append(BilyonerBulletin(
                        unique_key=m.get('unique_key'),
                        country=m.get('country', 'TURKEY'),
                        league=m.get('league', '-'),
                        match_date=m.get('match_date', ''),
                        match_time=m.get('match_time', '00:00'),
                        home_team=m.get('home_team', 'Unknown'),
                        away_team=m.get('away_team', 'Unknown'),
                        ms_1=m.get('ms_1', '-'),
                        ms_x=m.get('ms_x', '-'),
                        ms_2=m.get('ms_2', '-'),
                        under_2_5=m.get('under_2_5', '-'),
                        over_2_5=m.get('over_2_5', '-')
                    ))
                BilyonerBulletin.objects.bulk_create(bulk_list)
                
                msg = "SUNUCU veritabanı güncellendi." if is_cloud else "LOKAL veritabanı güncellendi."
                return JsonResponse({'success': True, 'count': len(matches), 'msg': msg})

            # --- ACTION 2: PUSH TO AWS (Only makes sense from Local) ---
            elif action == 'push_to_aws':
                if is_cloud:
                     return JsonResponse({'success': False, 'error': 'Zaten sunucudasınız! Push işlemi sadece lokalden yapılır.'})

                if not target_url:
                    return JsonResponse({'success': False, 'error': 'Hedef AWS URL girilmedi.'})
                
                local_matches = BilyonerBulletin.objects.all()
                if not local_matches.exists():
                     return JsonResponse({'success': False, 'error': 'Veritabanı boş!'})

                matches_payload = []
                for m in local_matches:
                    matches_payload.append({
                        'unique_key': m.unique_key,
                        'country': m.country,
                        'league': m.league,
                        'match_date': m.match_date,
                        'match_time': m.match_time,
                        'home_team': m.home_team,
                        'away_team': m.away_team,
                        'ms_1': m.ms_1,
                        'ms_x': m.ms_x,
                        'ms_2': m.ms_2,
                        'under_2_5': m.under_2_5,
                        'over_2_5': m.over_2_5,
                    })

                payload = { "secret": "WFM_PRO_2026_SECURE_SYNC", "matches": matches_payload }
                
                try:
                    resp = requests.post(target_url, json=payload, timeout=20)
                    if resp.status_code == 200:
                        remote_res = resp.json()
                        if remote_res.get('success'):
                            return JsonResponse({'success': True, 'count': len(matches_payload), 'msg': f"AWS Başarıyla Güncellendi: {remote_res.get('count')} Maç"})
                        else:
                            return JsonResponse({'success': False, 'error': f"AWS Hatası: {remote_res.get('error')}"})
                    else:
                        return JsonResponse({'success': False, 'error': f"AWS HTTP Hatası: {resp.status_code}"})
                except Exception as net_err:
                    return JsonResponse({'success': False, 'error': f"AWS Bağlantı Hatası: {str(net_err)}"})
            
            else:
                 return JsonResponse({'success': False, 'error': f'Geçersiz işlem: {action}'})

        except Exception as e:
            return JsonResponse({'success': False, 'error': f"İşlem Hatası: {str(e)}"})
            
    return JsonResponse({'success': False, 'error': 'Invalid Method'})
