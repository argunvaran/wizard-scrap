from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Coupon
from .utils import generate_coupon, check_coupon_results
from decimal import Decimal
from django.db.models import Sum

def coupon_create(request):
    """
    Shows "Generated Suggestion" coupons (is_played=False).
    Allows creating NEW suggestions (which deletes old suggestions).
    """
    if request.method == 'POST':
        action = request.POST.get('action', 'generate')
        
        if action == 'play_all':
            drafts = Coupon.objects.filter(is_played=False)
            
            # Fetch existing signatures from played portfolio
            played_coupons = Coupon.objects.filter(is_played=True)
            played_signatures = set()
            for pc in played_coupons:
                for item in pc.items.all():
                    # Signature: Home + Away + Date (User request: "ev sahibi deplasman ve maç günü aynıysa")
                    h = item.home_team.strip().lower()
                    a = item.away_team.strip().lower()
                    d = item.match_date.strip()
                    sig = f"{h}|{a}|{d}"
                    played_signatures.add(sig)
            
            played_count = 0
            skipped_count = 0
            
            for draft in drafts:
                is_duplicate = False
                for item in draft.items.all():
                    h = item.home_team.strip().lower()
                    a = item.away_team.strip().lower()
                    d = item.match_date.strip()
                    sig = f"{h}|{a}|{d}"
                    
                    if sig in played_signatures:
                        is_duplicate = True
                        break
                
                if is_duplicate:
                    # If it's a duplicate of something already played, discard this draft
                    draft.delete()
                    skipped_count += 1
                else:
                    # Proceed to play
                    draft.is_played = True
                    draft.status = 'PENDING'
                    draft.save()
                    
                    # Add to local signature set to prevent duplicates WITHIN the current batch
                    for item in draft.items.all():
                         h = item.home_team.strip().lower()
                         a = item.away_team.strip().lower()
                         d = item.match_date.strip()
                         sig = f"{h}|{a}|{d}"
                         played_signatures.add(sig)

                    played_count += 1
            
            if played_count > 0:
                msg = f"{played_count} kupon portföye eklendi!"
                if skipped_count > 0:
                    msg += f" ({skipped_count} adet mükerrer kupon engellendi)"
                messages.success(request, msg)
            elif skipped_count > 0:
                messages.warning(request, f"Seçilen kuponların tamamı ({skipped_count}) zaten portföyünüzde bulunduğu için tekrar eklenmedi.")
            else:
                messages.info(request, "Oynanacak kupon bulunamadı.")
                
            return redirect('coupon_portfolio')
            
        elif action == 'special_targets':
            amount = 50 # Fixed investment as per request
            targets = [100, 500, 1000]
            
            # Archive old suggestions instead of deleting
            Coupon.objects.filter(is_played=False, is_archived=False).update(is_archived=True)
            
            from .utils import generate_target_coupon
            
            created_count = 0
            for target in targets:
                coupon = generate_target_coupon(amount, target)
                if coupon:
                    created_count += 1
            
            if created_count > 0:
                messages.success(request, f"{created_count} adet Özel Hedef Kuponu oluşturuldu! (50₺ -> 100₺ / 500₺ / 1000₺)")
            else:
                messages.error(request, "Yeterli güvenilir maç bulunamadığı için özel kuponlar oluşturulamadı.")
            
        elif action == 'generate':
            amount = request.POST.get('amount', 50)
            try:
                amount = Decimal(amount)
            except:
                amount = Decimal(50)
                
            # Archive old suggestions
            Coupon.objects.filter(is_played=False, is_archived=False).update(is_archived=True)
                
            coupons = generate_coupon(amount)
            
            if coupons:
                messages.success(request, f"{len(coupons)} adet yüksek ihtimalli tek maç önerisi oluşturuldu! Bunları oynamak için aşağıdan onaylayın.")
            else:
                messages.error(request, "Uygun analiz maçı bulunamadı.")
            
        elif action == 'strategic_hedge':
            amount = request.POST.get('amount', 300)
            try:
                amount = Decimal(amount)
            except:
                amount = Decimal(300) # Default total budget for this strategy
                
            # Archive old
            Coupon.objects.filter(is_played=False, is_archived=False).update(is_archived=True)
            
            from .utils import generate_guaranteed_trio_hedge
            
            hedge_result = generate_guaranteed_trio_hedge(amount)
            
            if hedge_result:
                messages.success(request, f"3+1 Garantili Üçlü Kombinasyon oluşturuldu!")
                # Render with special context
                return render(request, 'betting_engine/coupon_create.html', {
                    'coupons': hedge_result['coupons'],
                    'hedge_mode': True,
                    'strategy_text': hedge_result['strategy_text'],
                    # 'focus_matches': hedge_result['focus_matches']
                })
            else:
                messages.error(request, "Strateji için uygun oranlı (1.45 - 2.10) maç bulunamadı.")
                
        elif action == 'generate_legendary':
            # Efsane (100x) Kupon
            try:
                amount = Decimal(request.POST.get('amount', 50))
            except: amount = Decimal(50)
            
            # Archive old
            Coupon.objects.filter(is_played=False, is_archived=False).update(is_archived=True)
            from .utils import generate_legendary_coupon
            
            result = generate_legendary_coupon(amount, target_odds=100.0)
            
            if result:
                c = result['coupon']
                pred_list = result['prediction_summary']
                total_odds_fmt = "{:.2f}".format(result['total_odds'])
                
                msg = f"EFSANE KUPON OLUŞTURULDU! 🚀\n" \
                      f"Maç Sayısı: {result['item_count']} | Toplam Oran: {total_odds_fmt}\n" \
                      f"Tahminler: {pred_list}"
                      
                messages.success(request, msg)
                # Redirect to avoid form resubmission but also to show the coupon in the list below
            else:
                messages.error(request, "Şu an için 100 oranlı efsane kupon çıkaracak kadar uygun ve değerli maç yok. Daha sonra tekrar deneyin.")
            
    # Show active drafts only
    draft_coupons = Coupon.objects.filter(is_played=False, is_archived=False).order_by('potential_return')
    return render(request, 'betting_engine/coupon_create.html', {'coupons': draft_coupons})

