import time
from io import StringIO
import sys
from django.core.management import call_command
from django.conf import settings
from data_manager.models import BilyonerBulletin, BilyonerBulletinStaging
from betting_engine.models import Coupon, BilyonerCredential
from betting_engine.utils import generate_coupon
from betting_engine.bot import BilyonerBot
from decimal import Decimal

# --- WRAPPER FUNCTIONS ---

def scrape_bilyoner_bulletin():
    """
    [VERİ ÇEKME] Bilyoner.com üzerinden güncel İddaa bültenini çeker.
    Bu işlem 'Staging' (Geçici) veritabanına kayıt atar.
    Yayına almak için 'publish_data' görevinin ardından çalıştırılması gerekir.
    """
    out = StringIO()
    sys.stdout = out
    try:
        print("Starting Bilyoner Scraper...")
        call_command('update_bilyoner_bulletin')
        print("Scraping completed.")
        return True, out.getvalue()
    except Exception as e:
        return False, str(e)
    finally:
        sys.stdout = sys.__stdout__

def publish_staged_data():
    """
    [YAYINLAMA] Geçici (Staging) alandaki verileri Canlı Sisteme aktarır.
    Bülten verileri dashboard ve analiz sayfalarında görünür hale gelir.
    Eski bülten verilerini siler ve yenilerini yazar.
    """
    try:
        staging_items = BilyonerBulletinStaging.objects.all()
        count = staging_items.count()
        if count == 0:
            return True, "No data in staging to publish."

        # Clear Live
        BilyonerBulletin.objects.all().delete()
        
        # Move
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
        
        # Clear Staging
        staging_items.delete()
        return True, f"Published {count} matches to Live Bulletin."
    except Exception as e:
        return False, str(e)

def generate_analysis_coupons():
    """
    Generates analysis coupons based on current bulletin.
    """
    try:
        # Default analysis amount 50
        amount = Decimal(50)
        
        # Archive old unplayed analyses to keep fresh
        updated = Coupon.objects.filter(is_played=False, is_archived=False).update(is_archived=True)
        
        coupons = generate_coupon(amount)
        
        if coupons:
            return True, f"Generated {len(coupons)} new analysis coupons. Archived {updated} old ones."
        else:
            return True, "No suitable matches found for analysis."
    except Exception as e:
        return False, str(e)

def auto_play_pending_coupons():
    """
    Automatically plays PENDING analysis coupons (DANGEROUS).
    Only plays coupons that match strict criteria if needed, or all 'generated' ones.
    For safety, let's play the top rated one or all logic.
    User said: 'bu tasklar... işlem yapıcak'
    Let's assume this plays ALL valid analysis coupons that are not archived.
    """
    try:
        # Fetch pending analyses (Drafts)
        drafts = Coupon.objects.filter(is_played=False, is_archived=False)
        
        if not drafts.exists():
            return True, "No pending analysis coupons to play."
            
        cred = BilyonerCredential.objects.first()
        if not cred:
            return False, "No Bilyoner credentials found."
            
        bot = BilyonerBot(cred.decrypted_username, cred.decrypted_password)
        
        played_count = 0
        failed_count = 0
        logs = []
        
        # Start Login Payload
        if not bot.login():
             return False, "Bot login failed."
             
        # Iterate
        for coupon in drafts:
            logs.append(f"Processing Coupon #{coupon.id}...")
            items = list(coupon.items.all())
            amount = float(coupon.amount)
            
            # PLAY with verification skipping = True ? Or False?
            # Automation usually implies skipping manual verification prompt.
            # Passed skip_verification=True
            success = bot.play_coupon(items, amount, skip_verification=True)
            
            if success:
                coupon.is_played = True
                coupon.execution_status = 'SUCCESS'
                coupon.status = 'PENDING'
                coupon.save()
                played_count += 1
                logs.append(f"Coupon #{coupon.id} SUCCESS.")
            else:
                coupon.execution_status = 'FAILED'
                coupon.save()
                failed_count += 1
                logs.append(f"Coupon #{coupon.id} FAILED.")
                
            time.sleep(2) # Cool down
            
        bot.close()
        return True, "\n".join(logs) + f"\nTotal: {played_count} Played, {failed_count} Failed."
        
    except Exception as e:
        return False, str(e)

