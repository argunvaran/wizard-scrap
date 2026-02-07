from difflib import get_close_matches
from data_manager.models import Standing, Fixture, Player, CountryChoices, BilyonerBulletin
from django.db.models import Q

class MatchAnalyzer:
    def __init__(self, match: BilyonerBulletin):
        self.match = match
        self.home_stats = self._get_team_stats(match.country, match.home_team)
        self.away_stats = self._get_team_stats(match.country, match.away_team)
        self.prediction = self._calculate_prediction()

    def _get_team_stats(self, country, team_name):
        """
        Fetches standings and recent form for a team.
        Uses robust 'Reverse Containment' matching to handle dirty prefixes 
        (e.g., finding 'Bologna' inside 'İtalya Serie A Paz 1 Bologna').
        """
        # 1. Standings - Robust Match
        standing = None
        
        # Strategy A: Check if any DB team is inside the Bilyoner team string
        # Fetch all teams for this country to minimize DB hits later? 
        all_teams_in_db = list(Standing.objects.filter(country=country).values_list('team', flat=True))
        
        best_match = None
        max_len = 0
        
        search_name = team_name.lower().strip()
        
        # 1. Exact/Substring Match
        for db_team in all_teams_in_db:
            clean_db = db_team.lower().strip()
            # Check if DB name is inside the messy Bilyoner name OR vice versa
            if clean_db in search_name or search_name in clean_db:
                if len(clean_db) > max_len:
                    max_len = len(clean_db)
                    best_match = db_team
        
        # 2. Fuzzy Match if strict failed
        if not best_match and all_teams_in_db:
            matches = get_close_matches(team_name, all_teams_in_db, n=1, cutoff=0.6)
            if matches:
                best_match = matches[0]

        if best_match:
             standing = Standing.objects.filter(country=country, team=best_match).first()
             # Update clean name for next steps
             clean_team_name = best_match
        else:
             # Strategy B: Fallback to old contains (maybe Bilyoner is cleaner but DB is longer?)
             standing = Standing.objects.filter(country=country, team__icontains=team_name).first()
             clean_team_name = team_name # Use original if fail

        # 2. Recent Form
        # Use the Cleaned Name if found, otherwise original
        recent_fixtures = Fixture.objects.filter(
            Q(country=country) & (Q(home_team__icontains=clean_team_name) | Q(away_team__icontains=clean_team_name))
        ).exclude(score__isnull=True).exclude(score='').order_by('-id')[:5]
        
        return {
            "standing": standing,
            "recent_matches": recent_fixtures,
            "clean_name": clean_team_name
        }

    def _calculate_form_score(self, fixtures, team_name):
        points = 0
        if not fixtures: return 0
        
        for f in fixtures:
            try:
                # Check if score exists and is valid format "H-A"
                if not f.score or '-' not in f.score: continue
                
                parts = f.score.split('-')
                h_goals = int(parts[0])
                a_goals = int(parts[1])
                
                is_home = team_name.lower() in f.home_team.lower()
                
                if is_home:
                    if h_goals > a_goals: points += 3
                    elif h_goals == a_goals: points += 1
                else:
                    if a_goals > h_goals: points += 3
                    elif a_goals == h_goals: points += 1
            except: pass
            
        # Normalize to 0-1 range (max 15 points)
        return points / 15.0

    def _calculate_prediction(self):
        h_stand = self.home_stats.get('standing')
        a_stand = self.away_stats.get('standing')
        
        if not h_stand or not a_stand:
            return {
                "status": "insufficient_data",
                "home_win_prob": 0,
                "draw_prob": 0,
                "away_win_prob": 0,
                "reason": "Lig verisi bulunamadı."
            }

        # --- ALGORITHM V1: SCORING MODEL ---
        
        # Base Strength (Points per Match)
        h_ppm = h_stand.points / max(1, h_stand.played)
        a_ppm = a_stand.points / max(1, a_stand.played)
        
        # Recent Form Impact (Deep Analysis)
        h_form = self._calculate_form_score(self.home_stats.get('recent_matches'), self.home_stats.get('clean_name'))
        a_form = self._calculate_form_score(self.away_stats.get('recent_matches'), self.away_stats.get('clean_name'))
        
        # Weighted Total Score
        # PPM: 40% importance
        # Form: 30% importance
        # Goal Power: 30% importance (handled below)
        
        h_base = (h_ppm * 0.7) + (h_form * 0.3)
        a_base = (a_ppm * 0.7) + (a_form * 0.3)
        
        # Home Advantage (Standard +10-15% roughly)
        # Home Advantage (Standard +15% roughly)
        h_score = h_base * 1.15
        a_score = a_base
        
        # Goal Power
        h_att = h_stand.goals_for / max(1, h_stand.played)
        h_def = h_stand.goals_against / max(1, h_stand.played)
        a_att = a_stand.goals_for / max(1, a_stand.played)
        a_def = a_stand.goals_against / max(1, a_stand.played)
        
        # Expected Goals
        exp_home_goals = (h_att + a_def) / 2
        exp_away_goals = (a_att + h_def) / 2
        
        # Determine Probabilities (Simplified Poisson-like estimation)
        total_strength = h_score + a_score
        h_prob = (h_score / total_strength) * 100
        a_prob = (a_score / total_strength) * 100
        
        # Draw adjustment
        # If teams are close, draw prob increases
        diff = abs(h_prob - a_prob)
        d_prob = 25.0 # Base draw prob
        if diff < 10: d_prob += 5
        
        # Normalize
        norm = h_prob + d_prob + a_prob
        h_prob = (h_prob / norm) * 100
        d_prob = (d_prob / norm) * 100
        a_prob = (a_prob / norm) * 100
        
        # Goals Prediction (Over/Under 2.5)
        total_exp_goals = exp_home_goals + exp_away_goals
        
        # Simple heuristic for Over/Under
        # Avg ~2.5. 
        # If > 2.8 -> High Over prob
        # If < 2.2 -> High Under prob
        
        over_prob = 50.0
        # Scale: 2.5 -> 50%, 3.5 -> 80%, 1.5 -> 20%
        # Diff from 2.5
        diff_goals = total_exp_goals - 2.5
        # Each 0.1 goal diff adds/subs ~3% prob
        over_prob += (diff_goals * 30) 
        
        # Clamp
        over_prob = max(10, min(90, over_prob))
        under_prob = 100.0 - over_prob
        
        # Decision
        prediction = "X"
        if h_prob > 45: prediction = "1"
        if a_prob > 45: prediction = "2"
        if h_prob > 60: prediction = "1 (Banko)"
        if a_prob > 60: prediction = "2 (Banko)"
        
        return {
            "status": "success",
            "home_win_prob": round(h_prob, 1),
            "draw_prob": round(d_prob, 1),
            "away_win_prob": round(a_prob, 1),
            "over_25_prob": round(over_prob, 1),
            "under_25_prob": round(under_prob, 1),
            "total_expected_goals": round(total_exp_goals, 2),
            "predicted_score": f"{round(exp_home_goals):.0f}-{round(exp_away_goals):.0f}",
            "prediction": prediction,
            "home_stats": h_stand,
            "away_stats": a_stand
        }
