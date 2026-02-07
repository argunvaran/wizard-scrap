import urllib3
import requests
import json
import logging

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# User provided key
GEMINI_API_KEY = "AIzaSyDNcfzMNd69cUOCEOtzDURqNGob0q5cGzI"
# Using the stable 'latest' alias which is typically the most reliable free tier model (1.5 Flash)
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"

def get_gemini_analysis(match_data, report_data):
    """
    Sends match data to Google Gemini API for professional football analysis.
    """
    try:
        # 1. Construct the Prompt
        # ... logic ...
        prompt = f"""
        Act as a professional football analyst and sports bettor. 
        Analyze the following match details and provide a concise, insightful commentary.
        
        MATCH: {match_data.home_team} vs {match_data.away_team}
        LEAGUE: {match_data.league}
        DATE: {match_data.match_time}
        
        STATS & ODDS:
        - Odds: MS 1 ({match_data.ms_1}), X ({match_data.ms_x}), MS 2 ({match_data.ms_2})
        - AI Model Prediction: {report_data.get('prediction', 'N/A')} (Confidence: {report_data.get('confidence', 'N/A')})
        - Win Probabilities: Home {report_data.get('probabilities', {}).get('home')}%, Draw {report_data.get('probabilities', {}).get('draw')}%, Away {report_data.get('probabilities', {}).get('away')}%
        - Expected Goals (xG): Home {report_data.get('expected_goals', {}).get('home')}, Away {report_data.get('expected_goals', {}).get('away')}
        
        KEY PLAYERS (HOME):
        {json.dumps(report_data.get('home_key_players', []), ensure_ascii=False)}
        
        KEY PLAYERS (AWAY):
        {json.dumps(report_data.get('away_key_players', []), ensure_ascii=False)}
        
        INSTRUCTIONS:
        1. Provide a "Match Narrative": How do you expect the game to flow? (e.g. Defensive struggle, high-scoring shootout).
        2. Identify the "Key Battle": Which player matchup or tactical factor will decide the game?
        3. Give a "Final Verdict": What is the smartest bet? (Moneyline, Over/Under, etc.)
        4. Keep it professional, data-driven, but engaging. Turkish Language.
        5. Max 200 words.
        """
        
        # 2. Prepare Request
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        # 3. Call API
        response = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=20, verify=False)
        
        if response.status_code == 200:
            result = response.json()
            # Extract text
            try:
                analysis_text = result['candidates'][0]['content']['parts'][0]['text']
                # Basic formatting cleanup
                # analysis_text = analysis_text.replace('**', '').replace('*', '-') 
                # Don't strip bold markers, let frontend handle it. Just fix lists.
                analysis_text = analysis_text.replace('* ', '• ')
                return {"success": True, "analysis": analysis_text}
            except (KeyError, IndexError):
                return {"success": False, "error": "Invalid response format from Gemini"}
        else:
            # LOG THE ERROR BODY
            print(f"Gemini 400 Error Body: {response.text}")
            return {"success": False, "error": f"API Error: {response.status_code} - {response.text}"}
            
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        return {"success": False, "error": str(e)}