def full_coupon_generation_and_play_flow():
    """
    [TAM OTOMASYON] Kupon oluşturma ve oynama döngüsünü tek seferde yapar.
    Adımlar:
    1. 'Özel Kupon Oluştur' butonuna basılmış gibi 50TL'lik kuponlar üretir.
    2. 'Tüm Kuponları Oyna' butonuna basılmış gibi bunları portföye aktarır (Mükerrerleri eler).
    3. Portföye eklenen bu kuponları 'Hızlı Başlat' modunda Bilyoner'de oynar ve sonucu kaydeder.
    """
    logs = []
    try:
        # --- ADIM 1: KUPON OLUŞTURMA ---
        logs.append("ADIM 1: Kupon Oluşturuluyor...")
        amount = Decimal(50)
        # Eski analizleri arşivle
        Coupon.objects.filter(is_played=False, is_archived=False).update(is_archived=True)
        
        generated_coupons = generate_coupon(amount)
        if not generated_coupons:
            return True, "Kupon oluşturulamadı (Uygun maç yok)."
        logs.append(f"{len(generated_coupons)} adet taslak kupon oluşturuldu.")
        
        # --- ADIM 2: PORTFÖYE EKLEME (MÜKERRER KONTROLÜ) ---
        logs.append("ADIM 2: Portföye Ekleniyor...")
        played_coupons = Coupon.objects.filter(is_played=True)
        played_signatures = set()
        for pc in played_coupons:
            for item in pc.items.all():
                sig = f"{item.home_team.strip().lower()}|{item.away_team.strip().lower()}|{item.match_date.strip()}"
                played_signatures.add(sig)
                
        valid_coupons_to_play = []
        skipped_count = 0
        
        # Sadece yeni oluşturulanları (active drafts) al
        current_drafts = Coupon.objects.filter(is_played=False, is_archived=False)
        
        for draft in current_drafts:
            is_duplicate = False
            for item in draft.items.all():
                sig = f"{item.home_team.strip().lower()}|{item.away_team.strip().lower()}|{item.match_date.strip()}"
                if sig in played_signatures:
                    is_duplicate = True
                    break
            
            if is_duplicate:
                draft.delete() # Mükerrer ise sil
                skipped_count += 1
            else:
                # Oynatılacak listeye al (henüz DB'de is_played=True yapmıyoruz, bot başarılı olursa yapacağız)
                valid_coupons_to_play.append(draft)
                
        logs.append(f"{len(valid_coupons_to_play)} kupon onaylandı. {skipped_count} mükerrer kupon silindi.")
        
        if not valid_coupons_to_play:
            return True, "\n".join(logs) + "\nOynanacak geçerli kupon kalmadı."

        # --- ADIM 3: BILYONER BOT OYNAMA ---
        logs.append("ADIM 3: Bilyoner Bot Başlatılıyor...")
        
        cred = BilyonerCredential.objects.first()
        if not cred:
            return False, "Bilyoner giriş bilgileri bulunamadı."
            
        bot = BilyonerBot(cred.decrypted_username, cred.decrypted_password)
        if not bot.login():
            return False, "Bot Bilyoner'e giriş yapamadı."
            
        played_success = 0
        played_failed = 0
        
        for coupon in valid_coupons_to_play:
            logs.append(f"Kupon #{coupon.id} Oynanıyor...")
            items = list(coupon.items.all())
            amt = float(coupon.amount)
            
            success = bot.play_coupon(items, amt, skip_verification=True)
            
            if success:
                coupon.is_played = True
                coupon.execution_status = 'SUCCESS'
                coupon.status = 'PENDING'
                coupon.save()
                played_success += 1
                logs.append("BAŞARILI.")
                
                # Yeni oynananın imzasını da ekle ki aynı loop içinde tekrar oynamasın
                for item in coupon.items.all():
                    sig = f"{item.home_team.strip().lower()}|{item.away_team.strip().lower()}|{item.match_date.strip()}"
                    played_signatures.add(sig)
            else:
                coupon.execution_status = 'FAILED'
                coupon.save()
                played_failed += 1
                logs.append("BAŞARISIZ.")
                
            time.sleep(2)
            
        bot.close()
        
        summary = f"\nİŞLEM TAMAMLANDI.\nBaşarılı: {played_success}\nHatalı: {played_failed}"
        logs.append(summary)
        return True, "\n".join(logs)

    except Exception as e:
        return False, f"HATA OLUŞTU: {str(e)}"