def coupon_logs(request):
    """
    Comprehensive log searching and filtering view.
    """
    from django.db.models import Q
    
    # Base query: All coupons
    coupons = Coupon.objects.all().order_by('-created_at')
    
    # Filters
    log_type = request.GET.get('log_type') # played, analyzed, all
    status = request.GET.get('status') # won, lost, pending
    search = request.GET.get('search') # team name or id
    
    if log_type == 'played':
        coupons = coupons.filter(is_played=True)
    elif log_type == 'analyzed':
        coupons = coupons.filter(is_played=False)
    elif log_type == 'bilyoner':
        coupons = coupons.filter(execution_status='SUCCESS')
        
    if status:
        coupons = coupons.filter(status=status.upper())
        
    if search:
        # Search in ID or related Items (Team Names)
        if search.isdigit():
            coupons = coupons.filter(id=search)
        else:
            coupons = coupons.filter(
                Q(items__home_team__icontains=search) | 
                Q(items__away_team__icontains=search) |
                Q(items__league__icontains=search)
            ).distinct()
            
    # Pagination? Let's limit to 100 for performance if list is long
    coupons = coupons[:200]
            
    context = {
        'coupons': coupons,
        'log_type': log_type,
        'status': status,
        'search': search
    }
    return render(request, 'betting_engine/coupon_logs.html', context)

