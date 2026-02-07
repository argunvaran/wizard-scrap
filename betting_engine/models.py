from django.db import models
from data_manager.models import BilyonerBulletin, CountryChoices

class Coupon(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Bekliyor'),
        ('WON', 'Tuttu'),
        ('LOST', 'Yattı'),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=50.00, verbose_name="Yatırılan Tutar")
    total_odds = models.DecimalField(max_digits=10, decimal_places=2, default=1.00, verbose_name="Toplam Oran")
    potential_return = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Olası Kazanç")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING', verbose_name="Durum")
    confidence = models.FloatField(default=0.0, verbose_name="Güven Oranı (%)")
    is_played = models.BooleanField(default=False, verbose_name="Oynandı mı?")
    is_archived = models.BooleanField(default=False, verbose_name="Arşivlendi mi?") 
    execution_status = models.CharField(max_length=20, default='', blank=True, verbose_name="Bot İşlem Durumu") # SUCCESS, FAILED

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Kupon #{self.id} | {self.amount} TL | {self.get_status_display()}"

    def update_status(self):
        # Check all items, if any creates LOST -> Coupon LOST
        # If all WON -> Coupon WON
        # Else PENDING
        items = self.items.all()
        if not items.exists():
            return
            
        any_lost = False
        all_won = True
        
        for item in items:
            if item.status == 'LOST':
                any_lost = True
            if item.status != 'WON':
                all_won = False
        
        if any_lost:
            self.status = 'LOST'
        elif all_won:
            self.status = 'WON'
        else:
            self.status = 'PENDING'
        self.save()


class CouponItem(models.Model):
    coupon = models.ForeignKey(Coupon, related_name='items', on_delete=models.CASCADE)
    match = models.ForeignKey(BilyonerBulletin, on_delete=models.SET_NULL, null=True, blank=True, help_text="Reference to bulletin if available")
    
    # Snapshot fields in case bulletin is deleted
    home_team = models.CharField(max_length=100)
    away_team = models.CharField(max_length=100)
    match_date = models.CharField(max_length=50, blank=True)
    match_time = models.CharField(max_length=50, blank=True)
    league = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=50, default="TURKEY")

    prediction = models.CharField(max_length=50) # "MS 1", "MS 2", "MS X"
    odds = models.DecimalField(max_digits=5, decimal_places=2)
    
    status = models.CharField(max_length=10, choices=Coupon.STATUS_CHOICES, default='PENDING')

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} - {self.prediction} ({self.odds})"


from .security import encrypt_credential, decrypt_credential

class BilyonerCredential(models.Model):
    username = models.CharField(max_length=100, verbose_name="TC Kimlik / Üye No (Şifreli Saklanır)")
    password = models.CharField(max_length=255, verbose_name="Şifre (Şifreli Saklanır)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Encrypt sensitive fields before saving
        if self.password and not self.password.startswith("ENC::"):
            self.password = encrypt_credential(self.password)
            
        # Encrypt username too as requested (TC Kimlik)
        if self.username and not self.username.startswith("ENC::"):
            self.username = encrypt_credential(self.username)
            
        super().save(*args, **kwargs)

    @property
    def decrypted_password(self):
        return decrypt_credential(self.password)

    @property
    def decrypted_username(self):
        return decrypt_credential(self.username)

    def __str__(self):
        # Masked representation
        try:
            real_user = self.get_decrypted_username()
            masked = real_user[:2] + "****" + real_user[-2:] if len(real_user) > 4 else "****"
            return f"Bilyoner Hesabı: {masked}"
        except:
            return "Bilyoner Hesabı (Şifreli)"