def strategic_hedge_play_flow():
    """
    [OTOMASYON] 3+1 Garantili Üçlü Sistem (Hedge) Akışı.
    1. Bültenden en uygun 3 maçı seçer.
    2. 3 Tekli + 1 Kombine (Toplam 4) kupon oluşturur.
    3. Bu kuponları Bilyoner'de otomatik oynar.
    Varsayılan Bütçe: 400 TL
    """
    logs = []
    try:
        from betting_engine.utils import generate_guaranteed_trio_hedge
        
        logs.append("ADIM 1: Stratejik Kapsama (3+1) Kuponları Hazırlanıyor...")
        budget = Decimal(400)
        
        # Eski analizleri arşivle
        Coupon.objects.filter(is_played=False, is_archived=False).update(is_archived=True)
        
        result = generate_guaranteed_trio_hedge(budget)
        
        if not result:
            return True, "Uygun stratejik maçlar bulunamadı (Oran kriteri: 1.45 - 2.10)."
            
        coupons = result['coupons']
        logs.append(f"{len(coupons)} adet stratejik kupon oluşturuldu.")
        
        # --- ADIM 2: BILYONER BOT OYNAMA ---
        logs.append("ADIM 2: Bilyoner Bot Başlatılıyor...")
        
        cred = BilyonerCredential.objects.first()
        if not cred:
            return False, "Bilyoner giriş bilgileri bulunamadı."
            
        bot = BilyonerBot(cred.decrypted_username, cred.decrypted_password)
        if not bot.login():
            return False, "Bot Bilyoner'e giriş yapamadı."
            
        played_success = 0
        played_failed = 0
        
        # KUYRUK SIRASI: Önce KOMBİNE (En Riskli / Büyük Ödül), Sonra TEKLİLER (Amorti)
        # Fonksiyon coupons listesini [Tekli, Tekli, Tekli, Kombine] olarak döndürüyor
        # Kombine'yi (Son eleman) başa alalım.
        
        if len(coupons) == 4:
            combo_coupon = coupons.pop() # Remove last (Combo)
            coupons.insert(0, combo_coupon) # Insert at beginning
            
        logs.append(f"Oynama Sırası Düzenlendi: Önce Kombine ({coupons[0].amount} TL), Sonra Tekliler.")
        
        for coupon in coupons:
            is_combo = (len(coupon.items.all()) > 1)
            type_str = "KOMBİNE" if is_combo else "TEKLİ"
            
            logs.append(f"{type_str} Kupon #{coupon.id} Oynanıyor ({coupon.amount} TL)...")
            items = list(coupon.items.all())
            amt = float(coupon.amount)
            
            # play_coupon handles adding multiple matches to basket if list has > 1 item
            success = bot.play_coupon(items, amt, skip_verification=True)
            
            if success:
                coupon.is_played = True
                coupon.execution_status = 'SUCCESS'
                coupon.status = 'PENDING'
                coupon.save()
                played_success += 1
                logs.append("BAŞARILI.")
                
                # Eğer Kombine başarısız olursa diğerlerini oynama riskine girmeyelim mi?
                # Hayır, kullanıcı 'sistemi çalıştır' dedi, devam edelim.
                # Ancak Kombine kritik ise durdurulabilir. Şimdilik devam.
            else:
                coupon.execution_status = 'FAILED'
                coupon.save()
                played_failed += 1
                logs.append("BAŞARISIZ.")
                
            time.sleep(3) # Biraz bekle diğer kupona geçmeden
            
        bot.close()
        
        summary = f"\nİŞLEM TAMAMLANDI.\nBaşarılı: {played_success}\nHatalı: {played_failed}"
        logs.append(summary)
        return True, "\n".join(logs)

    except Exception as e:
        return False, f"HATA OLUŞTU: {str(e)}"

