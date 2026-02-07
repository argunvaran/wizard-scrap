
import math
import random
from collections import Counter
from django.db.models import Q, Sum, Avg
from data_manager.models import Standing, Fixture, Player, BilyonerBulletin

class AdvancedMatchAnalyzer:
    """
    A heavyweight analyzer that uses Monte Carlo simulations, 
    Player individual stats, and weighted form to predict match outcomes.
    """
    
    def __init__(self, match: BilyonerBulletin):
        self.match = match
        self.country = match.country
        self.home_team = match.home_team
        self.away_team = match.away_team
        
        # Data Containers
        self.home_data = self._gather_team_full_data(self.home_team)
        self.away_data = self._gather_team_full_data(self.away_team)
        
        # Results
        self.simulation_results = self._run_monte_carlo_simulation()

    def _gather_team_full_data(self, team_name):
        """
        Aggregates data from Standings, Fixtures, and Players.
        Uses robust name matching.
        """
        # 1. Standing (Base Strength) & Name Cleaning
        standing = None
        all_teams_in_db = Standing.objects.filter(country=self.country).values_list('team', flat=True)
        
        best_match = None
        max_len = 0
        search_name = team_name.lower().strip()
        
        for db_team in all_teams_in_db:
            clean_db = db_team.lower().strip()
            if clean_db in search_name:
                if len(clean_db) > max_len:
                    max_len = len(clean_db)
                    best_match = db_team
                    
        clean_team_name = team_name # default
        if best_match:
             standing = Standing.objects.filter(country=self.country, team=best_match).first()
             clean_team_name = best_match
        else:
             standing = Standing.objects.filter(country=self.country, team__icontains=team_name).first()

        # 2. Recent Form (Last 6 Matches) - Weighted
        # Use Clean Name
        recent_fixtures = Fixture.objects.filter(
            Q(country=self.country) & (Q(home_team__icontains=clean_team_name) | Q(away_team__icontains=clean_team_name))
        ).order_by('-id')[:6]
        
        # 3. Player Power (Top 15 players by starts)
        # Use Clean Name
        players = Player.objects.filter(country=self.country, team_name__icontains=clean_team_name).order_by('-starts')[:15]
        
        team_goals_from_players = 0
        squad_experience = 0
        if players:
            team_goals_from_players = sum(p.goals for p in players)
            squad_experience = sum(p.matches_played for p in players) / len(players)
            
        return {
            "name": team_name,
            "standing": standing,
            "fixtures": recent_fixtures,
            "players": players,
            "player_goals_sum": team_goals_from_players,
            "squad_exp": squad_experience
        }

    def _calculate_xg_parameters(self):
        """
        Calculates Expected Goals (lambda) for Home and Away based on complex metrics.
        """
        h_stats = self.home_data
        a_stats = self.away_data
        
        if not h_stats['standing'] or not a_stats['standing']:
            return 1.4, 1.0 # Default if no data (League Avg approx)

        # A. League Position Factor (Logarithmic scale often fits better but linear for simplicity)
        h_st = h_stats['standing']
        a_st = a_stats['standing']
        
        # 1. Base Attack/Defense Ratings per match
        h_atk_base = h_st.goals_for / max(1, h_st.played)
        h_def_base = h_st.goals_against / max(1, h_st.played)
        
        a_atk_base = a_st.goals_for / max(1, a_st.played)
        a_def_base = a_st.goals_against / max(1, a_st.played)
        
        # B. Form Weighting (Last 3 games matter 2x more)
        def calc_form_score(fixtures, team_name):
            score = 0
            total_w = 0
            for i, f in enumerate(fixtures):
                weight = 1.0 + (0.1 * (6-i)) # Older games have less weight? No, 6-i means recent (index 0) is 6.
                is_home = team_name.lower() in f.home_team.lower()
                
                # Parse Score "2-1"
                try:
                    parts = f.score.split('-')
                    h_s, a_s = int(parts[0]), int(parts[1])
                    if is_home:
                        g_for, g_against = h_s, a_s
                    else:
                        g_for, g_against = a_s, h_s
                        
                    # Performance metric: Goal Diff + Result Bonus
                    gd = g_for - g_against
                    match_perf = gd
                    if gd > 0: match_perf += 2 # Win bonus
                    elif gd == 0: match_perf += 0.5 # Draw bonus
                    
                    score += match_perf * weight
                    total_w += weight
                except:
                    pass
            return score / max(1, total_w)

        h_form = calc_form_score(h_stats['fixtures'], self.home_team)
        a_form = calc_form_score(a_stats['fixtures'], self.away_team)
        
        # C. Squad Value / Player Metric Adjustment
        # If one team has significantly more player goals/experience, boost them
        h_p_power = h_stats['player_goals_sum']
        a_p_power = a_stats['player_goals_sum']
        power_ratio = h_p_power / max(1, a_p_power)
        # Cap ratio to avoid blowout predictions on bad data
        power_ratio = max(0.7, min(1.3, power_ratio))

        # D. Combine into xG
        # Home xG = (Home Atk + Away Def)/2 * FormFactor * PowerFactor * HomeAdvantage
        home_adv = 1.20 # 20% boost for home
        
        xg_home = ((h_atk_base + a_def_base) / 2) * (1 + (h_form * 0.1)) * math.sqrt(power_ratio) * home_adv
        xg_away = ((a_atk_base + h_def_base) / 2) * (1 + (a_form * 0.1)) * (1 / math.sqrt(power_ratio))
        
        return max(0.1, xg_home), max(0.1, xg_away)

    def _run_monte_carlo_simulation(self, iterations=10000):
        h_lambda, a_lambda = self._calculate_xg_parameters()
        
        results = {"1": 0, "X": 0, "2": 0}
        scores = []
        
        for _ in range(iterations):
            # Poisson simulation
            h_g = 0
            # Knuth's algorithm for Poisson generation or simpler loop
            L = math.exp(-h_lambda)
            k = 0
            p = 1.0
            while p > L:
                k += 1
                p *= random.random()
            h_g = k - 1
            
            L = math.exp(-a_lambda)
            k = 0
            p = 1.0
            while p > L:
                k += 1
                p *= random.random()
            a_g = k - 1
            
            # Record
            if h_g > a_g: results["1"] += 1
            elif h_g == a_g: results["X"] += 1
            else: results["2"] += 1
            
            # Store score for frequent scorelines (only first 1000 to save memory)
            if len(scores) < 1000:
                scores.append(f"{h_g}-{a_g}")
                
        # Aggregate
        total = iterations
        prob_1 = (results["1"] / total) * 100
        prob_x = (results["X"] / total) * 100
        prob_2 = (results["2"] / total) * 100
        
        most_common_scores = Counter(scores).most_common(3)
        
        return {
            "h_xg": float(f"{h_lambda:.2f}"),
            "a_xg": float(f"{a_lambda:.2f}"),
            "prob_1": prob_1,
            "prob_x": prob_x,
            "prob_2": prob_2,
            "common_scores": most_common_scores,
            "iterations": iterations
        }

    def get_detailed_report(self):
        res = self.simulation_results
        
        # Confidence Calculation
        max_prob = max(res['prob_1'], res['prob_x'], res['prob_2'])
        confidence = "Düşük"
        if max_prob > 55: confidence = "Orta"
        if max_prob > 70: confidence = "Yüksek"
        
        # Key Players Serialization
        def serialize_player(p):
            return {
                'player_name': p.player_name,
                'position': p.position,
                'goals': p.goals,
                'assists': p.assists,
                'matches_played': p.matches_played
            }

        h_key = []
        if self.home_data['players']:
            # Sort by G+A
            sorted_h = sorted(self.home_data['players'], key=lambda x: x.goals + x.assists, reverse=True)[:3]
            h_key = [serialize_player(p) for p in sorted_h]
            
        a_key = []
        if self.away_data['players']:
            sorted_a = sorted(self.away_data['players'], key=lambda x: x.goals + x.assists, reverse=True)[:3]
            a_key = [serialize_player(p) for p in sorted_a]

        prediction = "X"
        if res['prob_1'] > res['prob_2'] and res['prob_1'] > res['prob_x']: prediction = "1"
        elif res['prob_2'] > res['prob_1'] and res['prob_2'] > res['prob_x']: prediction = "2"
        
        # Risk Analysis
        risk_msg = "Maç ortada geçebilir."
        if confidence == "Yüksek": risk_msg = "Favori takımın kazanma şansı çok yüksek."
        elif abs(res['prob_1'] - res['prob_2']) < 10: risk_msg = "Çok riskli maç, sürprize açık."

        return {
            "engine": "Advanced Monte Carlo v1.0",
            "prediction": prediction,
            "confidence": confidence,
            "risk_analysis": risk_msg,
            "probabilities": {
                "home": round(res['prob_1'], 1),
                "draw": round(res['prob_x'], 1),
                "away": round(res['prob_2'], 1)
            },
            "expected_goals": {
                "home": res['h_xg'],
                "away": res['a_xg']
            },
            "likely_scores": [s[0] for s in res['common_scores']],
            "home_key_players": h_key,
            "away_key_players": a_key,
            "home_key_players": h_key,
            "away_key_players": a_key,
            "home_form_data": self.home_data['fixtures'],
            "away_form_data": self.away_data['fixtures'],
            "home_standing": self.home_data['standing'],
            "away_standing": self.away_data['standing'],
            "home_stats": {
                 "goals_for": self.home_data['standing'].goals_for if self.home_data['standing'] else 0,
                 "goals_against": self.home_data['standing'].goals_against if self.home_data['standing'] else 0,
                 "rank": self.home_data['standing'].rank if self.home_data['standing'] else "-",
                 "played": self.home_data['standing'].played if self.home_data['standing'] else 0,
                 "points": self.home_data['standing'].points if self.home_data['standing'] else 0,
                 "average": self.home_data['standing'].average if self.home_data['standing'] else 0,
            },
            "away_stats": {
                 "goals_for": self.away_data['standing'].goals_for if self.away_data['standing'] else 0,
                 "goals_against": self.away_data['standing'].goals_against if self.away_data['standing'] else 0,
                 "rank": self.away_data['standing'].rank if self.away_data['standing'] else "-",
                 "played": self.away_data['standing'].played if self.away_data['standing'] else 0,
                 "points": self.away_data['standing'].points if self.away_data['standing'] else 0,
                 "average": self.away_data['standing'].average if self.away_data['standing'] else 0,
            }
        }
