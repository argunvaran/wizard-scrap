import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'league_system.settings')
django.setup()

from betting_engine.models import Coupon, CouponItem

def clean_duplicates():
    print("Cleaning duplicates...")
    all_coupons = Coupon.objects.filter(is_played=True).order_by('created_at')
    
    seen_matches = set()
    coupons_to_delete = []
    
    for coupon in all_coupons:
        # Assuming single match coupons as per recent changes
        item = coupon.items.first()
        if not item:
            coupons_to_delete.append(coupon.id)
            continue
            
        # Key: HomeTeam-Date (or just HomeTeam if dates are messy, but Date is safer)
        # item.match_date might be "07.02.2026"
        key = f"{item.home_team}-{item.match_date}"
        
        if key in seen_matches:
            coupons_to_delete.append(coupon.id)
        else:
            seen_matches.add(key)
            
    if coupons_to_delete:
        print(f"Deleting {len(coupons_to_delete)} duplicate coupons...")
        Coupon.objects.filter(id__in=coupons_to_delete).delete()
    else:
        print("No duplicates found.")
        
if __name__ == "__main__":
    clean_duplicates()