def coupon_portfolio(request):
    """
    Shows "Played" coupons (is_played=True).
    Matches the user request: "başka sayfada kuponlar oynanmış ve toplam kazanç yazıcak"
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'clear_portfolio':
             Coupon.objects.filter(is_played=True).delete()
             messages.success(request, "Tüm oynanmış kuponlar temizlendi.")
             return redirect('coupon_portfolio')

    coupons = Coupon.objects.filter(is_played=True).order_by('-confidence', '-created_at')
    
    # Date Filtering
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        coupons = coupons.filter(created_at__date__gte=start_date)
    if end_date:
        coupons = coupons.filter(created_at__date__lte=end_date)
    
    # Auto-update status
    pending_coupons = coupons.filter(status='PENDING')
    for coupon in pending_coupons:
        check_coupon_results(coupon)
        
    # --- STRICT BILYONER STATS FILTER ---
    # User Request: "sadece bilyonerden oynanmış başarılı olmuş olanların sonuçlarını görelim"
    bilyoner_coupons = coupons.filter(execution_status='SUCCESS')
    
    # Calculate Stats based on BILYONER CONFIRMED coupons only
    total_investment = bilyoner_coupons.aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Calculate Returns (Realized)
    won_coupons = bilyoner_coupons.filter(status='WON')
    total_won = won_coupons.aggregate(Sum('potential_return'))['potential_return__sum'] or 0
    
    # Calculate Potential Return of Pending Bilyoner Coupons
    pending_real_coupons = bilyoner_coupons.filter(status='PENDING')
    total_potential = pending_real_coupons.aggregate(Sum('potential_return'))['potential_return__sum'] or 0
    
    net_profit = total_won - total_investment
    
    # Pass filter params back to context
    context = {
        'coupons': coupons,
        'bilyoner_count': bilyoner_coupons.count(),
        'total_investment': total_investment,
        'total_won': total_won,
        'total_potential': total_potential,
        'net_profit': net_profit,
        'start_date': start_date,
        'end_date': end_date
    }
        
    return render(request, 'betting_engine/coupon_portfolio.html', context)

def coupon_list(request):
    # Deprecated or redirect to portfolio? Let's keep for backward compatibility or use as "History"
    return redirect('coupon_portfolio')

def coupon_detail(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    if coupon.status == 'PENDING':
        check_coupon_results(coupon)
    return render(request, 'betting_engine/coupon_detail.html', {'coupon': coupon})

from .models import BilyonerCredential
from .bot import BilyonerBot
import threading

def bilyoner_settings(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Simple update or create (assuming single user context)
        cred, created = BilyonerCredential.objects.get_or_create(id=1)
        cred.username = username
        if password: # Only update if new password provided
            cred.password = password
        cred.save()
        messages.success(request, "Bilyoner giriş bilgileri güncellendi.")
        return redirect('bilyoner_settings')
        
    cred = BilyonerCredential.objects.filter(id=1).first()
    return render(request, 'betting_engine/bilyoner_settings.html', {'credential': cred})

def play_coupon_on_bilyoner(request, pk):
    # Retrieve coupon and credentials
    coupon = get_object_or_404(Coupon, pk=pk)
    
    # If standard GET request, show confirmation page
    if request.method == 'GET':
        return render(request, 'betting_engine/coupon_confirm_play.html', {'coupon': coupon})
        
    # If POST request, execute the bot
    cred = BilyonerCredential.objects.filter(id=1).first()
    
    if not cred or not cred.username or not cred.password:
        messages.error(request, "Lütfen önce Bilyoner giriş bilgilerinizi ayarlayın.")
        return redirect('bilyoner_settings')
        
    # Get user verification choice from POST request
    # 'on' means skip = True. 'off' means skip = False.
    skip_val = request.POST.get('skip_verification', 'off')
    skip_verification = (skip_val == 'on')

    # Start bot in background thread to avoid blocking
    def run_bot():
        try:
             # Extract necessary data before threading to avoid DB connection issues
             amount = float(coupon.amount)
             coupon_items = list(coupon.items.all()) # Evaluate queryset to list
             
             bot = BilyonerBot(cred.decrypted_username, cred.decrypted_password)
             
             # Pass the skip_verification flag to the play_coupon method
             success = bot.play_coupon(coupon_items, amount, skip_verification=skip_verification)
             
             # Update status in DB - Re-fetch inside thread to be safe
             from django.db import connection
             try:
                 c_update = Coupon.objects.get(pk=coupon.pk)
                 if success:
                     c_update.execution_status = 'SUCCESS'
                     print(f"Coupon {coupon.id} played successfully. DB Updated.")
                 else:
                     c_update.execution_status = 'FAILED'
                     print(f"Coupon {coupon.id} failed to play. DB Updated.")
                 c_update.save()
             except Exception as db_e:
                 print(f"DB Update Error in Thread: {db_e}")
             finally:
                 connection.close()

        except Exception as e:
            print(f"Thread error: {e}")
        
    thread = threading.Thread(target=run_bot)
    thread.start()
    
    mode_msg = "KONTROLSÜZ (HIZLI)" if skip_verification else "GÜVENLİ (KONTROLLÜ)"
    messages.info(request, f"Bilyoner otomasyonu başlatıldı. Mod: {mode_msg}. Tarayıcıyı takip edin.")
    return redirect('coupon_portfolio')

def coupon_delete(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == 'POST':
        coupon.delete()
        messages.success(request, f"Kupon #{pk} veritabanından silindi.")
    return redirect(request.META.get('HTTP_REFERER', 'coupon_logs'))
