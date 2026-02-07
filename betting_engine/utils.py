from decimal import Decimal
from django.utils import timezone
from data_manager.models import BilyonerBulletin, Fixture
from analysis.engine import MatchAnalyzer
from .models import Coupon, CouponItem
from django.db.models import Q

def generate_coupon(amount):
    """
    Generates top 5 high-confidence coupons, each with a single match.
    Returns a list of created coupons.
    """
    
    candidates = _get_candidates()
    
    # Sort candidates by probability descending
    candidates.sort(key=lambda x: x['prob'], reverse=True)
    
    # Take top 10
    top_picks = candidates[:10]
    
    if not top_picks:
        return []
        
    created_coupons = []
    
    for pick in top_picks:
        # Create separate coupon for each pick
        confidence = float(pick['prob']) * 100 # Already calculated max_prob, convert to percentage for display if needed or keep raw
        
        coupon = Coupon.objects.create(
            amount=amount,
            status='PENDING',
            confidence=confidence
        )
        
        bulletin = pick['bulletin']
        odds = Decimal(str(pick['odds']))
        
        CouponItem.objects.create(
            coupon=coupon,
            match=bulletin,
            home_team=bulletin.home_team,
            away_team=bulletin.away_team,
            match_date=bulletin.match_date,
            match_time=bulletin.match_time,
            league=bulletin.league,
            prediction=pick['pick'],
            odds=odds,
            status='PENDING'
        )
        
        coupon.total_odds = odds
        coupon.potential_return = Decimal(str(float(amount) * float(odds)))
        coupon.save()
        created_coupons.append(coupon)
    
    return created_coupons

def _get_candidates():
    """
    Helper to fetch and rank updated match candidates.
    Returns list of dicts. Now analyzes MS, Over 2.5, Under 2.5.
    """
    bulletins = BilyonerBulletin.objects.filter(
        Q(ms_1__isnull=False) & ~Q(ms_1='-') & ~Q(ms_1='') &
        Q(ms_2__isnull=False) & ~Q(ms_2='-') & ~Q(ms_2='')
    )
    
    # Get list of already played matches/predictions to avoid duplicates
    played_coupons = Coupon.objects.filter(is_played=True)
    played_keys = set()
    
    for pc in played_coupons:
        for item in pc.items.all():
            h = item.home_team.strip().lower()
            a = item.away_team.strip().lower()
            d = item.match_date.strip()
            str_key = f"{h}|{a}|{d}"
            played_keys.add(str_key)
            
    candidates = []

    for bulletin in bulletins:
        analyzer = MatchAnalyzer(bulletin)
        pred = analyzer.prediction  # Returns dict with probabilities
        
        # Probabilities
        h_prob = pred.get('home_win_prob', 0)
        a_prob = pred.get('away_win_prob', 0)
        over_prob = pred.get('over_25_prob', 0)
        under_prob = pred.get('under_25_prob', 0)
        
        # 3 Potential Picks per match: MS Best, Over, Under.
        
        # 1. Best MS Pick
        ms_pick = None
        ms_prob = 0
        ms_odds = 1.0
        
        try:
            o1 = float(bulletin.ms_1.replace(',', '.'))
        except: o1 = 1.0
        try:
            o2 = float(bulletin.ms_2.replace(',', '.'))
        except: o2 = 1.0
            
        if h_prob > a_prob:
            ms_pick = "MS 1"
            ms_prob = h_prob
            ms_odds = o1
        else:
            ms_pick = "MS 2"
            ms_prob = a_prob
            ms_odds = o2
            
        # 2. Over Pick
        try:
            o_over = float(bulletin.over_2_5.replace(',', '.')) if bulletin.over_2_5 else 1.0
        except: o_over = 1.0
        
        # 3. Under Pick
        try:
            o_under = float(bulletin.under_2_5.replace(',', '.')) if bulletin.under_2_5 else 1.0
        except: o_under = 1.0
        
        # Store all viable options (>50% prob)
        base_match_key = f"{bulletin.home_team}|{bulletin.away_team}|{bulletin.match_date}"
        if base_match_key.lower() in played_keys:
            continue
            
        # Add MS Candidate
        if ms_pick and ms_prob > 40: # threshold
            candidates.append({
                'bulletin': bulletin,
                'pick': ms_pick,
                'prob': ms_prob / 100.0,
                'odds': ms_odds,
                'type': 'MS'
            })
            
        # Add Over Candidate
        if over_prob > 55 and o_over > 1.30:
            candidates.append({
                'bulletin': bulletin,
                'pick': "2,5 Üst",
                'prob': over_prob / 100.0,
                'odds': o_over,
                'type': 'OU'
            })
            
        # Add Under Candidate
        if under_prob > 55 and o_under > 1.30:
            candidates.append({
                'bulletin': bulletin,
                'pick': "2,5 Alt",
                'prob': under_prob / 100.0,
                'odds': o_under,
                'type': 'OU'
            })
            
    return candidates