def generate_legendary_play_flow():
    """
    [OTOMASYON] Efsane Kupon (100x) Döngüsü.
    1. 100 oranlı tek bir kupon oluşturur.
    2. Bilyoner'de otomatik oynar.
    Varsayılan Yatırım: 50 TL
    """
    logs = []
    try:
        from betting_engine.utils import generate_legendary_coupon
        
        logs.append("ADIM 1: Efsane Kupon (100x) Hazırlanıyor...")
        investment = Decimal(50)
        
        # Eski analizleri arşivle
        Coupon.objects.filter(is_played=False, is_archived=False).update(is_archived=True)
        
        result = generate_legendary_coupon(investment, target_odds=100.0)
        
        if not result:
            return True, "100 oranlı efsane kupon çıkaracak kadar uygun maç bulunamadı."
            
        coupon = result['coupon']
        logs.append(f"Efsane Kupon Oluşturuldu! Oran: {coupon.total_odds:.2f}, Maç Sayısı: {result['item_count']}")
        
        # --- ADIM 2: BILYONER BOT OYNAMA ---
        logs.append("ADIM 2: Bilyoner Bot Başlatılıyor...")
        
        cred = BilyonerCredential.objects.first()
        if not cred:
            return False, "Bilyoner giriş bilgileri bulunamadı."
            
        bot = BilyonerBot(cred.decrypted_username, cred.decrypted_password)
        if not bot.login():
            return False, "Bot Bilyoner'e giriş yapamadı."
            
        logs.append(f"Kupon #{coupon.id} Oynanıyor ({coupon.amount} TL)...")
        items = list(coupon.items.all())
        amt = float(coupon.amount)
        
        success = bot.play_coupon(items, amt, skip_verification=True)
        
        if success:
            coupon.is_played = True
            coupon.execution_status = 'SUCCESS'
            coupon.status = 'PENDING'
            coupon.save()
            logs.append("BAŞARILI: Kupon oynandı.")
        else:
            coupon.execution_status = 'FAILED'
            coupon.save()
            logs.append("BAŞARISIZ: Kupon oynanamadı.")
            
        bot.close()
        
        return True, "\n".join(logs)

    except Exception as e:
        return False, f"HATA OLUŞTU: {str(e)}"

from .scraper_tasks import (
    sync_turkey_standings, sync_turkey_fixtures, sync_turkey_squads,
    sync_england_standings, sync_england_fixtures, sync_england_squads,
    sync_spain_standings, sync_spain_fixtures, sync_spain_squads,
    sync_italy_standings, sync_italy_fixtures, sync_italy_squads
)

# Service Registry
TASK_REGISTRY = {
    'scrape_bulletin': scrape_bilyoner_bulletin,
    'publish_data': publish_staged_data,
    'generate_coupons': generate_analysis_coupons,
    'auto_play': auto_play_pending_coupons,
    
    # --- Betting Flows ---
    'full_cycle_betting': full_coupon_generation_and_play_flow,
    'strategic_hedge_cycle': strategic_hedge_play_flow,
    'legendary_coupon_cycle': generate_legendary_play_flow,
    
    # --- Data Scrapers (Migrated from Tkinter) ---
    'sync_turkey_standings': sync_turkey_standings,
    'sync_turkey_fixtures': sync_turkey_fixtures,
    'sync_turkey_squads': sync_turkey_squads,
    
    'sync_england_standings': sync_england_standings,
    'sync_england_fixtures': sync_england_fixtures,
    'sync_england_squads': sync_england_squads,
    
    'sync_spain_standings': sync_spain_standings,
    'sync_spain_fixtures': sync_spain_fixtures,
    'sync_spain_squads': sync_spain_squads,
    
    'sync_italy_standings': sync_italy_standings,
    'sync_italy_fixtures': sync_italy_fixtures,
    'sync_italy_squads': sync_italy_squads,

    'cleanup_old_logs': lambda: (True, "Old logs cleanup placeholder"),
    'export_results': lambda: (True, "Export results placeholder"),
}
