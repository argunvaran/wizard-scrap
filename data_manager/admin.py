from django.contrib import admin
from .models import Player, Standing, Fixture

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('country', 'team_name', 'player_name', 'jersey_number', 'position', 'goals')
    list_filter = ('country', 'team_name', 'position')
    search_fields = ('player_name', 'team_name')

@admin.register(Standing)
class StandingAdmin(admin.ModelAdmin):
    list_display = ('country', 'rank', 'team', 'played', 'points')
    list_filter = ('country',)
    search_fields = ('team',)
    ordering = ('country', 'rank')

@admin.register(Fixture)
class FixtureAdmin(admin.ModelAdmin):
    list_display = ('country', 'week', 'home_team', 'score', 'away_team', 'date')
    list_filter = ('country', 'week')
    search_fields = ('home_team', 'away_team')