def generate_target_coupon(investment, target_amount):
    """
    Generates a single coupon attempting to reach target_amount with given investment.
    Uses an accumulator of highest probability matches.
    """
    target_multiplier = float(target_amount) / float(investment)
    
    candidates = _get_candidates()
    # Sort by probability DESC
    candidates.sort(key=lambda x: x['prob'], reverse=True)
    
    if not candidates:
        return None
        
    accumulator_items = []
    current_odds = 1.0
    combined_prob = 1.0
    used_matches = set()
    
    # Greedy approach: Take best matches until we hit target
    for pick in candidates:
        if current_odds >= target_multiplier:
            break
            
        # Avoid duplicate matches (e.g. don't pick MS 1 and Over 2.5 for same match in same coupon if they conflict or just to be safe)
        match_id = pick['bulletin'].id
        if match_id in used_matches:
            continue
            
        # Add to accumulator
        accumulator_items.append(pick)
        current_odds *= pick['odds']
        combined_prob *= pick['prob']
        used_matches.add(match_id)
        
    # Create the coupon
    coupon = Coupon.objects.create(
        amount=investment,
        status='PENDING',
        confidence=combined_prob * 100, # Approximate combined confidence
    )
    
    for pick in accumulator_items:
        bulletin = pick['bulletin']
        odds = Decimal(str(pick['odds']))
        
        CouponItem.objects.create(
            coupon=coupon,
            match=bulletin,
            home_team=bulletin.home_team,
            away_team=bulletin.away_team,
            match_date=bulletin.match_date,
            match_time=bulletin.match_time,
            league=bulletin.league,
            prediction=pick['pick'],
            odds=odds,
            status='PENDING'
        )
        
    coupon.total_odds = Decimal(str(current_odds))
    coupon.potential_return = Decimal(str(float(investment) * current_odds))
    coupon.save()
    
    return coupon

def generate_legendary_coupon(investment=50, target_odds=100.0):
    """
    [EFSANE KUPON]
    Generates a single coupon with ~100x odds.
    Uses a mix of MS and Over/Under bets.
    """
    candidates = _get_candidates()
    
    # Filter for value bets (Odds > 1.45 to build multiplier faster, but Prob > 50%)
    value_picks = [c for c in candidates if c['odds'] >= 1.45 and c['prob'] >= 0.50]
    
    # Sort by Value (Odds * Prob) -> Expected Value
    value_picks.sort(key=lambda x: (x['odds'] * x['prob']), reverse=True)
    
    if not value_picks:
        return None
        
    accumulator_items = []
    current_odds = 1.0
    combined_prob = 1.0
    used_matches = set()
    
    for pick in value_picks:
        if current_odds >= target_odds:
            break
        
        match_id = pick['bulletin'].id
        if match_id in used_matches:
            continue
            
        accumulator_items.append(pick)
        current_odds *= pick['odds']
        combined_prob *= pick['prob']
        used_matches.add(match_id)
        
    # Validation: If we didn't reach close to 100 (e.g. at least 50), it might not be legitimate "Legendary"
    if current_odds < 20.0:
        # Try adding lower probability but high odd matches if we are short?
        # For now, just return what we have.
        pass
        
    coupon = Coupon.objects.create(
        amount=investment,
        status='PENDING',
        confidence=combined_prob * 100,
        is_archived=False
    )
    
    for pick in accumulator_items:
        bulletin = pick['bulletin']
        odds = Decimal(str(pick['odds']))
        
        CouponItem.objects.create(
            coupon=coupon,
            match=bulletin,
            home_team=bulletin.home_team,
            away_team=bulletin.away_team,
            match_date=bulletin.match_date,
            match_time=bulletin.match_time,
            league=bulletin.league,
            prediction=pick['pick'],
            odds=odds,
            status='PENDING'
        )
        
    coupon.total_odds = Decimal(str(current_odds))
    coupon.potential_return = Decimal(str(float(investment) * current_odds))
    coupon.save()
    
    prediction_summary = ", ".join([f"{p['pick']}" for p in accumulator_items])
    
    return {
        'coupon': coupon,
        'item_count': len(accumulator_items),
        'total_odds': current_odds,
        'prediction_summary': prediction_summary
    }

