from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from data_manager.models import BilyonerBulletin
from .engine import MatchAnalyzer
from .advanced_engine import AdvancedMatchAnalyzer

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
