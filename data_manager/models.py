from django.db import models

class CountryChoices(models.TextChoices):
    TURKEY = 'TURKEY', 'Türkiye'
    ENGLAND = 'ENGLAND', 'İngiltere'
    SPAIN = 'SPAIN', 'İspanya'
    ITALY = 'ITALY', 'İtalya'
    GERMANY = 'GERMANY', 'Almanya' 

class BaseLeagueModel(models.Model):
    country = models.CharField(max_length=20, choices=CountryChoices.choices, default=CountryChoices.TURKEY)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Player(BaseLeagueModel):
    team_name = models.CharField(max_length=100)
    jersey_number = models.IntegerField(default=0)
    player_name = models.CharField(max_length=150)
    profile_url = models.URLField(max_length=500, blank=True, null=True)
    position = models.CharField(max_length=50, blank=True, null=True)
    age = models.IntegerField(default=0, null=True, blank=True)
    matches_played = models.IntegerField(default=0)
    starts = models.IntegerField(default=0)
    goals = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    yellow_cards = models.IntegerField(default=0)
    red_cards = models.IntegerField(default=0)
    
    def __str__(self):
        return f"[{self.get_country_display()}] {self.player_name} ({self.team_name})"

class Standing(BaseLeagueModel):
    rank = models.IntegerField(default=0)
    team = models.CharField(max_length=100)
    played = models.IntegerField(default=0)
    won = models.IntegerField(default=0)
    drawn = models.IntegerField(default=0)
    lost = models.IntegerField(default=0)
    goals_for = models.IntegerField(default=0)
    goals_against = models.IntegerField(default=0)
    average = models.IntegerField(default=0)
    points = models.IntegerField(default=0)

    class Meta:
        ordering = ['country', 'rank']

    def __str__(self):
        return f"[{self.get_country_display()}] {self.rank}. {self.team} ({self.points}p)"

class Fixture(BaseLeagueModel):
    week = models.CharField(max_length=100)  # "1. Hafta" etc.
    date = models.CharField(max_length=100, blank=True, null=True)
    time = models.CharField(max_length=50, blank=True, null=True)
    home_team = models.CharField(max_length=100)
    score = models.CharField(max_length=50, blank=True, null=True)
    away_team = models.CharField(max_length=100)

    class Meta:
        ordering = ['country', 'week']

    def __str__(self):
        return f"[{self.get_country_display()}] {self.week}: {self.home_team} vs {self.away_team}"

class BilyonerBulletin(BaseLeagueModel):
    unique_key = models.CharField(max_length=255, unique=True)
    league = models.CharField(max_length=100, blank=True, null=True)
    match_date = models.CharField(max_length=20, default="", blank=True)
    match_time = models.CharField(max_length=50) # "20:00"
    home_team = models.CharField(max_length=100)
    away_team = models.CharField(max_length=100)
    
    # Odds can be strings ("1.45") or Floats. Using CHAR for safety to avoid float precision issues during scrape/display
    ms_1 = models.CharField(max_length=10, default="-")
    ms_x = models.CharField(max_length=10, default="-")
    ms_2 = models.CharField(max_length=10, default="-")
    under_2_5 = models.CharField(max_length=10, default="-")
    over_2_5 = models.CharField(max_length=10, default="-")
    
    # AI Cache
    gemini_analysis = models.TextField(blank=True, null=True, verbose_name="Gemini AI Analizi")

    class Meta:
        ordering = ['country', 'match_time']
        verbose_name_plural = "Bilyoner Bulletins"

    def __str__(self):
        return f"[{self.get_country_display()}] {self.home_team} vs {self.away_team}"

class BilyonerBulletinStaging(BaseLeagueModel):
    unique_key = models.CharField(max_length=255, unique=True)
    league = models.CharField(max_length=100, blank=True, null=True)
    match_date = models.CharField(max_length=20, default="", blank=True)
    match_time = models.CharField(max_length=50) # "20:00"
    home_team = models.CharField(max_length=100)
    away_team = models.CharField(max_length=100)
    
    # Odds
    ms_1 = models.CharField(max_length=10, default="-")
    ms_x = models.CharField(max_length=10, default="-")
    ms_2 = models.CharField(max_length=10, default="-")
    under_2_5 = models.CharField(max_length=10, default="-")
    over_2_5 = models.CharField(max_length=10, default="-")

    class Meta:
        ordering = ['country', 'match_time']
        verbose_name_plural = "Bilyoner Bulletins (Staging)"

    def __str__(self):
        return f"[STAGING] {self.home_team} vs {self.away_team}"