def generate_guaranteed_trio_hedge(total_investment):
    """
    [3+1 SYSTEM] 
    Selects 3 Solid Matches.
    Creates 4 Coupons:
    1. Single Match A
    2. Single Match B
    3. Single Match C
    4. Combo (A + B + C)
    
    Goal: Optimize stakes so that even if 1 or 2 matches win, we amortize/recover costs, 
    but if all 3 win, we hit big with the combo + singles.
    """
    # 1. Select 3 Solid Candidates (Odds 1.45 - 2.10)
    candidates = _get_candidates()
    
    # Filter for "Solid" range
    solid_picks = []
    for c in candidates:
        if 1.45 <= c['odds'] <= 2.10:
            solid_picks.append(c)
            
    # Sort by probability
    solid_picks.sort(key=lambda x: x['prob'], reverse=True)
    
    # Take top 3
    if len(solid_picks) < 3:
        # Fallback to general pool if strict filter fails
        candidates.sort(key=lambda x: x['prob'], reverse=True)
        solid_picks = candidates[:3]
        
    final_picks = solid_picks[:3]
    
    if len(final_picks) < 3:
        return None
        
    # 2. Calculate Stakes
    # Strategy: 
    # Distribute ~85% to Singles (to cover costs), ~15% to Combo (Bonus)
    # Actually, let's try to balance.
    # Stake per Single = Total * 0.28 (3 * 0.28 = 0.84)
    # Stake Combo = Total * 0.16
    
    stake_single_ratio = Decimal("0.28")
    stake_combo_ratio  = Decimal("0.16")
    
    stake_per_single = total_investment * stake_single_ratio
    stake_combo = total_investment * stake_combo_ratio
    
    coupons = []
    singles_return = Decimal(0)
    
    # Create 3 Single Coupons
    for i, pick in enumerate(final_picks):
        c = Coupon.objects.create(amount=stake_per_single, status='PENDING', confidence=float(pick['prob']) * 100, is_archived=True)
        bulletin = pick['bulletin']
        odds = Decimal(str(pick['odds']))
        
        CouponItem.objects.create(
            coupon=c, match=bulletin, home_team=bulletin.home_team, away_team=bulletin.away_team,
            match_date=bulletin.match_date, match_time=bulletin.match_time, league=bulletin.league,
            prediction=pick['pick'], odds=odds, status='PENDING'
        )
        c.total_odds = odds
        c.potential_return = stake_per_single * odds
        c.save()
        coupons.append(c)
        singles_return += c.potential_return # Max potential from just singles

    # Create 1 Combo Coupon
    c_combo = Coupon.objects.create(amount=stake_combo, status='PENDING', confidence=65.0, is_archived=True)
    combo_odds = Decimal(1)
    
    for pick in final_picks:
        bulletin = pick['bulletin']
        odds = Decimal(str(pick['odds']))
        combo_odds *= odds
        
        CouponItem.objects.create(
            coupon=c_combo, match=bulletin, home_team=bulletin.home_team, away_team=bulletin.away_team,
            match_date=bulletin.match_date, match_time=bulletin.match_time, league=bulletin.league,
            prediction=pick['pick'], odds=odds, status='PENDING'
        )
        
    c_combo.total_odds = combo_odds
    c_combo.potential_return = stake_combo * combo_odds
    c_combo.save()
    coupons.append(c_combo)
    
    # 3. Strategy Analysis Text
    # Calculate scenarios
    # Worst case (0 wins): Loss Total
    # 1 Win (Avg single odds ~1.7): Return ~1.7 * 0.28*T = 0.47T. Loss 53% (Amortized half)
    # 2 Wins: Return ~2 * 0.47T = 0.94T. (Almost Break Even / Small Loss)
    # 3 Wins: Return 3 singles + Combo. 
    #   3 * 0.47T = 1.41T
    #   Combo: 0.16T * 1.7^3 = 0.16 * 4.9 = 0.78T
    #   Total: 2.19T (Double Money)
    
    match_names = ", ".join([f"{p['bulletin'].home_team}" for p in final_picks])
    
    strategy_text = f"""
    <strong>Seçilen Banko Adayları:</strong> {match_names}<br><br>
    
    Bu "Kombine + Tekli (3+1)" sistemi, paranızı 4 kupona bölerek riskinizi yönetir:<br><br>
    
    <span class='text-primary'>1️⃣ TEKLİ KUPONLAR (3 Adet):</span> Her maça ayrı ayrı <strong>{stake_per_single:.2f} TL</strong> yatırıldı. 
    amaç, maçlardan biri veya ikisi yatarsa bile kazananlardan gelen parayla zararı kapatmak (Amorti).<br>
    
    <span class='text-success'>🚀 KOMBİNE KUPON (1 Adet):</span> 3 maçın hepsi tutarsa devreye girecek <strong>{stake_combo:.2f} TL</strong>'lik kupon. 
    Büyük karı buradan hedefliyoruz.<br><br>
    
    <strong>Senaryolar:</strong><br>
    - <strong>1 Maç Gelirse:</strong> Yatırımın yaklaşık %40-50'si geri döner.<br>
    - <strong>2 Maç Gelirse:</strong> Yatırımın %90-110'u geri döner (Neredeyse Kayıpsız / Ufak Kar).<br>
    - <strong>3 Maç Gelirse:</strong> HEM Tekliler HEM Kombine tutar! <strong>Toplam {singles_return + c_combo.potential_return:.2f} TL</strong> kazanırsınız.
    """
    
    return {
        'coupons': coupons,
        'strategy_text': strategy_text,
        'focus_matches': final_picks
    }

def check_coupon_results(coupon):
    """
    Checks if pending items in coupon match known fixtures with scores.
    """
    items = coupon.items.filter(status='PENDING')
    if not items.exists():
        return

    for item in items:
        # Try to find a completed fixture
        # Note: Bilyoner Use 'Galatasaray' but Fixture might be 'Galatasaray A.Ş.'?
        # Using icontains might be risky if multiple matches exist, but usually recent one is matched.
        # We can also filter by date if stored cleanly.
        
        fixture = Fixture.objects.filter(
            score__isnull=False
        ).exclude(score='').filter(
            Q(home_team__icontains=item.home_team) & Q(away_team__icontains=item.away_team)
        ).first()

        if fixture:
            try:
                score = fixture.score.strip()
                if '-' not in score: continue
                
                parts = score.split('-')
                h_goals = int(parts[0])
                a_goals = int(parts[1])
                
                result = "X"
                if h_goals > a_goals: result = "1"
                elif a_goals > h_goals: result = "2"
                
                # Parse our prediction: "MS 1", "MS 2", "1", "2"
                pred = item.prediction.replace("MS ", "").replace(" (Banko)", "").strip()
                
                if pred == result:
                    item.status = 'WON'
                else:
                    item.status = 'LOST'
                item.save()
            except Exception as e:
                print(f"Error checking result for {item}: {e}")
                
    coupon.update_status()

